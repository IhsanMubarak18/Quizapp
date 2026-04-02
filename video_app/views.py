import random
import io
from datetime import date
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.utils import timezone
from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Category, Question, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, QuizResult
from .forms import QuestionForm, QuizForm, RandomQuestionSelectForm, CategoryFilterForm
from .selectors import (
    admin_dashboard_stats,
    admin_quizzes_queryset,
    admin_students_queryset,
    available_quizzes_queryset,
    filtered_students_queryset,
    ordered_questions_for_attempt,
    question_map_for_ids,
    review_items_for_attempt,
    student_qualification_options,
)
from users.forms import AdminUserCreationForm, AdminUserChangeForm
from users.models import StudentProfile

from django.http import HttpResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
import io
import pandas as pd
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.staticfiles import finders
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch

AuthUser = get_user_model()


# ─── Decorators ──────────────────────────────────────────────────────────────

def staff_required(view_func):
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/admin-login/'
    )(view_func)
    return decorated


def student_login_required(view_func):
    decorated = login_required(view_func, login_url='/login/')
    return decorated


def admin_manager_required(view_func):
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff and u.is_superuser,
        login_url='/admin-login/'
    )(view_func)
    return decorated


def max_attempts_check(view_func):
    """
    Decorator to check if student has reached max attempts before accessing quiz.
    This provides additional protection beyond the view-level checks.
    """
    def wrapper(request, quiz_id, *args, **kwargs):
        try:
            quiz = Quiz.objects.get(id=quiz_id)
            if quiz.has_reached_max_attempts(request.user):
                messages.error(request, f"You have reached the maximum number of attempts ({quiz.max_attempts}).")
                return redirect('video_app:quiz_list')
        except Quiz.DoesNotExist:
            messages.error(request, "Quiz not found.")
            return redirect('video_app:quiz_list')
        
        return view_func(request, quiz_id, *args, **kwargs)
    
    return wrapper


# ─── Home ─────────────────────────────────────────────────────────────────────

def home_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('video_app:admin_dashboard')
        return redirect('video_app:student_dashboard')
    return render(request, 'home.html')


# ─── Student Views ────────────────────────────────────────────────────────────

@student_login_required
def student_dashboard(request):
    student = getattr(request.user, 'student_profile', None)
    available_quizzes = available_quizzes_queryset()
    
    # Get all previous results (not just recent 5)
    all_results = (
        QuizResult.objects.filter(student=request.user)
        .select_related('quiz', 'attempt')
        .order_by('-completed_at')
    )
    
    # Group results by quiz to show all attempts per quiz
    results_by_quiz = {}
    for result in all_results:
        quiz_id = result.quiz.id
        if quiz_id not in results_by_quiz:
            results_by_quiz[quiz_id] = []
        results_by_quiz[quiz_id].append(result)
    
    attempted_quiz_ids = set(
        QuizAttempt.objects.filter(student=request.user, is_submitted=True)
        .values_list('quiz_id', flat=True)
    )
    
    # Build quiz data with remaining attempts
    quiz_data = []
    for quiz in available_quizzes:
        remaining = quiz.remaining_attempts(request.user)
        quiz_data.append({
            'quiz': quiz,
            'remaining_attempts': remaining,
            'can_retake': remaining is None or remaining > 0,
            'all_attempts': results_by_quiz.get(quiz.id, [])
        })
    
    return render(request, 'student/dashboard.html', {
        'student': student,
        'available_quizzes': quiz_data,
        'all_results': all_results,
        'results_by_quiz': results_by_quiz,
        'attempted_quiz_ids': attempted_quiz_ids,
        'quizzes_taken': len(attempted_quiz_ids),  # Count unique quizzes
    })



@student_login_required
def quiz_list(request):
    available = available_quizzes_queryset()
    # Mark which quizzes user has attempted
    attempted_ids = set(
        QuizAttempt.objects.filter(student=request.user, is_submitted=True)
        .values_list('quiz_id', flat=True)
    )
    
    # Build quiz data with remaining attempts
    quiz_data = []
    for q in available:
        attempted = q.id in attempted_ids
        remaining = q.remaining_attempts(request.user)
        quiz_data.append({
            'quiz': q,
            'attempted': attempted,
            'remaining_attempts': remaining
        })
    
    # Pagination
    paginator = Paginator(quiz_data, 12)  # 12 quizzes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'student/quiz_list.html', {
        'page_obj': page_obj,
        'quiz_data': page_obj
    })


