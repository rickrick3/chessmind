from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .domain.areas import AREAS

AREA_CHOICES = [(a, a) for a in AREAS]
BASES = [("puzzle", "Puzzle"), ("lesson", "Lesson"), ("none", "None")]
CONFIDENCES = [("none", "None"), ("early", "Early"), ("reliable", "Reliable")]


class Evidence(models.Model):
    """The evidence ledger: one observation of one skill area. Append-only; deleted with the learner."""

    SOURCES = [("puzzle", "Puzzle"), ("lesson", "Lesson")]

    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="evidence")
    area = models.CharField(max_length=12, choices=AREA_CHOICES)
    source = models.CharField(max_length=7, choices=SOURCES)
    puzzle_attempt = models.ForeignKey("puzzles.PuzzleAttempt", null=True, blank=True, on_delete=models.CASCADE,
                                       related_name="evidence")
    step_result = models.ForeignKey("learning.StepResult", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="evidence")
    success = models.BooleanField()
    difficulty = models.IntegerField(null=True, blank=True)  # the puzzle's rating
    learner_rating = models.FloatField(null=True, blank=True)  # the learner's puzzle rating before the attempt
    tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    local_date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["puzzle_attempt", "area"], condition=Q(puzzle_attempt__isnull=False),
                                    name="one_area_per_puzzle_attempt"),
            models.UniqueConstraint(fields=["step_result", "area"], condition=Q(step_result__isnull=False),
                                    name="one_area_per_step_result"),
        ]
        indexes = [models.Index(fields=["learner", "area", "created_at"])]


class SkillEstimate(models.Model):
    """The current estimate for one skill area or one puzzle theme, recomputed from the ledger after each finish."""

    KINDS = [("area", "Area"), ("theme", "Theme")]

    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="skill_estimates")
    kind = models.CharField(max_length=5, choices=KINDS)
    key = models.CharField(max_length=30)
    basis = models.CharField(max_length=6, choices=BASES)
    value = models.FloatField(null=True, blank=True)
    low = models.IntegerField(null=True, blank=True)
    high = models.IntegerField(null=True, blank=True)
    observations = models.IntegerField(default=0)
    days = models.IntegerField(default=0)
    confidence = models.CharField(max_length=8, choices=CONFIDENCES)
    comparison = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=20, blank=True)
    repeated_mistake = models.BooleanField(default=False)  # for the coach; never shown to the learner
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "kind", "key"], name="one_estimate_per_key")]


class SkillHistory(models.Model):
    """One row per area per local day: the last estimate of that day, for progress charts later."""

    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="skill_history")
    key = models.CharField(max_length=12)
    local_date = models.DateField()
    basis = models.CharField(max_length=6, choices=BASES)
    value = models.FloatField(null=True, blank=True)
    low = models.IntegerField(null=True, blank=True)
    high = models.IntegerField(null=True, blank=True)
    confidence = models.CharField(max_length=8, choices=CONFIDENCES)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "key", "local_date"], name="one_history_per_day")]
