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
    return render(request, 'student/quiz_list.html', {'quiz_data': quiz_data})


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

    # Enforce certificate minimum percentage threshold
    min_pct = attempt.quiz.certificate_min_percentage
    if result.percentage < min_pct:
        messages.error(request, f"Certificate not available. You need at least {min_pct:.0f}% to receive a certificate (your score: {result.percentage:.1f}%).")
        return redirect('video_app:quiz_result', attempt_id=attempt_id)

    student_profile = getattr(request.user, 'student_profile', None)
    student_name = student_profile.student_name if student_profile else request.user.get_full_name()
    college_name = student_profile.college_name if student_profile else ''

    # Generate PDF using ReportLab
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    buffer = io.BytesIO()
    page_size = landscape(A4)
    width, height = page_size
    pdf = canvas.Canvas(buffer, pagesize=page_size)

    # Background gradient-like (white)
    pdf.setFillColorRGB(0.98, 0.98, 1.0)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer gold border
    pdf.setStrokeColorRGB(0.72, 0.58, 0.12)
    pdf.setLineWidth(6)
    pdf.rect(25, 25, width - 50, height - 50, stroke=1, fill=0)

    # Inner border
    pdf.setStrokeColorRGB(0.72, 0.58, 0.12)
    pdf.setLineWidth(2)
    pdf.rect(38, 38, width - 76, height - 76, stroke=1, fill=0)

    # Title
    pdf.setFont("Helvetica-Bold", 38)
    pdf.setFillColorRGB(0.2, 0.2, 0.5)
    pdf.drawCentredString(width / 2, height - 100, "Certificate of Achievement")

    # Decorative line
    pdf.setStrokeColorRGB(0.72, 0.58, 0.12)
    pdf.setLineWidth(1.5)
    pdf.line(80, height - 115, width - 80, height - 115)

    # Subtitle
    pdf.setFont("Helvetica", 14)
    pdf.setFillColorRGB(0.4, 0.4, 0.4)
    pdf.drawCentredString(width / 2, height - 140, "This is to certify that")

    # Student Name
    pdf.setFont("Helvetica-Bold", 28)
    pdf.setFillColorRGB(0.1, 0.1, 0.4)
    pdf.drawCentredString(width / 2, height - 185, student_name)

    # Underline name
    name_width = pdf.stringWidth(student_name, "Helvetica-Bold", 28)
    pdf.setStrokeColorRGB(0.72, 0.58, 0.12)
    pdf.setLineWidth(1)
    pdf.line(width / 2 - name_width / 2, height - 190, width / 2 + name_width / 2, height - 190)

    if college_name:
        pdf.setFont("Helvetica", 13)
        pdf.setFillColorRGB(0.4, 0.4, 0.4)
        pdf.drawCentredString(width / 2, height - 215, f"from {college_name}")

    # Body text
    pdf.setFont("Helvetica", 14)
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    body = f"has successfully completed the quiz"
    pdf.drawCentredString(width / 2, height - 250, body)

    # Quiz Name
    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColorRGB(0.2, 0.2, 0.5)
    pdf.drawCentredString(width / 2, height - 285, f'"{result.quiz.title}"')

    # Score details
    pdf.setFont("Helvetica", 13)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    score_text = f"Score: {result.score} / {result.total_questions}   |   Percentage: {result.percentage:.1f}%   |   Grade: {result.grade}"
    pdf.drawCentredString(width / 2, height - 325, score_text)

    # Date
    date_str = result.completed_at.strftime("%d %B %Y")
    pdf.setFont("Helvetica", 12)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    pdf.drawCentredString(width / 2, height - 355, f"Date of Completion: {date_str}")

    # Bottom decorative line
    pdf.setStrokeColorRGB(0.72, 0.58, 0.12)
    pdf.setLineWidth(1.5)
    pdf.line(80, 100, width - 80, 100)

    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.6, 0.6, 0.6)
    pdf.drawCentredString(width / 2, 75, "Online Quiz Management System — Generated Certificate")

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
    return render(request, 'admin_panel/quiz_questions.html', {
        'quiz': quiz,
        'quiz_questions': quiz_questions,
        'available_questions': available_questions,
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
    """Download student list as PDF."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    import io

    selected_college = request.GET.get('college', '')
    students = filtered_students_queryset(college=selected_college).order_by('student_name')
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Professional background with subtle gradient effect
    pdf.setFillColorRGB(0.98, 0.98, 1.0)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Professional header background with gradient effect
    header_gradient_height = 140
    for i in range(header_gradient_height):
        color_intensity = 0.95 - (i * 0.0002)
        pdf.setFillColorRGB(color_intensity, color_intensity + 0.02, 1.0)
        pdf.rect(0, height - i, width, 1, fill=1, stroke=0)
    
    # Professional border
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(2)
    pdf.rect(20, 20, width - 40, height - 40, stroke=1, fill=0)
    
    # Inner decorative border
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(0.5)
    pdf.rect(30, 30, width - 60, height - 60, stroke=1, fill=0)
    
    # Header decorative line
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(1.5)
    pdf.line(50, height - 140, width - 50, height - 140)

    # Company/Institution Name (Header)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColorRGB(0.1, 0.2, 0.5)
    pdf.drawCentredString(width / 2, height - 30, "Quiz Management System")
    
    # Document type
    pdf.setFont("Helvetica-Oblique", 12)
    pdf.setFillColorRGB(0.4, 0.5, 0.7)
    pdf.drawCentredString(width / 2, height - 50, "Official Student Report")
    
    # Professional title with better typography
    pdf.setFont("Helvetica-Bold", 24)
    pdf.setFillColorRGB(0.1, 0.2, 0.5)
    title = f"Student List - {selected_college}" if selected_college else "Complete Student List"
    pdf.drawCentredString(width / 2, height - 90, title)
    
    # Subtitle with generation info
    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(0.5, 0.5, 0.6)
    pdf.drawCentredString(width / 2, height - 115, f"Generated on {timezone.now().strftime('%d %B %Y at %I:%M %p')}")
    
    # Student count badge with enhanced styling
    pdf.setFillColorRGB(0.9, 0.95, 1.0)
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(1.5)
    badge_width = 180
    badge_height = 30
    badge_x = (width - badge_width) / 2
    badge_y = height - 135
    pdf.roundRect(badge_x, badge_y, badge_width, badge_height, 8, fill=1, stroke=1)
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColorRGB(0.1, 0.2, 0.5)
    count_text = f"Total Students: {len(students)}"
    pdf.drawCentredString(width / 2, badge_y + 10, count_text)

    # Professional table header
    y = height - 180
    headers = ["#", "Student Name", "College Name", "Phone Number", "Email"]
    col_x = [40, 70, 230, 380, 460]
    col_widths = [30, 160, 150, 80, 100]
    
    # Table header background with gradient
    header_bg_height = 25
    for i in range(header_bg_height):
        color_intensity = 0.1 + (i * 0.002)
        pdf.setFillColorRGB(color_intensity, color_intensity + 0.1, 0.5)
        pdf.rect(40, y - 5 - i, width - 80, 1, fill=1, stroke=0)
    
    # Table header text
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColorRGB(1.0, 1.0, 1.0)
    for h, x in zip(headers, col_x):
        pdf.drawString(x, y, h)
    
    # Header underline
    pdf.setStrokeColorRGB(0.1, 0.2, 0.5)
    pdf.setLineWidth(2)
    pdf.line(40, y - 5, width - 40, y - 5)
    y -= 30

    # Table rows with alternating colors
    pdf.setFont("Helvetica", 9)
    row_count = 0
    for i, sp in enumerate(students, 1):
        if y < 100:  # New page when reaching bottom
            # Footer for current page
            pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
            pdf.setLineWidth(1)
            pdf.line(40, 70, width - 40, 70)
            
            # Footer background
            pdf.setFillColorRGB(0.95, 0.97, 1.0)
            pdf.rect(40, 20, width - 80, 50, fill=1, stroke=0)
            
            pdf.setFont("Helvetica-Oblique", 8)
            pdf.setFillColorRGB(0.5, 0.5, 0.6)
            pdf.drawCentredString(width / 2, 45, f"Page {pdf.getPageNumber()} - Student List")
            pdf.setFont("Helvetica-Oblique", 7)
            pdf.drawCentredString(width / 2, 30, "Confidential - For Internal Use Only")
            
            pdf.showPage()
            
            # New page setup with header
            # Background
            pdf.setFillColorRGB(0.98, 0.98, 1.0)
            pdf.rect(0, 0, width, height, fill=1, stroke=0)
            
            # Header gradient
            for i in range(header_gradient_height):
                color_intensity = 0.95 - (i * 0.0002)
                pdf.setFillColorRGB(color_intensity, color_intensity + 0.02, 1.0)
                pdf.rect(0, height - i, width, 1, fill=1, stroke=0)
            
            # Borders
            pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
            pdf.setLineWidth(2)
            pdf.rect(20, 20, width - 40, height - 40, stroke=1, fill=0)
            pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
            pdf.setLineWidth(0.5)
            pdf.rect(30, 30, width - 60, height - 60, stroke=1, fill=0)
            
            # Header content
            pdf.setFont("Helvetica-Bold", 16)
            pdf.setFillColorRGB(0.1, 0.2, 0.5)
            pdf.drawCentredString(width / 2, height - 30, "Quiz Management System")
            
            pdf.setFont("Helvetica-Oblique", 12)
            pdf.setFillColorRGB(0.4, 0.5, 0.7)
            pdf.drawCentredString(width / 2, height - 50, "Official Student Report")
            
            pdf.setFont("Helvetica-Bold", 20)
            pdf.setFillColorRGB(0.1, 0.2, 0.5)
            pdf.drawCentredString(width / 2, height - 85, title)
            
            # Header line
            pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
            pdf.setLineWidth(1.5)
            pdf.line(50, height - 100, width - 50, height - 100)
            
            # Table header on new page
            y = height - 130
            for i in range(header_bg_height):
                color_intensity = 0.1 + (i * 0.002)
                pdf.setFillColorRGB(color_intensity, color_intensity + 0.1, 0.5)
                pdf.rect(40, y - 5 - i, width - 80, 1, fill=1, stroke=0)
            
            pdf.setFont("Helvetica-Bold", 11)
            pdf.setFillColorRGB(1.0, 1.0, 1.0)
            for h, x in zip(headers, col_x):
                pdf.drawString(x, y, h)
            pdf.setStrokeColorRGB(0.1, 0.2, 0.5)
            pdf.setLineWidth(2)
            pdf.line(40, y - 5, width - 40, y - 5)
            y -= 30

        # Alternating row colors with subtle gradient
        if i % 2 == 0:
            pdf.setFillColorRGB(0.97, 0.97, 0.99)
            pdf.rect(40, y - 2, width - 80, 18, fill=1, stroke=0)
            # Add subtle row highlight
            pdf.setFillColorRGB(0.98, 0.98, 1.0)
            pdf.rect(40, y + 8, width - 80, 8, fill=1, stroke=0)
        
        # Row data with better styling
        pdf.setFont("Helvetica", 9)
        pdf.setFillColorRGB(0.1, 0.1, 0.1)
        
        # Truncate text with ellipsis if too long
        student_name = sp.student_name[:28] + "..." if len(sp.student_name) > 28 else sp.student_name
        college_name = sp.college_name[:22] + "..." if len(sp.college_name) > 22 else sp.college_name
        email = sp.user.email[:25] + "..." if len(sp.user.email) > 25 else sp.user.email
        
        # Row number with special styling
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColorRGB(0.2, 0.3, 0.6)
        pdf.drawString(col_x[0], y, str(i))
        
        # Other data
        pdf.setFont("Helvetica", 9)
        pdf.setFillColorRGB(0.1, 0.1, 0.1)
        row_data = [student_name, college_name, sp.mobile_number or "N/A", email]
        for val, x in zip(row_data, col_x[1:]):
            pdf.drawString(x, y, val)
        
        # Row separator line
        pdf.setStrokeColorRGB(0.8, 0.8, 0.85)
        pdf.setLineWidth(0.3)
        pdf.line(40, y - 3, width - 40, y - 3)
        y -= 18
        row_count += 1

    # Enhanced footer section
    footer_y = 80
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(1)
    pdf.line(40, footer_y + 10, width - 40, footer_y + 10)
    
    # Footer background
    pdf.setFillColorRGB(0.95, 0.97, 1.0)
    pdf.rect(40, 20, width - 80, 70, fill=1, stroke=0)
    
    # Footer border
    pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
    pdf.setLineWidth(0.5)
    pdf.rect(40, 20, width - 80, 70, stroke=1, fill=0)
    
    # Footer text
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.setFillColorRGB(0.5, 0.5, 0.6)
    pdf.drawCentredString(width / 2, footer_y, f"Generated by Quiz Management System - Page {pdf.getPageNumber()}")
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.setFillColorRGB(0.6, 0.6, 0.7)
    pdf.drawCentredString(width / 2, footer_y - 15, "Confidential - For Internal Use Only")
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.setFillColorRGB(0.6, 0.6, 0.7)
    pdf.drawCentredString(width / 2, footer_y - 30, f"Report ID: QMS-{timezone.now().strftime('%Y%m%d%H%M')}")
    
    # Enhanced summary box
    if len(students) > 0:
        # Summary background with gradient
        summary_y = footer_y - 45
        summary_width = 200
        summary_height = 25
        
        pdf.setFillColorRGB(0.1, 0.2, 0.5)
        pdf.roundRect(width - summary_width - 40, summary_y, summary_width, summary_height, 5, fill=1, stroke=0)
        
        pdf.setFillColorRGB(0.9, 0.95, 1.0)
        pdf.roundRect(width - summary_width - 38, summary_y + 2, summary_width - 4, summary_height - 4, 4, fill=1, stroke=0)
        
        pdf.setStrokeColorRGB(0.2, 0.3, 0.6)
        pdf.setLineWidth(1)
        pdf.roundRect(width - summary_width - 40, summary_y, summary_width, summary_height, 5, fill=0, stroke=1)
        
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColorRGB(0.1, 0.2, 0.5)
        pdf.drawString(width - summary_width - 35, summary_y + 8, f"Total Students: {len(students)}")
        pdf.setFont("Helvetica", 8)
        pdf.drawString(width - summary_width - 35, summary_y - 2, f"Rows: {row_count}")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = 'students_list.pdf'
    if selected_college:
        safe_college = selected_college.strip().lower().replace(' ', '_')
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
