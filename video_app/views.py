import json
from textwrap import wrap
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from .models import QuizResult, VideoLesson, Question, Option, FinalCertificate, CertificateConfig
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import VideoLessonForm, QuestionForm, OptionForm, CertificateConfigForm
import qrcode
from io import BytesIO
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.units import inch
from django.urls import reverse
from django.db.models import Max
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from reportlab.lib.utils import ImageReader
from django.contrib.auth import get_user_model
from django.forms import modelformset_factory


def staff_required(view_func):
    """Decorator: redirect non-staff users to admin login."""
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/admin-login/'
    )(view_func)
    return decorated



def home_view(request):
    return render(request, 'home.html')

@login_required(login_url='/users/login/')
def video_list(request):
    all_videos = VideoLesson.objects.all().order_by('id')

    # Get latest quiz result per video
    latest_results = []
    completed_video_ids = set()

    for video in all_videos:
        latest_result = QuizResult.objects.filter(user=request.user, video=video).order_by('-id').first()
        if latest_result:
            latest_results.append(latest_result)
            completed_video_ids.add(video.id)

    # Show generate button only if all videos have been completed
    all_video_ids = set(all_videos.values_list('id', flat=True))
    show_generate_button = (completed_video_ids == all_video_ids)

    return render(request, 'videoquiz/video_list.html', {
        'all_videos': all_videos,
        'quiz_results': latest_results,
        'show_generate_button': show_generate_button,
    })




@login_required(login_url='/users/login/')
def video_quiz_page(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)

    # ✅ Allow multiple attempts — no restriction
    all_videos = VideoLesson.objects.all().order_by('id')
    is_last_video = video == all_videos.last()

    return render(request, 'videoquiz/video_quiz.html', {
        'video': video,
        'is_last_video': is_last_video
    })





@login_required(login_url='/users/login/')
def questions_for_video(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)
    data = []
    for q in video.questions.all():
        data.append({
            "id": q.id,
            #"timestamp": q.timestamp,
            "text": q.question_text,
            "options": [{"id": opt.id, "text": opt.text} for opt in q.options.all()]
        })
    return JsonResponse(data, safe=False)



