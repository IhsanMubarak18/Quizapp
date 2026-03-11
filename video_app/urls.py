from django.urls import path
from . import views

app_name = 'video_app'

urlpatterns = [
    # Public & User views
    path('', views.home_view, name='home'),
    path('video_list/', views.video_list, name='video_list'),
    path('lesson/<int:video_id>/', views.video_quiz_page, name='video_quiz_page'),
    path('api/questions/<int:video_id>/', views.questions_for_video, name='questions_for_video'),
    path('api/validate-answer/', views.validate_answer, name='validate_answer'),
    path('submit-quiz/', views.submit_quiz_result, name='submit_quiz_result'),
    path('final-certificate/', views.generate_final_certificate, name='generate_final_certificate'),
    path('verify-certificate/<int:user_id>/', views.verify_certificate, name='verify_certificate'),

    # Custom Admin Dashboard
    path('custom-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('custom-admin/videos/', views.admin_videos, name='admin_videos'),
    path('custom-admin/videos/add/', views.admin_add_video, name='admin_add_video'),
    path('custom-admin/videos/<int:video_id>/edit/', views.admin_edit_video, name='admin_edit_video'),
    path('custom-admin/videos/<int:video_id>/delete/', views.admin_delete_video, name='admin_delete_video'),
    path('custom-admin/videos/<int:video_id>/questions/', views.admin_questions, name='admin_questions'),
    path('custom-admin/videos/<int:video_id>/questions/add/', views.admin_add_question, name='admin_add_question'),
    path('custom-admin/questions/<int:question_id>/edit/', views.admin_edit_question, name='admin_edit_question'),
    path('custom-admin/questions/<int:question_id>/delete/', views.admin_delete_question, name='admin_delete_question'),
    path('custom-admin/certificate-config/', views.admin_certificate_config, name='admin_certificate_config'),
    path('custom-admin/users/', views.admin_users, name='admin_users'),
]
