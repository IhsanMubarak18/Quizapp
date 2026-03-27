# video_app/forms.py
from django import forms
from .models import Question, Quiz


OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']
CORRECT_CHOICES = [(l, f'Option {l}') for l in OPTION_LETTERS]


class QuestionForm(forms.Form):
    """
    Custom form for Question that supports:
    - 2-6 dynamic answer options (option_a required, option_b required, option_c-f optional)
    - Multiple correct answers via checkboxes
    """
    question_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Enter question text..."}),
        label="Question"
    )
    option_a = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"placeholder": "Option A (required)"}))
    option_b = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"placeholder": "Option B (required)"}))
    option_c = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={"placeholder": "Option C"}))
    option_d = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={"placeholder": "Option D"}))
    option_e = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={"placeholder": "Option E"}))
    option_f = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={"placeholder": "Option F"}))

    correct_answers = forms.MultipleChoiceField(
        choices=CORRECT_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        label="Correct Answer(s)",
        help_text="Select one or more correct options."
    )

    def clean_correct_answers(self):
        answers = self.cleaned_data.get("correct_answers", [])
        if not answers:
            raise forms.ValidationError("Please select at least one correct answer.")
        return answers

    def clean(self):
        cleaned = super().clean()
        # Validate: selected correct answers must correspond to non-empty options
        answers = cleaned.get("correct_answers", [])
        option_vals = {
            'A': cleaned.get("option_a", "").strip(),
            'B': cleaned.get("option_b", "").strip(),
            'C': cleaned.get("option_c", "").strip(),
            'D': cleaned.get("option_d", "").strip(),
            'E': cleaned.get("option_e", "").strip(),
            'F': cleaned.get("option_f", "").strip(),
        }
        for ans in answers:
            if not option_vals.get(ans):
                self.add_error("correct_answers", f"Option {ans} is marked correct but its text is empty.")
        return cleaned

    def save(self, instance=None):
        """Save to a Question instance (create or update)."""
        from .models import Question
        data = self.cleaned_data
        if instance is None:
            instance = Question()
        instance.question_text = data["question_text"]
        instance.option_a = data["option_a"]
        instance.option_b = data["option_b"]
        instance.option_c = data.get("option_c", "") or ""
        instance.option_d = data.get("option_d", "") or ""
        instance.option_e = data.get("option_e", "") or ""
        instance.option_f = data.get("option_f", "") or ""
        instance.correct_answers = data["correct_answers"]
        instance.save()
        return instance

    @classmethod
    def from_instance(cls, instance, data=None):
        """Initialise form from an existing Question instance."""
        initial = {
            "question_text": instance.question_text,
            "option_a": instance.option_a,
            "option_b": instance.option_b,
            "option_c": instance.option_c,
            "option_d": instance.option_d,
            "option_e": instance.option_e,
            "option_f": instance.option_f,
            "correct_answers": instance.correct_answers or [],
        }
        return cls(data=data, initial=initial)


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'time_limit_minutes', 'shuffle_questions', 'max_attempts',
                  'is_active', 'certificate_min_percentage', 'start_time', 'end_time']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Quiz title'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Short description (optional)'}),
            'time_limit_minutes': forms.NumberInput(attrs={'min': 1, 'max': 300}),
            'max_attempts': forms.NumberInput(attrs={'min': 0, 'max': 100, 'placeholder': '0 for unlimited attempts'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
        labels = {
            'time_limit_minutes': 'Time Limit (minutes)',
            'shuffle_questions': 'Shuffle Questions',
            'is_active': 'Active (visible to students)',
            'certificate_min_percentage': 'Min % for Certificate (0 = all pass)',
            'start_time': 'Schedule Start (optional)',
            'end_time': 'Schedule End (optional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_time'].required = False
        self.fields['end_time'].required = False
        self.fields['description'].required = False


class RandomQuestionSelectForm(forms.Form):
    count = forms.IntegerField(min_value=1, label="Number of Random Questions",
                               widget=forms.NumberInput(attrs={'placeholder': 'e.g. 10'}))