@csrf_exempt
@login_required(login_url='/users/login/')
def validate_answer(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            question = Question.objects.get(id=data['question_id'])
            option = Option.objects.get(id=data['selected_option_id'], question=question)
            return JsonResponse({"correct": option.is_correct})
        except (Question.DoesNotExist, Option.DoesNotExist):
            return JsonResponse({"error": "Invalid question or option"}, status=400)
        
        



@csrf_exempt
@login_required(login_url='/users/login/')
def submit_quiz_result(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    data = json.loads(request.body)
    video_id = data.get("video_id")
    answers = data.get("answers")  # ✅ list of dicts: {question_id, selected_option_id}

    if not video_id or not answers:
        return JsonResponse({"error": "Invalid data"}, status=400)

    video = get_object_or_404(VideoLesson, id=video_id)
    total_video_marks = video.get_total_mark

    raw_score = 0
    total_question_marks = 0

    for ans in answers:
        try:
            question = Question.objects.get(id=ans['question_id'], video=video)
            option = Option.objects.get(id=ans['selected_option_id'], question=question)
            mark = getattr(question, 'mark', 1)
            total_question_marks += mark
            if option.is_correct:
                raw_score += mark
        except (Question.DoesNotExist, Option.DoesNotExist):
            continue

    if total_question_marks == 0:
        return JsonResponse({"error": "No valid questions found."}, status=400)

    #scaled_score = (raw_score / total_question_marks) * total_video_marks
    percentage = (raw_score / total_video_marks) * 100

    # ✅ Calculate credit point based on percentage
    if percentage >= 91:
        credit_point = 6
    elif percentage >= 80:
        credit_point = 5
    elif percentage >= 70:
        credit_point = 4
    elif percentage >= 60:
        credit_point = 3
    else:
        credit_point = 0

    result = QuizResult.objects.create(
        user=request.user,
        video=video,
        score=round(raw_score, 2),
        total_questions=len(answers),
        percentage=round(percentage, 2),
        credit_point=credit_point,
        certificate_generated=False
    )

    # ✅ Check if all videos are completed
    all_video_ids = set(VideoLesson.objects.values_list('id', flat=True))
    completed_video_ids = set(
        QuizResult.objects.filter(user=request.user).values_list('video_id', flat=True)
    )

    if all_video_ids == completed_video_ids:
        return JsonResponse({
            "message": "All quizzes completed",
            "certificate_url": f"/certificate/{result.id}/"
        })

    return JsonResponse({
        "message": "Quiz submitted successfully",
        "next_video": True
    })



def verify_certificate(request, user_id):
    user = get_object_or_404(User, id=user_id)
    certificate = FinalCertificate.objects.filter(user=user).last()

    if certificate:
        return render(request, 'certificate_verification.html', {
            'user': user,
            'certificate': certificate
        })
    else:
        return HttpResponse("<h2>Certificate Not Found</h2><p>No certificate is available for this user.</p>", status=404)







# @login_required(login_url='/users/login/')
# def certificate_list(request):
#     user = request.user

#     all_videos = VideoLesson.objects.all()
#     all_video_ids = set(all_videos.values_list('id', flat=True))

#     # Collect latest attempt per video
#     latest_results = []
#     completed_video_ids = set()

#     for video in all_videos:
#         latest_result = QuizResult.objects.filter(user=user, video=video).order_by('-id').first()
#         if latest_result:
#             latest_results.append(latest_result)
#             completed_video_ids.add(video.id)

#     if not completed_video_ids:  # No attempts at all
#         return render(request, 'certificate_not_eligible.html', {
#             'user': user,
#             'score': 0,
#             'max_score': 0,
#             'percentage': 0,
#             'show_attempt_msg': True,
#         })

#     if all_video_ids != completed_video_ids:  # Some videos are not attempted
#         return render(request, 'certificate_not_eligible.html', {
#             'user': user,
#             'score': 0,
#             'max_score': 0,
#             'percentage': 0,
#             'show_attempt_msg': False,
#         })

#     total_score = sum(r.score for r in latest_results)
#     total_possible = sum(r.video.total_marks for r in latest_results)

#     if total_possible == 0:
#         return render(request, 'certificate_not_eligible.html', {
#             'user': user,
#             'score': 0,
#             'max_score': 0,
#             'percentage': 0,
#             'show_attempt_msg': False,
#         })

#     percentage = (total_score / total_possible) * 100

#     if percentage < 60:
#         return render(request, 'certificate_not_eligible.html', {
#             'user': user,
#             'score': round(total_score, 2),
#             'max_score': total_possible,
#             'percentage': round(percentage, 2),
#             'show_attempt_msg': False,
#         })

#     # Credit point logic
#     if 60 <= percentage < 70:
#         credit_point = 3
#     elif 70 <= percentage < 80:
#         credit_point = 4
#     elif 80 <= percentage <= 90:
#         credit_point = 5
#     else:  # > 90%
#         credit_point = 6

#     # Latest quiz timestamp from any of the latest results
#     latest_result = max(latest_results, key=lambda r: r.timestamp)

#     return render(request, 'certificate_list.html', {
#         'final_certificate': {
#             'user': user,
#             'score': round(total_score, 2),
#             'total_possible': total_possible,
#             'percentage': round(percentage, 2),
#             'credit_point': credit_point,
#             'date': latest_result.timestamp,
#             'certificate_title': "Final Certificate of Completion",
#         },
#         'result_id': latest_result.id
#     })


    
    
    

@login_required(login_url='/users/login/')
def generate_final_certificate(request):
    user = request.user

    all_videos = VideoLesson.objects.all()
    all_video_ids = set(all_videos.values_list('id', flat=True))

    # Get latest quiz result for each video
    latest_results = []
    completed_video_ids = set()

    for video in all_videos:
        latest_result = QuizResult.objects.filter(user=user, video=video).order_by('-id').first()
        if latest_result:
            latest_results.append(latest_result)
            completed_video_ids.add(video.id)

    # Check completion
    if all_video_ids != completed_video_ids:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
        })

    total_score = sum(r.score for r in latest_results)
    total_possible = sum(r.video.get_total_mark for r in latest_results)

    if total_possible == 0:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
        })

    percentage = (total_score / total_possible) * 100

    if percentage < 60:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': round(total_score, 2),
            'max_score': total_possible,
            'percentage': round(percentage, 2),
        })

    # Assign credit point
    if 60 <= percentage < 70:
        credit_point = 3
    elif 70 <= percentage < 80:
        credit_point = 4
    elif 80 <= percentage <= 90:
        credit_point = 5
    else:
        credit_point = 6

    # Remove previously generated certificate for same user (optional)
    FinalCertificate.objects.filter(user=user).delete()

    # === Generate Certificate PDF ===
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    config = CertificateConfig.objects.first()
    institution_name = config.institution_name if config else "Your Institution"
    campaign_name = config.campaign_name if config else "the program"

    # Border
    pdf.setStrokeColorRGB(0.2, 0.2, 0.2)
    pdf.setLineWidth(4)
    pdf.rect(40, 40, width - 80, height - 80)

    # Decorative lines
    pdf.setStrokeColorRGB(0.6, 0.6, 0.6)
    pdf.setLineWidth(1)
    pdf.line(60, height - 130, width - 60, height - 130)
    pdf.line(60, height - 135, width - 60, height - 135)

    # Title
    pdf.setFont("Helvetica-Bold", 32)
    pdf.drawCentredString(width / 2, height - 100, "Certificate of Achievement")

    # Certificate paragraph
    normal_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    font_size = 14

    full_name = f"{user.first_name} {user.last_name}".strip() or user.email
    paragraph_text = (
        f"This is to certify that {full_name} has successfully completed the "
        f"'{campaign_name}' test, organized at {institution_name}, and is hereby awarded "
        f"{credit_point} credit points in recognition of this accomplishment."
    )

    max_text_width = width - 160
    char_width_estimate = 7
    wrap_width = int(max_text_width / char_width_estimate)
    wrapped_lines = wrap(paragraph_text, width=wrap_width)
    y_position = height - 180

    for line in wrapped_lines:
        if full_name in line:
            parts = line.split(full_name)
            total_line_width = (
                pdf.stringWidth(parts[0], normal_font, font_size) +
                pdf.stringWidth(full_name, bold_font, font_size) +
                pdf.stringWidth(parts[1], normal_font, font_size)
            )
            x_start = (width - total_line_width) / 2

            pdf.setFont(normal_font, font_size)
            pdf.drawString(x_start, y_position, parts[0])
            x_current = x_start + pdf.stringWidth(parts[0], normal_font, font_size)

            pdf.setFont(bold_font, font_size)
            pdf.drawString(x_current, y_position, full_name)
            x_current += pdf.stringWidth(full_name, bold_font, font_size)

            pdf.setFont(normal_font, font_size)
            pdf.drawString(x_current, y_position, parts[1])
        else:
            pdf.setFont(normal_font, font_size)
            pdf.drawCentredString(width / 2, y_position, line)
        y_position -= 20

    # QR Code
    current_site = Site.objects.get_current()
    verification_url = f"https://{current_site.domain}" + reverse('video_app:verify_certificate', args=[user.id])
    qr_img = qrcode.make(verification_url)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    qr_reader = ImageReader(qr_buffer)
    pdf.drawImage(qr_reader, inch, inch, width=80, height=80)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    # Save PDF to model
    filename = f"final_certificate_{user.email}.pdf"
    FinalCertificate.objects.create(
        user=user,
        score=round(total_score, 2),
        total=total_possible,
        percentage=round(percentage, 2),
        credit_point=credit_point,
        certificate_file=ContentFile(buffer.getvalue(), name=filename),
    )

    # Mark quiz results as used
    for result in latest_results:
        result.certificate_generated = True
        result.credit_point = credit_point
        result.save()

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─────────────────────────────────────────────
# CUSTOM ADMIN DASHBOARD VIEWS
# ─────────────────────────────────────────────

