import random
import io
from datetime import date
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.utils import timezone
from django.db.models import Q
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Question, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, QuizResult
from .forms import QuestionForm, QuizForm, RandomQuestionSelectForm
from .selectors import (
    admin_dashboard_stats,
    admin_quizzes_queryset,
    admin_students_queryset,
    available_quizzes_queryset,
    filtered_students_queryset,
    ordered_questions_for_attempt,
    question_map_for_ids,
    review_items_for_attempt,
    student_college_options,
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

import io
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.staticfiles import finders
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch

import io

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
    recent_results = (
        QuizResult.objects.filter(student=request.user)
        .select_related('quiz', 'attempt')
        .order_by('-completed_at')[:5]
    )
    attempted_quiz_ids = set(
        QuizAttempt.objects.filter(student=request.user, is_submitted=True)
        .values_list('quiz_id', flat=True)
    )
    return render(request, 'student/dashboard.html', {
        'student': student,
        'available_quizzes': available_quizzes,
        'recent_results': recent_results,
        'attempted_quiz_ids': attempted_quiz_ids,
    })



@student_login_required
def quiz_list(request):
    available = available_quizzes_queryset()
    # Mark which quizzes user has attempted
    attempted_ids = set(
        QuizAttempt.objects.filter(student=request.user, is_submitted=True)
        .values_list('quiz_id', flat=True)
    )
    quiz_data = [{'quiz': q, 'attempted': q.id in attempted_ids} for q in available]
    
    # Pagination
    paginator = Paginator(quiz_data, 12)  # 12 quizzes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'student/quiz_list.html', {
        'page_obj': page_obj,
        'quiz_data': page_obj
    })


@student_login_required
def start_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if not quiz.is_available():
        messages.error(request, "This quiz is not currently available.")
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
    college_name = student_profile.college_name if student_profile else ''

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

    # College
    if college_name:
        pdf.setFont("Helvetica", 14)
        pdf.setFillColorRGB(0.45,0.45,0.45)
        pdf.drawCentredString(width/2, height-300, f"from {college_name}")

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
        "Online Quiz Management System — Generated Certificate"
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
    search = request.GET.get('search', '')
    questions = Question.objects.all().order_by('-created_at')
    if search:
        questions = questions.filter(question_text__icontains=search)
    return render(request, 'admin_panel/question_bank.html', {
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
    # All questions NOT already in this quiz
    existing_ids = quiz_questions.values_list('question_id', flat=True)
    available_questions = Question.objects.exclude(id__in=existing_ids).order_by('-created_at')
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
    selected_college = request.GET.get('college', '')
    students = admin_students_queryset(search=search, college=selected_college)
    college_options = student_college_options()
    student_data = [{'profile': sp, 'attempts': sp.attempts_count} for sp in students]
    return render(request, 'admin_panel/students.html', {
        'student_data': student_data,
        'search': search,
        'college_options': college_options,
        'selected_college': selected_college,
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
def admin_students_pdf(request):

    selected_college = request.GET.get('college', '')
    students = filtered_students_queryset(college=selected_college).order_by('student_name')

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'title',
        parent=styles['Title'],
        alignment=1,
        fontSize=18,
        spaceAfter=6
    )

    meta_style = ParagraphStyle(
        'meta',
        parent=styles['Normal'],
        alignment=1,
        textColor=colors.grey,
        fontSize=9
    )

    elements = []

    title = "Students List"
    elements.append(Paragraph(title, title_style))

    elements.append(
        Paragraph(
            f"Generated on {timezone.now().strftime('%d %B %Y')} | Total Students: {students.count()}",
            meta_style
        )
    )

    elements.append(Spacer(1, 20))

    data = [
        ["#", "Student Name", "College Name", "Phone Number", "Email"]
    ]

    for i, s in enumerate(students, 1):
        data.append([
            i,
            Paragraph(s.student_name, styles['BodyText']),
            Paragraph(s.college_name, styles['BodyText']),
            s.mobile_number or "N/A",
            Paragraph(s.user.email, styles['BodyText'])
        ])

    table = Table(
        data,
        colWidths=[1.2*cm, 4*cm, 5*cm, 3.5*cm, 5.5*cm]
    )

    table.setStyle(TableStyle([

        # Header
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F3C79E")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.black),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,0),10),

        # Grid
        ("LINEBELOW",(0,0),(-1,0),1,colors.grey),
        ("GRID",(0,1),(-1,-1),0.3,colors.lightgrey),

        # Alignment
        ("ALIGN",(0,0),(0,-1),"CENTER"),

        # Padding
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("RIGHTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),

        # Zebra rows
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.whitesmoke]),
    ]))

    elements.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)

        page_num = canvas.getPageNumber()

        canvas.drawCentredString(
            A4[0] / 2,
            1.5 * cm,
            f"Quiz Management System • Page {page_num}"
        )

        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')

    filename = "students_list.pdf"
    if selected_college:
        safe_college = selected_college.strip().lower().replace(" ", "_")
        filename = f"students_{safe_college}.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response

# ── Reports ──

@staff_required
def admin_reports(request):
    selected_quiz_attempt = request.GET.get('quiz_attempt', '')
    results = (
        QuizResult.objects
        .select_related('student', 'student__student_profile', 'quiz', 'attempt')
        .order_by('-attempt__started_at', '-completed_at')
    )

    if selected_quiz_attempt:
        try:
            quiz_id_str, attempt_date_str = selected_quiz_attempt.split('|', 1)
            attempt_date = date.fromisoformat(attempt_date_str)
            results = results.filter(
                quiz_id=int(quiz_id_str),
                attempt__started_at__date=attempt_date,
            )
        except (TypeError, ValueError):
            selected_quiz_attempt = ''

    raw_report_filters = (
        QuizResult.objects
        .annotate(attempt_date=TruncDate('attempt__started_at'))
        .values('quiz_id', 'quiz__title', 'attempt_date')
        .order_by('quiz__title', '-attempt_date')
        .distinct()
    )
    report_filters = [
        {
            'value': f"{item['quiz_id']}|{item['attempt_date'].isoformat()}",
            'quiz_title': item['quiz__title'],
            'attempt_date': item['attempt_date'],
        }
        for item in raw_report_filters
        if item['attempt_date']
    ]

    return render(request, 'admin_panel/reports.html', {
        'results': results,
        'report_filters': report_filters,
        'selected_quiz_attempt': selected_quiz_attempt,
    })
