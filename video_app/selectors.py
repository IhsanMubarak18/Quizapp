from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from users.models import StudentProfile

from .models import Question, Quiz, QuizAttempt

AuthUser = get_user_model()

DASHBOARD_STATS_CACHE_KEY = 'admin-dashboard-stats'
COLLEGE_OPTIONS_CACHE_KEY = 'student-college-options'


def admin_dashboard_stats():
    stats = cache.get(DASHBOARD_STATS_CACHE_KEY)
    if stats is None:
        stats = {
            'total_questions': Question.objects.count(),
            'total_quizzes': Quiz.objects.count(),
            'total_students': AuthUser.objects.filter(is_staff=False).count(),
            'total_attempts': QuizAttempt.objects.filter(is_submitted=True).count(),
            'total_admin_users': AuthUser.objects.filter(is_staff=True).count(),
        }
        cache.set(DASHBOARD_STATS_CACHE_KEY, stats, timeout=30)
    return stats


def student_college_options():
    options = cache.get(COLLEGE_OPTIONS_CACHE_KEY)
    if options is None:
        options = list(
            StudentProfile.objects.exclude(college_name='')
            .order_by('college_name')
            .values_list('college_name', flat=True)
            .distinct()
        )
        cache.set(COLLEGE_OPTIONS_CACHE_KEY, options, timeout=300)
    return options


def available_quizzes_queryset(now=None):
    now = now or timezone.now()
    manual_availability = Q(start_time__isnull=True, end_time__isnull=True, is_active=True)
    scheduled_availability = (
        (Q(start_time__isnull=False) | Q(end_time__isnull=False)) &
        (Q(start_time__isnull=True) | Q(start_time__lte=now)) &
        (Q(end_time__isnull=True) | Q(end_time__gte=now))
    )
    return (
        Quiz.objects.filter(manual_availability | scheduled_availability)
        .annotate(question_count=Count('quizquestion', distinct=True))
        .order_by('-created_at')
    )


def admin_quizzes_queryset():
    return (
        Quiz.objects.annotate(
            question_count=Count('quizquestion', distinct=True),
            attempt_count=Count('attempts', filter=Q(attempts__is_submitted=True), distinct=True),
        )
        .order_by('-created_at')
    )


def filtered_students_queryset(search='', college=''):
    students = StudentProfile.objects.select_related('user')
    if search:
        students = students.filter(
            Q(student_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(college_name__icontains=search) |
            Q(mobile_number__icontains=search)
        )
    if college:
        students = students.filter(college_name=college)
    return students


def admin_students_queryset(search='', college=''):
    return (
        filtered_students_queryset(search=search, college=college)
        .annotate(
            attempts_count=Count(
                'user__quiz_attempts',
                filter=Q(user__quiz_attempts__is_submitted=True),
                distinct=True,
            )
        )
        .order_by('-user__date_joined')
    )


def ordered_questions_for_attempt(attempt):
    question_map = Question.objects.in_bulk(attempt.question_order)
    return [question_map[qid] for qid in attempt.question_order if qid in question_map]


def question_map_for_ids(question_ids):
    return Question.objects.in_bulk(question_ids)


def review_items_for_attempt(attempt):
    question_map = question_map_for_ids(attempt.question_order)
    answer_map = {
        answer.question_id: answer
        for answer in attempt.answers.select_related('question')
    }
    items = []
    for question_id in attempt.question_order:
        question = question_map.get(question_id)
        if question is None:
            continue
        answer = answer_map.get(question_id)
        selected_answers = answer.selected_answers if answer else []
        correct_answers = set(a.upper() for a in (question.correct_answers or []))
        selected_set = set(a.upper() for a in selected_answers)
        items.append({
            'question': question,
            'selected_answers': selected_answers,
            'is_correct': selected_set == correct_answers and len(selected_set) > 0,
        })
    return items
