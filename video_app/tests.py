import re
from datetime import datetime
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import StudentProfile

from .models import Quiz, QuizAttempt, QuizResult


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
