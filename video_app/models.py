from django.db import models
from django.conf import settings
from django.utils import timezone


class Question(models.Model):
    """Global question bank - supports 2-6 answer options and multiple correct answers."""
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500, blank=True, default='')
    option_d = models.CharField(max_length=500, blank=True, default='')
    option_e = models.CharField(max_length=500, blank=True, default='')
    option_f = models.CharField(max_length=500, blank=True, default='')
    # List of correct option letters e.g. ["A"] or ["A", "C"]
    correct_answers = models.JSONField(default=list, help_text="List of correct option letters, e.g. [\"A\", \"C\"]")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question_text[:80]

    def get_options(self):
        """Return list of (letter, text) tuples for all non-empty options."""
        pairs = [
            ('A', self.option_a),
            ('B', self.option_b),
            ('C', self.option_c),
            ('D', self.option_d),
            ('E', self.option_e),
            ('F', self.option_f),
        ]
        return [(letter, text) for letter, text in pairs if text.strip()]

    def is_answer_correct(self, selected):
        """Return True if the selected letter is in the correct_answers list."""
        if not selected:
            return False
        return selected.upper() in [a.upper() for a in (self.correct_answers or [])]


class Quiz(models.Model):
    """A quiz created by admin."""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(default=30, help_text="Time limit in minutes")
    shuffle_questions = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(null=True, blank=True, help_text="Leave blank for no schedule")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Leave blank for no schedule")
    certificate_min_percentage = models.FloatField(default=60.0, help_text="Minimum % score required to download certificate")
    created_at = models.DateTimeField(auto_now_add=True)
    questions = models.ManyToManyField(Question, through='QuizQuestion', blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['start_time']),
            models.Index(fields=['end_time']),
        ]

    def __str__(self):
        return self.title

    def is_available(self):
        now = timezone.now()
        # If a schedule is set, availability is driven purely by time
        if self.start_time or self.end_time:
            if self.start_time and now < self.start_time:
                return False  # not started yet
            if self.end_time and now > self.end_time:
                return False  # already ended
            return True       # within the scheduled window
        # No schedule — use the manual is_active flag
        return self.is_active

    @property
    def schedule_status(self):
        """Rich status string for admin display."""
        now = timezone.now()
        if self.start_time or self.end_time:
            if self.start_time and now < self.start_time:
                return 'scheduled'   # upcoming
            if self.end_time and now > self.end_time:
                return 'ended'       # finished
            return 'live'            # currently running
        return 'active' if self.is_active else 'inactive'

    def total_questions(self):
        return self.quizquestion_set.count()


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'question')

    def __str__(self):
        return f"{self.quiz.title} → Q{self.order}"


class QuizAttempt(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_submitted = models.BooleanField(default=False)
    question_order = models.JSONField(default=list)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'is_submitted']),
            models.Index(fields=['quiz', 'is_submitted']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"{self.student.email} → {self.quiz.title}"

    def time_remaining_seconds(self):
        if self.is_submitted:
            return 0
        elapsed = (timezone.now() - self.started_at).total_seconds()
        limit = self.quiz.time_limit_minutes * 60
        return max(0, int(limit - elapsed))


class StudentAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    # For single-correct: list with one element e.g. ["A"]
    # For multi-correct:  list with multiple elements e.g. ["A", "C"]
    selected_answers = models.JSONField(default=list)

    class Meta:
        unique_together = ('attempt', 'question')

    @property
    def selected_answer(self):
        """Backwards-compat: return first selected answer or None (for display)."""
        return self.selected_answers[0] if self.selected_answers else None

    @property
    def is_correct(self):
        correct = set(a.upper() for a in (self.question.correct_answers or []))
        selected = set(a.upper() for a in (self.selected_answers or []))
        return selected == correct and len(selected) > 0


class QuizResult(models.Model):
    attempt = models.OneToOneField(QuizAttempt, on_delete=models.CASCADE, related_name='result')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_results')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='results')
    score = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'completed_at']),
            models.Index(fields=['quiz', 'completed_at']),
        ]

    def __str__(self):
        return f"{self.student.email} | {self.quiz.title} | {self.percentage:.1f}%"

    @property
    def grade(self):
        if self.percentage >= 90: return 'A+'
        elif self.percentage >= 80: return 'A'
        elif self.percentage >= 70: return 'B'
        elif self.percentage >= 60: return 'C'
        else: return 'F'
