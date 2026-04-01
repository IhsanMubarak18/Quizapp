# video_app/admin.py
from django.contrib import admin
from .models import Category, Question, Quiz, QuizQuestion, QuizAttempt, StudentAnswer, QuizResult


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'question_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'question_count')
    ordering = ('name',)
    
    def question_count(self, obj):
        return obj.question_count()
    question_count.short_description = 'Questions'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text_preview', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('question_text', 'category__name')
    list_select_related = ('category',)
    ordering = ('-created_at',)
    
    def question_text_preview(self, obj):
        return obj.question_text[:100] + '...' if len(obj.question_text) > 100 else obj.question_text
    question_text_preview.short_description = 'Question'


admin.site.register(Quiz)
admin.site.register(QuizQuestion)
admin.site.register(QuizAttempt)
admin.site.register(StudentAnswer)
admin.site.register(QuizResult)