@student_login_required
@max_attempts_check
def start_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not quiz.is_available():
        messages.error(request, "This quiz is not currently available.")
        return redirect('video_app:quiz_list')

    # Check if student has reached maximum attempts
    if quiz.has_reached_max_attempts(request.user):
        remaining = quiz.remaining_attempts(request.user)
        if remaining is None:
            messages.error(request, "This quiz has unlimited attempts.")
        else:
            messages.error(request, f"You have reached the maximum number of attempts ({quiz.max_attempts}).")
        return redirect('video_app:quiz_list')

    # Check for existing incomplete attempt
    existing = QuizAttempt.objects.filter(
        student=request.user, quiz=quiz, is_submitted=False
    ).first()

    if existing:
        # Check if time expired
        if existing.time_remaining_seconds() == 0:
            # Auto-submit
            _auto_submit(existing)
            return redirect('video_app:quiz_result', attempt_id=existing.id)
        attempt = existing
    else:
        # Build question order
        question_ids = list(
            QuizQuestion.objects.filter(quiz=quiz).values_list('question_id', flat=True)
        )
        if quiz.shuffle_questions:
            random.shuffle(question_ids)
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            question_order=question_ids,
        )

    questions = ordered_questions_for_attempt(attempt)

    # Load any existing answers: {question_id: list_of_selected_letters}
    existing_answers = {
        a.question_id: a.selected_answers
        for a in StudentAnswer.objects.filter(attempt=attempt)
    }

    return render(request, 'student/quiz_attempt.html', {
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'existing_answers': existing_answers,
        'time_remaining': attempt.time_remaining_seconds(),
    })


@student_login_required
def submit_quiz(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user)

    if attempt.is_submitted:
        return redirect('video_app:quiz_result', attempt_id=attempt.id)

    if request.method == 'POST':
        # Collect all question keys — supports both radio (single) and checkbox (multi)
        question_keys = set(k for k in request.POST if k.startswith('q_'))
        question_ids = []
        for key in question_keys:
            try:
                question_ids.append(int(key[2:]))
            except ValueError:
                continue
        question_map = question_map_for_ids(question_ids)
        for key in question_keys:
            try:
                question_id = int(key[2:])
                question = question_map.get(question_id)
                if question is None:
                    continue
                # getlist returns all checked values for the same name (checkboxes)
                values = [v.upper() for v in request.POST.getlist(key) if v]
                StudentAnswer.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={'selected_answers': values}
                )
            except (ValueError, Question.DoesNotExist):
                continue

    _compute_result(attempt)
    return redirect('video_app:quiz_result', attempt_id=attempt.id)


def _auto_submit(attempt):
    """Auto-submit an expired attempt without any new answers."""
    _compute_result(attempt)


def _compute_result(attempt):
    """Evaluate attempt answers and save QuizResult."""
    attempt.is_submitted = True
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=['is_submitted', 'submitted_at'])

    total = len(attempt.question_order)
    score = sum(
        1 for a in StudentAnswer.objects.filter(attempt=attempt).select_related('question') if a.is_correct
    )
    percentage = (score / total * 100) if total > 0 else 0.0

    QuizResult.objects.update_or_create(
        attempt=attempt,
        defaults={
            'student': attempt.student,
            'quiz': attempt.quiz,
            'score': score,
            'total_questions': total,
            'percentage': round(percentage, 2),
        }
    )


@student_login_required
def quiz_result(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user)
    if not attempt.is_submitted:
        return redirect('video_app:start_quiz', quiz_id=attempt.quiz.id)
    
    # Check if student has reached max attempts and should not access this quiz
    if attempt.quiz.has_reached_max_attempts(request.user):
        # Allow viewing old results but show a message about max attempts reached
        messages.info(request, f"You have reached the maximum number of attempts ({attempt.quiz.max_attempts}) for this quiz.")
    
    result = get_object_or_404(QuizResult, attempt=attempt)
    review_items = review_items_for_attempt(attempt)
    min_pct = attempt.quiz.certificate_min_percentage
    certificate_eligible = result.percentage >= min_pct
    return render(request, 'student/quiz_result.html', {
        'result': result,
        'attempt': attempt,
        'review_items': review_items,
        'certificate_eligible': certificate_eligible,
        'min_pct': min_pct,
        'max_attempts_reached': attempt.quiz.has_reached_max_attempts(request.user),
    })


