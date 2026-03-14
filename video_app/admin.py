# video_app/admin.py
from django.contrib import admin
from .models import Question, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, QuizResult

admin.site.register(Question)
admin.site.register(Quiz)
admin.site.register(QuizQuestion)
admin.site.register(QuizAttempt)
admin.site.register(StudentAnswer)
admin.site.register(QuizResult)
