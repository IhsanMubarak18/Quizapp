from django.urls import path
from . import views

app_name = 'video_app'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('video_list/', views.video_list, name='video_list'),
    path('lesson/<int:video_id>/', views.video_quiz_page, name='video_quiz_page'),
    path('api/questions/<int:video_id>/', views.questions_for_video, name='questions_for_video'),
    path('api/validate-answer/', views.validate_answer, name='validate_answer'),
    path('submit-quiz/', views.submit_quiz_result, name='submit_quiz_result'),
    #path('certificates/', views.certificate_list, name='certificate_list'),
    path('final-certificate/', views.generate_final_certificate, name='generate_final_certificate'),
    path('verify-certificate/<int:user_id>/', views.verify_certificate, name='verify_certificate')

]
