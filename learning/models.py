import uuid

from django.db import models
from django.utils import timezone


class LessonAttempt(models.Model):
    """One run through a lesson, pinned to the version it started on. The UUID is the idempotency key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="attempts")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.CASCADE, related_name="attempts")
    version = models.ForeignKey("curriculum.LessonVersion", on_delete=models.PROTECT, related_name="attempts")
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(null=True)
    accuracy = models.FloatField(null=True)
    xp_awarded = models.IntegerField(default=0)
    result = models.JSONField(null=True, blank=True)  # the finish response, returned again on a repeat call


class StepResult(models.Model):
    """How one scored step went: raw learning data for weakness detection later."""

    attempt = models.ForeignKey(LessonAttempt, on_delete=models.CASCADE, related_name="steps")
    step_id = models.CharField(max_length=20)
    step_type = models.CharField(max_length=12)
    correct = models.BooleanField()
    cleared = models.BooleanField()
    tries = models.JSONField(default=list)
    hints = models.JSONField(default=int)  # int, or one int per learner move in a play_line
    ms = models.IntegerField(default=0)
    skills = models.JSONField(default=list)


class LessonProgress(models.Model):
    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="progress")
    lesson = models.ForeignKey("curriculum.Lesson", on_delete=models.CASCADE, related_name="progress")
    first_completed_at = models.DateTimeField(null=True, blank=True)
    best_accuracy = models.FloatField(default=0.0)
    completions = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "lesson"], name="one_progress_per_lesson")]