@student_login_required
def download_certificate(request, attempt_id):

    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user)
    result = get_object_or_404(QuizResult, attempt=attempt)

    # Certificate eligibility check
    min_pct = attempt.quiz.certificate_min_percentage
    if result.percentage < min_pct:
        messages.error(
            request,
            f"Certificate not available. You need at least {min_pct:.0f}% "
            f"to receive a certificate (your score: {result.percentage:.1f}%)."
        )
        return redirect('video_app:quiz_result', attempt_id=attempt_id)

    student_profile = getattr(request.user, 'student_profile', None)
    student_name = student_profile.student_name if student_profile else request.user.get_full_name()
    
    # Get qualification info
    if student_profile:
        if student_profile.qualification == 'Others':
            qualification = student_profile.qualification_other or 'Others'
        else:
            qualification = student_profile.qualification
    else:
        qualification = ''

    buffer = io.BytesIO()

    page_size = landscape(A4)
    width, height = page_size

    pdf = canvas.Canvas(buffer, pagesize=page_size)

    # Background
    pdf.setFillColorRGB(0.97, 0.97, 0.99)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer border
    pdf.setStrokeColorRGB(0.74, 0.60, 0.18)
    pdf.setLineWidth(6)
    pdf.rect(30, 30, width - 60, height - 60)

    # Inner border
    pdf.setLineWidth(2)
    pdf.rect(45, 45, width - 90, height - 90)

    # ---------------- LOGO ----------------
    logo_path = finders.find('logo/talent_infosys_logo.jpg')

    if logo_path:
        logo_width = 160
        logo_height = 70

        pdf.drawImage(
            logo_path,
            width / 2 - logo_width / 2,
            height - 110,
            width=logo_width,
            height=logo_height,
            preserveAspectRatio=True,
            mask='auto'
        )

    # ---------------- TITLE ----------------
    pdf.setFont("Helvetica-Bold", 40)
    pdf.setFillColorRGB(0.22, 0.22, 0.45)
    pdf.drawCentredString(width/2, height-170, "Certificate of Achievement")

    # Decorative line
    pdf.setStrokeColorRGB(0.74, 0.60, 0.18)
    pdf.setLineWidth(1.5)
    pdf.line(120, height-185, width-120, height-185)

    # Subtitle
    pdf.setFont("Helvetica", 15)
    pdf.setFillColorRGB(0.4,0.4,0.4)
    pdf.drawCentredString(width/2, height-220, "This is to certify that")

    # Student Name
    pdf.setFont("Helvetica-Bold", 30)
    pdf.setFillColorRGB(0.12,0.12,0.45)
    pdf.drawCentredString(width/2, height-260, student_name)

    # Underline name
    name_width = pdf.stringWidth(student_name, "Helvetica-Bold", 30)
    pdf.setStrokeColorRGB(0.74, 0.60, 0.18)
    pdf.line(width/2 - name_width/2, height-265, width/2 + name_width/2, height-265)

    # Qualification
    if qualification:
        pdf.setFont("Helvetica", 14)
        pdf.setFillColorRGB(0.45,0.45,0.45)
        pdf.drawCentredString(width/2, height-300, f"Qualification: {qualification}")

    # Body text
    pdf.setFont("Helvetica", 15)
    pdf.setFillColorRGB(0.2,0.2,0.2)
    pdf.drawCentredString(width/2, height-340, "has successfully completed the quiz")

    # Quiz title
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColorRGB(0.2,0.2,0.5)
    pdf.drawCentredString(width/2, height-375, f'"{result.quiz.title}"')

    # Score section
    pdf.setFont("Helvetica", 14)
    score_text = (
        f"Score {result.score}/{result.total_questions}   |   "
        f"Percentage {result.percentage:.1f}%   |   "
        f"Grade {result.grade}"
    )
    pdf.drawCentredString(width/2, height-410, score_text)

    # Date
    date_str = result.completed_at.strftime("%d %B %Y")

    pdf.setFont("Helvetica", 12)
    pdf.setFillColorRGB(0.45,0.45,0.45)
    pdf.drawCentredString(width/2, height-440, f"Date of Completion: {date_str}")

    # Bottom decorative line
    pdf.setStrokeColorRGB(0.74, 0.60, 0.18)
    pdf.setLineWidth(1.5)
    pdf.line(120, 120, width-120, 120)

    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.6,0.6,0.6)
    pdf.drawCentredString(
        width/2,
        95,
        "Talent Infosys Online Quiz Management System"
    )

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')

    safe_name = student_name.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="certificate_{safe_name}.pdf"'

    return response