AuthUser = get_user_model()

@staff_required
def admin_dashboard(request):
    total_videos = VideoLesson.objects.count()
    total_questions = Question.objects.count()
    total_users = AuthUser.objects.filter(is_staff=False).count()
    total_results = QuizResult.objects.count()
    recent_results = QuizResult.objects.select_related('user', 'video').order_by('-id')[:8]
    return render(request, 'admin/dashboard.html', {
        'total_videos': total_videos,
        'total_questions': total_questions,
        'total_users': total_users,
        'total_results': total_results,
        'recent_results': recent_results,
    })


@staff_required
def admin_videos(request):
    videos = VideoLesson.objects.all().order_by('order')
    return render(request, 'admin/videos.html', {'videos': videos})


@staff_required
def admin_add_video(request):
    if request.method == 'POST':
        form = VideoLessonForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('video_app:admin_videos')
    else:
        form = VideoLessonForm()
    return render(request, 'admin/add_video.html', {'form': form})


@staff_required
def admin_edit_video(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)
    if request.method == 'POST':
        form = VideoLessonForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            return redirect('video_app:admin_videos')
    else:
        form = VideoLessonForm(instance=video)
    return render(request, 'admin/edit_video.html', {'form': form, 'video': video})


@staff_required
def admin_delete_video(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)
    if request.method == 'POST':
        video.delete()
        return redirect('video_app:admin_videos')
    return render(request, 'admin/delete_confirm.html', {
        'object_name': video.title,
        'cancel_url': 'admin_videos',
        'object_type': 'Video',
    })


