from django.db import models
from django.db.models import Q


class XpEvent(models.Model):
    """The XP ledger: the source of truth. Learner.xp_total and the streak fields are caches of it."""

    REASONS = [("lesson_first", "First completion"), ("accuracy_bonus", "Accuracy bonus"),
               ("lesson_replay", "Replay"), ("review", "Review card"), ("puzzle", "Puzzle")]

    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="xp_events")
    amount = models.IntegerField()
    reason = models.CharField(max_length=20, choices=REASONS)
    lesson = models.ForeignKey("curriculum.Lesson", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    attempt = models.ForeignKey("learning.LessonAttempt", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="xp_events")
    puzzle_attempt = models.ForeignKey("puzzles.PuzzleAttempt", null=True, blank=True, on_delete=models.CASCADE,
                                       related_name="xp_events")
    local_date = models.DateField()  # the learner's own day when it was earned
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "reason"], condition=Q(attempt__isnull=False),
                                               name="one_reason_per_attempt"),
                       models.UniqueConstraint(fields=["puzzle_attempt", "reason"],
                                               condition=Q(puzzle_attempt__isnull=False),
                                               name="one_reason_per_puzzle_attempt")]
        indexes = [models.Index(fields=["learner", "local_date"])]


class LearnerAchievement(models.Model):
    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="achievements")
    code = models.CharField(max_length=30)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "code"], name="one_achievement_per_code")]
