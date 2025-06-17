import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from .models import QuizResult, VideoLesson, Question, Option, FinalCertificate, CertificateConfig
from django.contrib.auth.decorators import login_required
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




def home_view(request):
    return render(request, 'home.html')

@login_required(login_url='/users/login/')
def video_list(request):
    all_videos = VideoLesson.objects.all().order_by('id')
    completed_ids = QuizResult.objects.filter(user=request.user).values_list('video_id', flat=True)

    video_statuses = []
    for video in all_videos:
        attempted = video.id in completed_ids
        video_statuses.append({
            'video': video,
            'attempted': attempted
        })

    return render(request, 'videoquiz/video_list.html', {
        'video_statuses': video_statuses
    })




@login_required(login_url='/users/login/')
def video_quiz_page(request, video_id):
    video = get_object_or_404(VideoLesson, id=video_id)

    # Prevent reattempt
    if QuizResult.objects.filter(user=request.user, video=video).exists():
        return HttpResponse("❌ You have already completed this quiz.")

    # Determine if it's the last video
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
            "timestamp": q.timestamp,
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
    total_video_marks = video.total_marks

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

    scaled_score = (raw_score / total_question_marks) * total_video_marks
    percentage = (scaled_score / total_video_marks) * 100

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
        score=round(scaled_score, 2),
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







@login_required(login_url='/users/login/')
def certificate_list(request):
    user = request.user

    all_video_ids = set(VideoLesson.objects.values_list('id', flat=True))
    completed_video_ids = set(QuizResult.objects.filter(user=user).values_list('video_id', flat=True))

    if not completed_video_ids:  # User has not attempted any quiz
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
            'show_attempt_msg': True,
        })

    if all_video_ids != completed_video_ids:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
            'show_attempt_msg': False,
        })

    results = QuizResult.objects.filter(user=user)
    total_score = sum(r.score for r in results)
    total_possible = sum(r.video.total_marks for r in results)

    if total_possible == 0:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
            'show_attempt_msg': False,
        })

    percentage = (total_score / total_possible) * 100

    if percentage < 60:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': round(total_score, 2),
            'max_score': total_possible,
            'percentage': round(percentage, 2),
            'show_attempt_msg': False,
        })

    # Credit point logic
    if 60 <= percentage < 70:
        credit_point = 3
    elif 70 <= percentage < 80:
        credit_point = 4
    elif 80 <= percentage <= 90:
        credit_point = 5
    elif percentage > 90:
        credit_point = 6
    else:
        credit_point = 0

    latest_result = results.latest('timestamp')

    return render(request, 'certificate_list.html', {
        'final_certificate': {
            'user': user,
            'score': round(total_score, 2),
            'total_possible': total_possible,
            'percentage': round(percentage, 2),
            'credit_point': credit_point,
            'date': latest_result.timestamp,
            'certificate_title': "Final Certificate of Completion",
        },
        'result_id': latest_result.id
    })


    
    
    

@login_required(login_url='/users/login/')
def generate_final_certificate(request):
    user = request.user

    all_video_ids = set(VideoLesson.objects.values_list('id', flat=True))
    completed_video_ids = set(QuizResult.objects.filter(user=user).values_list('video_id', flat=True))

    if all_video_ids != completed_video_ids:
        return render(request, 'certificate_not_eligible.html', {
            'user': user,
            'score': 0,
            'max_score': 0,
            'percentage': 0,
        })

    results = QuizResult.objects.filter(user=user)
    total_score = sum(r.score for r in results)
    total_possible = sum(r.video.total_marks for r in results)

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

    # === Generate PDF and capture it ===
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

    # Paragraph text with bold name
    from textwrap import wrap

    normal_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    font_size = 14

    full_name = f"{user.first_name} {user.last_name}".strip() or user.username
    paragraph_text = (
        f"This is to certify that {full_name} has successfully completed the "
        f"'{campaign_name}' test, organized at {institution_name}, and is hereby awarded "
        f"{credit_point} credit points in recognition of this accomplishment."
    )

    max_text_width = width - 160  # 80 on each side (matches your border)
    char_width_estimate = 7  # avg char width at size 14
    wrap_width = int(max_text_width / char_width_estimate)
    wrapped_lines = wrap(paragraph_text, width=wrap_width)
    y_position = height - 180

    for line in wrapped_lines:
        if full_name in line:
            parts = line.split(full_name)
            total_line_width = (
                pdf.stringWidth(parts[0], normal_font, font_size)
                + pdf.stringWidth(full_name, bold_font, font_size)
                + pdf.stringWidth(parts[1], normal_font, font_size)
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

    # Save PDF
    filename = f"final_certificate_{user.username}.pdf"
    final_cert = FinalCertificate.objects.create(
        user=user,
        score=round(total_score, 2),
        total=total_possible,
        percentage=round(percentage, 2),
        credit_point=credit_point,
        certificate_file=ContentFile(buffer.getvalue(), name=filename),
    )

    for result in results:
        result.certificate_generated = True
        result.credit_point = credit_point
        result.save()

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