@staff_required
def admin_questions(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)
    questions = video.questions.prefetch_related('options').all()
    return render(request, 'admin/questions.html', {'video': video, 'questions': questions})


@staff_required
def admin_add_question(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)
    OptionFormSet = modelformset_factory(Option, form=OptionForm, extra=4, max_num=4)

    if request.method == 'POST':
        q_form = QuestionForm(request.POST)
        opt_formset = OptionFormSet(request.POST, queryset=Option.objects.none(), prefix='options')
        if q_form.is_valid() and opt_formset.is_valid():
            question = q_form.save(commit=False)
            question.video = video
            question.save()
            for opt_form in opt_formset:
                if opt_form.cleaned_data.get('text'):
                    opt = opt_form.save(commit=False)
                    opt.question = question
                    opt.save()
            return redirect('video_app:admin_questions', video_id=video.id)
    else:
        q_form = QuestionForm()
        opt_formset = OptionFormSet(queryset=Option.objects.none(), prefix='options')

    return render(request, 'admin/add_question.html', {
        'video': video, 'q_form': q_form, 'opt_formset': opt_formset,
    })


@staff_required
def admin_edit_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    OptionFormSet = modelformset_factory(Option, form=OptionForm, extra=0)

    if request.method == 'POST':
        q_form = QuestionForm(request.POST, instance=question)
        opt_formset = OptionFormSet(request.POST, queryset=question.options.all(), prefix='options')
        if q_form.is_valid() and opt_formset.is_valid():
            q_form.save()
            for opt_form in opt_formset:
                if opt_form.cleaned_data.get('text'):
                    opt = opt_form.save(commit=False)
                    opt.question = question
                    opt.save()
                elif opt_form.instance.pk and not opt_form.cleaned_data.get('text'):
                    opt_form.instance.delete()
            return redirect('video_app:admin_questions', video_id=question.video.id)
    else:
        q_form = QuestionForm(instance=question)
        opt_formset = OptionFormSet(queryset=question.options.all(), prefix='options')

    return render(request, 'admin/edit_question.html', {
        'question': question, 'q_form': q_form, 'opt_formset': opt_formset,
    })


@staff_required
def admin_delete_question(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    video_id = question.video.id
    if request.method == 'POST':
        question.delete()
        return redirect('video_app:admin_questions', video_id=video_id)
    return render(request, 'admin/delete_confirm.html', {
        'object_name': f'Question #{question.id}',
        'cancel_url': 'admin_questions',
        'cancel_arg': video_id,
        'object_type': 'Question',
    })


@staff_required
def admin_certificate_config(request):
    config = CertificateConfig.objects.first()
    if request.method == 'POST':
        form = CertificateConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            return redirect('video_app:admin_dashboard')
    else:
        form = CertificateConfigForm(instance=config)
    return render(request, 'admin/certificate_config.html', {'form': form, 'config': config})


@staff_required
def admin_users(request):
    users = AuthUser.objects.filter(is_staff=False).order_by('-date_joined')
    user_data = []
    for u in users:
        results = QuizResult.objects.filter(user=u)
        user_data.append({
            'user': u,
            'quizzes_taken': results.count(),
            'latest_result': results.order_by('-id').first(),
        })
    return render(request, 'admin/users.html', {'user_data': user_data})
