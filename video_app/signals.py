from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from users.models import StudentProfile

from .models import Question, Quiz, QuizAttempt, QuizQuestion, QuizResult
from .selectors import COLLEGE_OPTIONS_CACHE_KEY, DASHBOARD_STATS_CACHE_KEY

AuthUser = get_user_model()


def invalidate_shared_caches():
    cache.delete_many([
        DASHBOARD_STATS_CACHE_KEY,
        COLLEGE_OPTIONS_CACHE_KEY,
    ])


@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
@receiver(post_save, sender=Quiz)
@receiver(post_delete, sender=Quiz)
@receiver(post_save, sender=QuizQuestion)
@receiver(post_delete, sender=QuizQuestion)
@receiver(post_save, sender=QuizAttempt)
@receiver(post_delete, sender=QuizAttempt)
@receiver(post_save, sender=QuizResult)
@receiver(post_delete, sender=QuizResult)
@receiver(post_save, sender=StudentProfile)
@receiver(post_delete, sender=StudentProfile)
@receiver(post_save, sender=AuthUser)
@receiver(post_delete, sender=AuthUser)
def clear_performance_caches(**kwargs):
    invalidate_shared_caches()
