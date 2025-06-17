from django.db import models
from django.contrib.auth.models import User

class VideoLesson(models.Model):
    title = models.CharField(max_length=200)
    video_file = models.FileField(upload_to='videos/')
    order = models.PositiveIntegerField(default=1)
    total_marks = models.PositiveIntegerField(default=20)
    

    def __str__(self):
        return self.title



class Question(models.Model):
    video = models.ForeignKey(VideoLesson, related_name='questions', on_delete=models.CASCADE)
    question_text = models.TextField()
    timestamp = models.FloatField()
    mark = models.FloatField(default=1)  # mark per question (optional if all are equal)

    def __str__(self):
        return f"Question of {self.video.title} at {self.timestamp}s"


class Option(models.Model):
    question = models.ForeignKey(Question, related_name="options", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Wrong'})"
    
    
class QuizResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(VideoLesson, on_delete=models.CASCADE)
    score = models.FloatField()
    total_questions = models.IntegerField()
    percentage = models.FloatField()
    credit_point = models.IntegerField(default=0)  # Add this if not present
    certificate_generated = models.BooleanField(default=False)
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)  # New optional field
    timestamp = models.DateTimeField(auto_now_add=True)


class FinalCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField()
    total = models.FloatField()
    percentage = models.FloatField()
    credit_point = models.IntegerField()
    certificate_file = models.FileField(upload_to='certificates/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.percentage}% - {self.created_at.date()}"
    
    
class CertificateConfig(models.Model):
    institution_name = models.CharField(max_length=255, default="Your Institution Name")
    campaign_name = models.CharField(max_length=255, default="Your Campaign Name")

    def __str__(self):
        return f"{self.institution_name} - {self.campaign_name}"