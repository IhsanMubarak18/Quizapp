from django.contrib import admin
from .models import VideoLesson, Question, Option, CertificateConfig

class OptionInline(admin.TabularInline):
    model = Option
    extra = 2

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['question_text', 'mark']  # include mark

class QuestionAdmin(admin.ModelAdmin):
    inlines = [OptionInline]

class VideoLessonAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = ['title', 'order']
    fields = ['title', 'video_file', 'order']

@admin.register(CertificateConfig)
class CertificateConfigAdmin(admin.ModelAdmin):
    list_display = ['institution_name', 'campaign_name']



admin.site.register(VideoLesson, VideoLessonAdmin)
admin.site.register(Question, QuestionAdmin)


