from django import forms
from .models import VideoLesson, Question, Option, CertificateConfig


class VideoLessonForm(forms.ModelForm):
    class Meta:
        model = VideoLesson
        fields = ['title', 'video_file', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Video title'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Display order'}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['question_text', 'mark']
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter question...'}),
            'mark': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5', 'min': '0.5'}),
        }


class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Option text'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class CertificateConfigForm(forms.ModelForm):
    class Meta:
        model = CertificateConfig
        fields = ['institution_name', 'campaign_name']
        widgets = {
            'institution_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Institution Name'}),
            'campaign_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Campaign / Program Name'}),
        }
