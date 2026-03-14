import re
from datetime import datetime
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import StudentProfile

from .models import Question, Quiz, QuizAttempt, QuizResult
from .selectors import DASHBOARD_STATS_CACHE_KEY, admin_dashboard_stats


class QuizScheduleEditTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            email='admin@example.com',
            first_name='Admin',
            password='testpass123',
        )
        self.admin_user.is_staff = True
        self.admin_user.is_superuser = True
        self.admin_user.save()

    def test_edit_quiz_preserves_schedule_when_admin_submits_existing_values(self):
        local_tz = timezone.get_current_timezone()
        original_start = timezone.make_aware(datetime(2026, 3, 20, 10, 30), local_tz)
        original_end = timezone.make_aware(datetime(2026, 3, 20, 12, 45), local_tz)
        quiz = Quiz.objects.create(
            title='Physics Quiz',
            description='Original description',
            time_limit_minutes=30,
            shuffle_questions=True,
            is_active=True,
            certificate_min_percentage=60,
            start_time=original_start,
            end_time=original_end,
        )

        self.client.force_login(self.admin_user)
        url = reverse('video_app:admin_edit_quiz', args=[quiz.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        page = response.content.decode()
        start_match = re.search(r'name="start_time"[^>]*value="([^"]*)"', page)
        end_match = re.search(r'name="end_time"[^>]*value="([^"]*)"', page)
        self.assertIsNotNone(start_match)
        self.assertIsNotNone(end_match)

        start_value = start_match.group(1)
        end_value = end_match.group(1)
        self.assertEqual(
            start_value,
            timezone.localtime(original_start).strftime('%Y-%m-%dT%H:%M'),
        )
        self.assertEqual(
            end_value,
            timezone.localtime(original_end).strftime('%Y-%m-%dT%H:%M'),
        )

        response = self.client.post(url, {
            'title': 'Physics Quiz Updated',
            'description': 'Updated description',
            'time_limit_minutes': 45,
            'shuffle_questions': 'on',
            'is_active': 'on',
            'certificate_min_percentage': '75',
            'start_time': start_value,
            'end_time': end_value,
        })

        self.assertRedirects(response, reverse('video_app:admin_quizzes'))

        quiz.refresh_from_db()
        self.assertEqual(quiz.title, 'Physics Quiz Updated')
        self.assertEqual(quiz.description, 'Updated description')
        self.assertEqual(quiz.time_limit_minutes, 45)
        self.assertEqual(quiz.certificate_min_percentage, 75.0)
        self.assertEqual(quiz.start_time, original_start)
        self.assertEqual(quiz.end_time, original_end)

    def test_edit_quiz_with_schedule_renders_locked_active_toggle_ui(self):
        local_tz = timezone.get_current_timezone()
        quiz = Quiz.objects.create(
            title='Scheduled Quiz',
            time_limit_minutes=30,
            is_active=True,
            start_time=timezone.make_aware(datetime(2026, 3, 21, 9, 0), local_tz),
            end_time=timezone.make_aware(datetime(2026, 3, 21, 11, 0), local_tz),
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('video_app:admin_edit_quiz', args=[quiz.id]))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="schedule-active-toggle"', html)
        self.assertIn('schedule-active-toggle is-locked', html)
        self.assertIn('Scheduling controls quiz visibility automatically.', html)
        self.assertIn('id="schedule-active-toggle-mirror"', html)


class StudentTemplateRenderingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student_user = user_model.objects.create_user(
            email='student@example.com',
            first_name='Student',
            password='testpass123',
        )
        StudentProfile.objects.create(
            user=self.student_user,
            student_name='Student Example',
            college_name='Example College',
            mobile_number='1234567890',
        )

    def test_dashboard_and_quiz_list_render_grades_and_schedule_values(self):
        now = timezone.now()
        quiz = Quiz.objects.create(
            title='Chemistry Quiz',
            description='Quiz description',
            time_limit_minutes=20,
            is_active=True,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
        )
        attempt = QuizAttempt.objects.create(
            student=self.student_user,
            quiz=quiz,
            is_submitted=True,
            submitted_at=now,
            question_order=[],
        )
        result = QuizResult.objects.create(
            attempt=attempt,
            student=self.student_user,
            quiz=quiz,
            score=9,
            total_questions=10,
            percentage=90.0,
        )

        self.client.force_login(self.student_user)

        dashboard_response = self.client.get(reverse('video_app:student_dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_html = dashboard_response.content.decode()
        self.assertNotIn('{{ grade }}', dashboard_html)
        self.assertNotIn('{{ quiz.end_time|date:"d M Y, H:i" }}', dashboard_html)
        self.assertIn(result.grade, dashboard_html)
        self.assertIn(timezone.localtime(quiz.start_time).strftime('%d %b %Y, %H:%M'), dashboard_html)
        self.assertIn(timezone.localtime(quiz.end_time).strftime('%d %b %Y, %H:%M'), dashboard_html)

        quiz_list_response = self.client.get(reverse('video_app:quiz_list'))
        self.assertEqual(quiz_list_response.status_code, 200)
        quiz_list_html = quiz_list_response.content.decode()
        self.assertNotIn('{{ quiz.end_time|date:"d M Y, H:i" }}', quiz_list_html)
        self.assertIn(timezone.localtime(quiz.start_time).strftime('%d %b %Y, %H:%M'), quiz_list_html)
        self.assertIn(timezone.localtime(quiz.end_time).strftime('%d %b %Y, %H:%M'), quiz_list_html)


class AdminReportsFilterTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            email='reports-admin@example.com',
            first_name='Reports',
            password='testpass123',
        )
        self.admin_user.is_staff = True
        self.admin_user.is_superuser = True
        self.admin_user.save()

        self.student_one = user_model.objects.create_user(
            email='alice@example.com',
            first_name='Alice',
            password='testpass123',
        )
        StudentProfile.objects.create(
            user=self.student_one,
            student_name='Alice Example',
            college_name='North College',
            mobile_number='1111111111',
        )

        self.student_two = user_model.objects.create_user(
            email='bob@example.com',
            first_name='Bob',
            password='testpass123',
        )
        StudentProfile.objects.create(
            user=self.student_two,
            student_name='Bob Example',
            college_name='South College',
            mobile_number='2222222222',
        )

    def _create_result(self, student, quiz, started_at, score, total_questions):
        attempt = QuizAttempt.objects.create(
            student=student,
            quiz=quiz,
            is_submitted=True,
            submitted_at=started_at,
            question_order=[],
        )
        QuizAttempt.objects.filter(pk=attempt.pk).update(
            started_at=started_at,
            submitted_at=started_at,
            is_submitted=True,
        )
        attempt.refresh_from_db()

        percentage = round((score / total_questions) * 100, 2)
        result = QuizResult.objects.create(
            attempt=attempt,
            student=student,
            quiz=quiz,
            score=score,
            total_questions=total_questions,
            percentage=percentage,
        )
        QuizResult.objects.filter(pk=result.pk).update(completed_at=started_at + timedelta(minutes=20))
        return QuizResult.objects.get(pk=result.pk)

    def test_reports_filter_groups_by_quiz_name_and_attempt_date(self):
        local_tz = timezone.get_current_timezone()
        date_one = timezone.make_aware(datetime(2026, 3, 12, 14, 0), local_tz)
        date_two = timezone.make_aware(datetime(2026, 3, 13, 15, 30), local_tz)

        science_quiz = Quiz.objects.create(title='Science Quiz', is_active=True)
        math_quiz = Quiz.objects.create(title='Math Quiz', is_active=True)

        science_result_day_one = self._create_result(
            student=self.student_one,
            quiz=science_quiz,
            started_at=date_one,
            score=8,
            total_questions=10,
        )
        self._create_result(
            student=self.student_two,
            quiz=science_quiz,
            started_at=date_two,
            score=7,
            total_questions=10,
        )
        self._create_result(
            student=self.student_one,
            quiz=math_quiz,
            started_at=date_one,
            score=9,
            total_questions=10,
        )

        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('video_app:admin_reports'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Science Quiz - 12 Mar 2026', html)
        self.assertIn('Science Quiz - 13 Mar 2026', html)
        self.assertIn('Math Quiz - 12 Mar 2026', html)

        filter_value = f'{science_quiz.id}|2026-03-12'
        response = self.client.get(reverse('video_app:admin_reports'), {
            'quiz_attempt': filter_value,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_quiz_attempt'], filter_value)
        filtered_results = list(response.context['results'])
        self.assertEqual(len(filtered_results), 1)
        self.assertEqual(filtered_results[0].id, science_result_day_one.id)

        filtered_html = response.content.decode()
        self.assertIn('Alice Example', filtered_html)
        self.assertNotIn('Bob Example', filtered_html)
        self.assertNotIn('<td>Math Quiz</td>', filtered_html)


class AdminStudentsExportTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            email='students-admin@example.com',
            first_name='Students',
            password='testpass123',
        )
        self.admin_user.is_staff = True
        self.admin_user.is_superuser = True
        self.admin_user.save()

        self._create_student('alice@example.com', 'Alice Example', 'North College', '1111111111')
        self._create_student('bob@example.com', 'Bob Example', 'North College', '2222222222')
        self._create_student('carol@example.com', 'Carol Example', 'South College', '3333333333')

    def _create_student(self, email, student_name, college_name, mobile_number):
        user_model = get_user_model()
        student = user_model.objects.create_user(
            email=email,
            first_name=student_name.split()[0],
            password='testpass123',
        )
        StudentProfile.objects.create(
            user=student,
            student_name=student_name,
            college_name=college_name,
            mobile_number=mobile_number,
        )
        return student

    def test_students_page_and_pdf_can_be_filtered_by_college(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('video_app:admin_students'), {
            'college': 'North College',
        })

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Alice Example', html)
        self.assertIn('Bob Example', html)
        self.assertNotIn('Carol Example', html)
        self.assertIn('value="North College" selected', html)
        self.assertIn('?college=North%20College', html)

        pdf_response = self.client.get(reverse('video_app:admin_students_pdf'), {
            'college': 'North College',
        })

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
        self.assertIn('students_north_college.pdf', pdf_response['Content-Disposition'])
        self.assertGreater(len(pdf_response.content), 0)


class AdminUserManagementTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.super_admin = user_model.objects.create_superuser(
            email='owner@example.com',
            first_name='Owner',
            password='testpass123',
        )
        self.standard_admin = user_model.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            password='testpass123',
        )
        self.standard_admin.is_staff = True
        self.standard_admin.save()

    def test_only_superusers_can_access_admin_user_management(self):
        self.client.force_login(self.standard_admin)

        response = self.client.get(reverse('video_app:admin_users'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin-login/', response['Location'])

    def test_superuser_can_create_edit_and_delete_admin_users(self):
        self.client.force_login(self.super_admin)

        create_response = self.client.post(reverse('video_app:admin_add_user'), {
            'email': 'manager@example.com',
            'first_name': 'Manager',
            'last_name': 'Admin',
            'password1': 'securepass123',
            'password2': 'securepass123',
            'is_active': 'on',
            'can_manage_admins': 'on',
        })

        self.assertRedirects(create_response, reverse('video_app:admin_users'))
        created_admin = get_user_model().objects.get(email='manager@example.com')
        self.assertTrue(created_admin.is_staff)
        self.assertTrue(created_admin.is_superuser)

        edit_response = self.client.post(reverse('video_app:admin_edit_user', args=[created_admin.id]), {
            'email': 'manager@example.com',
            'first_name': 'Updated',
            'last_name': 'Admin',
            'password1': '',
            'password2': '',
            'is_active': 'on',
        })

        self.assertRedirects(edit_response, reverse('video_app:admin_users'))
        created_admin.refresh_from_db()
        self.assertEqual(created_admin.first_name, 'Updated')
        self.assertFalse(created_admin.is_superuser)
        self.assertTrue(created_admin.is_staff)

        delete_response = self.client.post(reverse('video_app:admin_delete_user', args=[created_admin.id]))

        self.assertRedirects(delete_response, reverse('video_app:admin_users'))
        self.assertFalse(get_user_model().objects.filter(email='manager@example.com').exists())

    def test_superuser_cannot_delete_own_admin_account(self):
        self.client.force_login(self.super_admin)

        response = self.client.post(reverse('video_app:admin_delete_user', args=[self.super_admin.id]))

        self.assertRedirects(response, reverse('video_app:admin_users'))
        self.assertTrue(get_user_model().objects.filter(pk=self.super_admin.pk).exists())


class PerformanceOptimizationTests(TestCase):
    def test_dashboard_stats_cache_is_invalidated_when_related_data_changes(self):
        cache.clear()

        stats = admin_dashboard_stats()

        self.assertEqual(stats['total_questions'], 0)
        self.assertIsNotNone(cache.get(DASHBOARD_STATS_CACHE_KEY))

        Question.objects.create(
            question_text='What is 2 + 2?',
            option_a='4',
            option_b='5',
            correct_answers=['A'],
        )

        self.assertIsNone(cache.get(DASHBOARD_STATS_CACHE_KEY))