# ─── Admin Views ──────────────────────────────────────────────────────────────

@staff_required
def admin_dashboard(request):
    return render(request, 'admin_panel/dashboard.html', admin_dashboard_stats())


# ── Question Bank ──

@staff_required
def admin_question_bank(request):
    """Show categories first, then questions within selected category."""
    category_id = request.GET.get('category')
    search = request.GET.get('search', '')
    
    # Get all active categories with question counts
    categories = Category.objects.filter(is_active=True).annotate(
        question_count=Count('question')
    ).order_by('name')
    
    # Apply category search if provided
    if search:
        categories = categories.filter(name__icontains=search)
    
    # Handle category selection
    selected_category = None
    questions = Question.objects.none()
    
    if category_id:
        try:
            selected_category = Category.objects.get(id=category_id, is_active=True)
            questions = Question.objects.filter(category=selected_category).order_by('-created_at')
        except Category.DoesNotExist:
            pass
    
    return render(request, 'admin_panel/question_bank.html', {
        'categories': categories,
        'selected_category': selected_category,
        'questions': questions,
        'search': search,
    })


@staff_required
def admin_add_question(request):
    next_url = request.GET.get('next', '') or request.POST.get('next', '')
    add_to_quiz_id = request.GET.get('add_to_quiz', '') or request.POST.get('add_to_quiz', '')
    back_url = next_url or None
    back_label = '← Back to Quiz Questions' if next_url else None
    form = QuestionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        question = form.save()
        # Auto-add to quiz if requested (admin came from quiz questions page)
        if add_to_quiz_id:
            try:
                target_quiz = Quiz.objects.get(id=int(add_to_quiz_id))
                order = target_quiz.total_questions() + 1
                QuizQuestion.objects.get_or_create(
                    quiz=target_quiz, question=question,
                    defaults={'order': order}
                )
                messages.success(request, f"Question added and included in \"{target_quiz.title}\".")
            except (ValueError, Quiz.DoesNotExist):
                messages.success(request, "Question added to the question bank.")
        else:
            messages.success(request, "Question added successfully.")
        if next_url:
            return redirect(next_url)
        return redirect('video_app:admin_question_bank')
    return render(request, 'admin_panel/add_question.html', {
        'form': form, 'action': 'Add',
        'next_url': next_url, 'add_to_quiz_id': add_to_quiz_id,
        'back_url': back_url, 'back_label': back_label,
    })



