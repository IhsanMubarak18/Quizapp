# video_app/urls.py
from django.urls import path
from . import views

app_name = 'video_app'

urlpatterns = [
    # ── Home ──────────────────────────────────────────────────────
    path('', views.home_view, name='home'),

    # ── Student ───────────────────────────────────────────────────
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quiz/<int:quiz_id>/start/', views.start_quiz, name='start_quiz'),
    path('quiz/submit/<int:attempt_id>/', views.submit_quiz, name='submit_quiz'),
    path('quiz/result/<int:attempt_id>/', views.quiz_result, name='quiz_result'),
    path('quiz/certificate/<int:attempt_id>/', views.download_certificate, name='download_certificate'),

    # ── Admin Dashboard ────────────────────────────────────────────
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),

    # ── Question Bank ──────────────────────────────────────────────
    path('admin-panel/questions/', views.admin_question_bank, name='admin_question_bank'),
    path('admin-panel/questions/add/', views.admin_add_question, name='admin_add_question'),
    path('admin-panel/questions/<int:question_id>/edit/', views.admin_edit_question, name='admin_edit_question'),
    path('admin-panel/questions/<int:question_id>/delete/', views.admin_delete_question, name='admin_delete_question'),

    # ── Categories ────────────────────────────────────────────────────
    path('admin-panel/categories/', views.admin_categories, name='admin_categories'),
    path('admin-panel/categories/add/', views.admin_add_category, name='admin_add_category'),
    path('admin-panel/categories/<int:category_id>/edit/', views.admin_edit_category, name='admin_edit_category'),
    path('admin-panel/categories/<int:category_id>/delete/', views.admin_delete_category, name='admin_delete_category'),

    # ── Quiz Management ────────────────────────────────────────────
    path('admin-panel/quizzes/', views.admin_quizzes, name='admin_quizzes'),
    path('admin-panel/quizzes/add/', views.admin_add_quiz, name='admin_add_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/edit/', views.admin_edit_quiz, name='admin_edit_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/delete/', views.admin_delete_quiz, name='admin_delete_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/toggle/', views.admin_toggle_quiz, name='admin_toggle_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/questions/', views.admin_quiz_questions, name='admin_quiz_questions'),
    path('admin-panel/quizzes/<int:quiz_id>/questions/add/', views.admin_add_question_to_quiz, name='admin_add_question_to_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/questions/random/', views.admin_add_random_questions, name='admin_add_random_questions'),
    path('admin-panel/quizzes/<int:quiz_id>/questions/<int:question_id>/remove/', views.admin_remove_question_from_quiz, name='admin_remove_question_from_quiz'),
    path('admin-panel/quizzes/<int:quiz_id>/questions/<int:question_id>/edit/', views.admin_edit_quiz_question, name='admin_edit_quiz_question'),

    # ── Admin Users ────────────────────────────────────────────────
    path('admin-panel/admin-users/', views.admin_users, name='admin_users'),
    path('admin-panel/admin-users/add/', views.admin_add_user, name='admin_add_user'),
    path('admin-panel/admin-users/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-panel/admin-users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),


    # ── Students ───────────────────────────────────────────────────
    path('admin-panel/students/', views.admin_students, name='admin_students'),
    path('admin-panel/students/<int:user_id>/edit/', views.admin_edit_student, name='admin_edit_student'),
    path('admin-panel/students/<int:user_id>/delete/', views.admin_delete_student, name='admin_delete_student'),
    path('admin-panel/students/excel/', views.admin_students_excel, name='admin_students_excel'),

    # ── Reports ────────────────────────────────────────────────────
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),
]