@staff_required
def admin_edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    form = QuestionForm.from_instance(question, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(instance=question)
        messages.success(request, "Question updated successfully.")
        return redirect('video_app:admin_question_bank')
    return render(request, 'admin_panel/add_question.html', {
        'form': form, 'action': 'Edit', 'question': question,
    })


@staff_required
def admin_delete_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    if request.method == 'POST':
        question.delete()
        messages.success(request, "Question deleted.")
        return redirect('video_app:admin_question_bank')
    return render(request, 'admin_panel/confirm_delete.html', {
        'object_name': question.question_text[:80],
        'cancel_url_resolved': reverse('video_app:admin_question_bank'),
    })


@staff_required
def admin_edit_quiz_question(request, quiz_id, question_id):
    """Edit a question in a quiz, then return to quiz question manager."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    question = get_object_or_404(Question, id=question_id)
    back_url = reverse('video_app:admin_quiz_questions', kwargs={'quiz_id': quiz_id})
    form = QuestionForm.from_instance(question, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(instance=question)
        messages.success(request, "Question updated successfully.")
        return redirect('video_app:admin_quiz_questions', quiz_id=quiz_id)
    return render(request, 'admin_panel/add_question.html', {
        'form': form, 'action': 'Edit', 'question': question,
        'back_url': back_url,
        'back_label': f'← Back to "{quiz.title}" Questions',
    })


# ── Quiz Management ──

@staff_required
def admin_quizzes(request):
    quiz_data = admin_quizzes_queryset()
    return render(request, 'admin_panel/quiz_list.html', {'quiz_data': quiz_data})


@staff_required
def admin_add_quiz(request):
    form = QuizForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        quiz = form.save()
        messages.success(request, f'Quiz "{quiz.title}" created. Now add questions.')
        return redirect('video_app:admin_quiz_questions', quiz_id=quiz.id)
    return render(request, 'admin_panel/add_quiz.html', {'form': form, 'action': 'Create'})


@staff_required
def admin_edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Quiz updated.")
        return redirect('video_app:admin_quizzes')
    return render(request, 'admin_panel/add_quiz.html', {'form': form, 'action': 'Edit', 'quiz': quiz})


@staff_required
def admin_delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, "Quiz deleted.")
        return redirect('video_app:admin_quizzes')
    return render(request, 'admin_panel/confirm_delete.html', {
        'object_name': quiz.title,
        'cancel_url_resolved': reverse('video_app:admin_quizzes'),
    })


@staff_required
def admin_toggle_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.is_active = not quiz.is_active
    quiz.save()
    status = "activated" if quiz.is_active else "deactivated"
    messages.success(request, f'Quiz "{quiz.title}" {status}.')
    return redirect('video_app:admin_quizzes')


@staff_required
def admin_quiz_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz_questions = QuizQuestion.objects.filter(quiz=quiz).select_related('question').order_by('order')
    
    # Handle category filtering
    category_filter_form = CategoryFilterForm(request.GET or None)
    selected_category = None
    
    if category_filter_form.is_valid():
        selected_category = category_filter_form.cleaned_data.get('category')
    
    # All questions NOT already in this quiz, filtered by category if selected
    existing_ids = quiz_questions.values_list('question_id', flat=True)
    available_questions = Question.objects.exclude(id__in=existing_ids)
    
    if selected_category:
        available_questions = available_questions.filter(category=selected_category)
    
    available_questions = available_questions.select_related('category').order_by('-created_at')
    random_form = RandomQuestionSelectForm()
    
    # Pagination for available questions
    paginator = Paginator(available_questions, 20)  # 20 questions per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'admin_panel/quiz_questions.html', {
        'quiz': quiz,
        'quiz_questions': quiz_questions,
        'available_questions': page_obj,
        'page_obj': page_obj,
        'random_form': random_form,
        'category_filter_form': category_filter_form,
        'selected_category': selected_category,
    })


@staff_required
def admin_add_question_to_quiz(request, quiz_id):
    """Add specific questions from bank to quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    if request.method == 'POST':
        question_ids = []
        for qid in request.POST.getlist('question_ids'):
            try:
                question_ids.append(int(qid))
            except ValueError:
                continue
        existing_ids = set(
            QuizQuestion.objects.filter(quiz=quiz, question_id__in=question_ids)
            .values_list('question_id', flat=True)
        )
        new_question_ids = [qid for qid in question_ids if qid not in existing_ids]
        valid_question_ids = list(
            Question.objects.filter(id__in=new_question_ids).values_list('id', flat=True)
        )
        current_max = QuizQuestion.objects.filter(quiz=quiz).count()
        quiz_questions = [
            QuizQuestion(quiz=quiz, question_id=qid, order=current_max + index + 1)
            for index, qid in enumerate(valid_question_ids)
        ]
        QuizQuestion.objects.bulk_create(quiz_questions)
        messages.success(request, f"{len(valid_question_ids)} question(s) added to quiz.")
    return redirect('video_app:admin_quiz_questions', quiz_id=quiz_id)


@staff_required
def admin_add_random_questions(request, quiz_id):
    """Add N random questions from bank to quiz."""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    form = RandomQuestionSelectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        count = form.cleaned_data['count']
        existing_ids = QuizQuestion.objects.filter(quiz=quiz).values_list('question_id', flat=True)
        candidates = list(Question.objects.exclude(id__in=existing_ids))
        selected = random.sample(candidates, min(count, len(candidates)))
        current_max = QuizQuestion.objects.filter(quiz=quiz).count()
        QuizQuestion.objects.bulk_create([
            QuizQuestion(quiz=quiz, question=q, order=current_max + i + 1)
            for i, q in enumerate(selected)
        ])
        messages.success(request, f"{len(selected)} random question(s) added.")
    return redirect('video_app:admin_quiz_questions', quiz_id=quiz_id)


@staff_required
def admin_remove_question_from_quiz(request, quiz_id, question_id):
    QuizQuestion.objects.filter(quiz_id=quiz_id, question_id=question_id).delete()
    messages.success(request, "Question removed from quiz.")
    return redirect('video_app:admin_quiz_questions', quiz_id=quiz_id)


@admin_manager_required
def admin_users(request):
    search = request.GET.get('search', '')
    admins = AuthUser.objects.filter(is_staff=True).order_by('first_name', 'email')
    if search:
        admins = admins.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    return render(request, 'admin_panel/admin_users.html', {
        'admin_users': admins,
        'search': search,
    })


@admin_manager_required
def admin_add_user(request):
    form = AdminUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        admin_user = form.save()
        messages.success(request, f'Admin account "{admin_user.email}" created successfully.')
        return redirect('video_app:admin_users')
    return render(request, 'admin_panel/admin_user_form.html', {
        'form': form,
        'action': 'Create',
    })


@admin_manager_required
def admin_edit_user(request, user_id):
    admin_user = get_object_or_404(AuthUser, id=user_id, is_staff=True)
    form = AdminUserChangeForm(request.POST or None, instance=admin_user)
    if request.method == 'POST' and form.is_valid():
        if admin_user == request.user and not form.cleaned_data['can_manage_admins']:
            form.add_error('can_manage_admins', "You can't remove your own admin-management access.")
        elif admin_user == request.user and not form.cleaned_data['is_active']:
            form.add_error('is_active', "You can't deactivate your own admin account.")
        elif (
            admin_user.is_superuser and
            not form.cleaned_data['can_manage_admins'] and
            not AuthUser.objects.filter(is_staff=True, is_superuser=True).exclude(pk=admin_user.pk).exists()
        ):
            form.add_error('can_manage_admins', "At least one admin must keep permission to manage admins.")
        else:
            updated_user = form.save()
            if updated_user == request.user and form.cleaned_data.get('password1'):
                update_session_auth_hash(request, updated_user)
            messages.success(request, f'Admin account "{updated_user.email}" updated successfully.')
            return redirect('video_app:admin_users')
    return render(request, 'admin_panel/admin_user_form.html', {
        'form': form,
        'action': 'Edit',
        'admin_user': admin_user,
    })


@admin_manager_required
def admin_delete_user(request, user_id):
    admin_user = get_object_or_404(AuthUser, id=user_id, is_staff=True)
    if request.method == 'POST':
        if admin_user == request.user:
            messages.error(request, "You can't delete your own admin account.")
            return redirect('video_app:admin_users')
        if admin_user.is_superuser and AuthUser.objects.filter(is_staff=True, is_superuser=True).count() <= 1:
            messages.error(request, "At least one admin must keep permission to manage admins.")
            return redirect('video_app:admin_users')
        admin_user.delete()
        messages.success(request, "Admin account deleted.")
        return redirect('video_app:admin_users')
    return render(request, 'admin_panel/confirm_delete.html', {
        'object_name': admin_user.get_full_name() or admin_user.email,
        'cancel_url_resolved': reverse('video_app:admin_users'),
    })


@staff_required
def admin_students(request):
    search = request.GET.get('search', '')
    selected_qualification = request.GET.get('qualification', '')
    students = admin_students_queryset(search=search, qualification=selected_qualification)
    qualification_options = student_qualification_options()
    student_data = [{'profile': sp, 'attempts': sp.attempts_count} for sp in students]
    return render(request, 'admin_panel/students.html', {
        'student_data': student_data,
        'search': search,
        'qualification_options': qualification_options,
        'selected_qualification': selected_qualification,
    })


@staff_required
def admin_delete_student(request, user_id):
    user = get_object_or_404(AuthUser, id=user_id, is_staff=False)
    if request.method == 'POST':
        user.delete()
        messages.success(request, "Student deleted.")
        return redirect('video_app:admin_students')
    return render(request, 'admin_panel/confirm_delete.html', {
        'object_name': getattr(getattr(user, 'student_profile', None), 'student_name', user.email),
        'cancel_url_resolved': reverse('video_app:admin_students'),
    })


@staff_required
def admin_edit_student(request, user_id):
    user = get_object_or_404(get_user_model(), id=user_id)
    student_profile = getattr(user, 'student_profile', None)
    
    if not student_profile:
        messages.error(request, "Student profile not found.")
        return redirect('video_app:admin_students')
    
    if request.method == 'POST':
        # Update user email
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update student profile
        student_profile.student_name = request.POST.get('student_name', student_profile.student_name)
        student_profile.qualification = request.POST.get('qualification', student_profile.qualification)
        student_profile.qualification_other = request.POST.get('qualification_other', student_profile.qualification_other)
        student_profile.district = request.POST.get('district', student_profile.district)
        student_profile.district_other = request.POST.get('district_other', student_profile.district_other)
        student_profile.mobile_number = request.POST.get('mobile_number', student_profile.mobile_number)
        student_profile.save()
        
        messages.success(request, f"Student '{student_profile.student_name}' updated successfully.")
        return redirect('video_app:admin_students')
    
    return render(request, 'admin_panel/edit_student.html', {
        'user': user,
        'student_profile': student_profile
    })


@staff_required
def admin_students_excel(request):
    selected_qualification = request.GET.get('qualification', '')
    students = filtered_students_queryset(qualification=selected_qualification).order_by('student_name')
    
    # Create DataFrame
    data = []
    for i, student in enumerate(students, 1):
        # Get qualification info
        if student.qualification == 'Others':
            qualification = student.qualification_other or 'Others'
        else:
            qualification = student.qualification
        
        # Get district info
        if student.district == 'Others':
            district = student.district_other or 'Others'
        else:
            district = student.district
        
        data.append({
            'Sr No': i,
            'Student Name': student.student_name,
            'Qualification': qualification,
            'District': district,
            'Phone Number': student.mobile_number or 'N/A',
            'Email': student.user.email
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory with formatting
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Students', index=False)
        
        # Get the worksheet for formatting
        worksheet = writer.sheets['Students']
        
        # Import openpyxl styles
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        # Define styles
        header_font = Font(bold=True, size=12, color='000000')
        header_fill = PatternFill(start_color='D3E4FD', end_color='D3E4FD', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        
        # Cell alignment based on content type
        number_alignment = Alignment(horizontal='center', vertical='center')
        text_alignment = Alignment(horizontal='left', vertical='center')
        
        # Border style
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Format header row (row 1)
        for col_num, cell in enumerate(worksheet[1], 1):
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Format data rows with appropriate alignment
        for row_num in range(2, len(df) + 2):  # Start from row 2 (after header)
            for col_num, cell in enumerate(worksheet[row_num], 1):
                cell.border = thin_border
                
                # Apply alignment based on column
                if col_num == 1:  # Sr No - center
                    cell.alignment = number_alignment
                elif col_num == 4:  # Phone Number - center
                    cell.alignment = number_alignment
                else:  # Student Name, College Name, Email - left
                    cell.alignment = text_alignment
        
        # Auto-adjust column widths based on content
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            # Get max length of content in this column
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            # Set column width with some padding
            adjusted_width = min(max_length + 2, 50)  # Cap at 50 for very long content
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Set minimum widths for better appearance
        worksheet.column_dimensions['A'].width = 8   # Sr No
        worksheet.column_dimensions['B'].width = 25  # Student Name
        worksheet.column_dimensions['C'].width = 30  # College Name
        worksheet.column_dimensions['D'].width = 20  # Phone Number - increased from 15
        worksheet.column_dimensions['E'].width = 35  # Email
    
    # Reset position to beginning
    output.seek(0)
    
    # Create response
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    # Set filename
    filename = "students_list.xlsx"
    if selected_qualification:
        safe_qualification = selected_qualification.strip().lower().replace(" ", "_").replace("/", "_")
        filename = f"students_{safe_qualification}.xlsx"
    
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

# ── Reports ──

@staff_required
def admin_reports(request):
    selected_quiz_attempt = request.GET.get('quiz_attempt', '')
    selected_quiz_id = request.GET.get('quiz_id', '')
    selected_quiz = None
    
    results = (
        QuizResult.objects
        .select_related('student', 'student__student_profile', 'quiz', 'attempt')
        .order_by('-attempt__started_at', '-completed_at')
    )

    # Handle quiz-specific filtering
    if selected_quiz_id:
        try:
            results = results.filter(quiz_id=int(selected_quiz_id))
            selected_quiz = Quiz.objects.get(id=int(selected_quiz_id))
        except (ValueError, Quiz.DoesNotExist):
            selected_quiz_id = ''
    elif selected_quiz_attempt:
        try:
            quiz_id_str, attempt_date_str = selected_quiz_attempt.split('|', 1)
            attempt_date = date.fromisoformat(attempt_date_str)
            results = results.filter(
                quiz_id=int(quiz_id_str),
                attempt__started_at__date=attempt_date,
            )
            selected_quiz = Quiz.objects.get(id=int(quiz_id_str))
        except (TypeError, ValueError, Quiz.DoesNotExist):
            selected_quiz_attempt = ''
            selected_quiz = None

    # Get unique quizzes for filter dropdown
    raw_report_filters = (
        QuizResult.objects
        .values('quiz_id', 'quiz__title')
        .distinct()
        .order_by('quiz__title')
    )
    report_filters = [
        {
            'quiz_id': item['quiz_id'],
            'quiz_title': item['quiz__title'],
        }
        for item in raw_report_filters
    ]

    return render(request, 'admin_panel/reports.html', {
        'results': results,
        'report_filters': report_filters,
        'selected_quiz_attempt': selected_quiz_attempt,
        'selected_quiz_id': selected_quiz_id,
        'selected_quiz': selected_quiz,
    })


# ─── Category Management Views ────────────────────────────────────────────────────────────

@staff_required
def admin_categories(request):
    """Manage question categories."""
    categories = Category.objects.all().order_by('name')
    return render(request, 'admin_panel/categories.html', {
        'categories': categories,
    })


@staff_required
def admin_add_category(request):
    """Add a new category."""
    # Determine redirect URL based on original referrer (case-insensitive)
    if request.method == 'POST':
        original_referrer = request.POST.get('original_referrer', '').lower()
    else:
        original_referrer = request.META.get('HTTP_REFERER', '').lower()
    
    if 'admin-panel/questions' in original_referrer:
        redirect_url = 'video_app:admin_question_bank'
    else:
        redirect_url = 'video_app:admin_categories'
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, "Category name is required.")
            return render(request, 'admin_panel/add_category.html')
        
        if Category.objects.filter(name__iexact=name).exists():
            messages.error(request, "A category with this name already exists.")
            return render(request, 'admin_panel/add_category.html')
        
        category = Category.objects.create(
            name=name,
            description=description,
            is_active=is_active
        )
        messages.success(request, f"Category '{category.name}' created successfully.")
        return redirect(redirect_url)
    
    return render(request, 'admin_panel/add_category.html')


@staff_required
def admin_edit_category(request, category_id):
    """Edit an existing category."""
    category = get_object_or_404(Category, id=category_id)
    
    # Determine redirect URL based on original referrer (case-insensitive)
    if request.method == 'POST':
        original_referrer = request.POST.get('original_referrer', '').lower()
    else:
        original_referrer = request.META.get('HTTP_REFERER', '').lower()
    
    if 'admin-panel/questions' in original_referrer:
        redirect_url = 'video_app:admin_question_bank'
    else:
        redirect_url = 'video_app:admin_categories'
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, "Category name is required.")
            return redirect(redirect_url)
        
        # Check if name conflicts with another category
        existing = Category.objects.filter(name__iexact=name).exclude(id=category_id)
        if existing.exists():
            messages.error(request, "A category with this name already exists.")
            return redirect(redirect_url)
        
        category.name = name
        category.description = description
        category.is_active = is_active
        category.save()
        
        messages.success(request, f"Category '{category.name}' updated successfully.")
        return redirect(redirect_url)
    
    return render(request, 'admin_panel/edit_category.html', {
        'category': category,
    })


@staff_required
def admin_delete_category(request, category_id):
    """Delete a category and all its questions permanently."""
    category = get_object_or_404(Category, id=category_id)
    
    # Determine redirect URL based on referrer (case-insensitive)
    referrer = request.META.get('HTTP_REFERER', '').lower()
    if 'admin-panel/questions' in referrer:
        redirect_url = 'video_app:admin_question_bank'
    else:
        redirect_url = 'video_app:admin_categories'
    
    # Get questions in this category
    questions_count = category.question_count()
    
    # Permanently delete the category and all its questions
    Question.objects.filter(category=category).delete()
    category.delete()
    
    if questions_count > 0:
        messages.warning(request, f"Category '{category.name}' and {questions_count} question(s) have been permanently deleted.")
    else:
        messages.success(request, f"Category '{category.name}' deleted successfully.")
    
    return redirect(redirect_url)


@staff_required
def admin_bulk_assign_category(request):
    """Bulk assign questions to a category - DEPRECATED."""
    # This functionality has been removed as requested
    return redirect('video_app:admin_question_bank')
