import uuid

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Puzzle(models.Model):
    """One puzzle from the Lichess puzzle database (CC0). `fen` is the position before the opponent's move."""

    SIDES = [("white", "White"), ("black", "Black")]

    lichess_id = models.CharField(max_length=10, unique=True)
    fen = models.CharField(max_length=100)
    moves = ArrayField(models.CharField(max_length=5))  # UCI; the first move is the opponent's
    rating = models.IntegerField()
    rating_deviation = models.IntegerField()
    popularity = models.IntegerField()
    plays = models.IntegerField()
    themes = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    opening_tags = ArrayField(models.CharField(max_length=80), default=list, blank=True)
    game_url = models.URLField(blank=True)
    side = models.CharField(max_length=5, choices=SIDES)  # the learner's side
    start_fen = models.CharField(max_length=100)  # the position the learner sees, after the opponent's move
    is_active = models.BooleanField(default=True)
    imported_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["is_active", "rating"]), GinIndex(fields=["themes"])]

    def __str__(self):
        return f"{self.lichess_id} ({self.rating})"


class PuzzleAttempt(models.Model):
    """One puzzle served to a learner. The UUID is the idempotency key of its finish call."""

    MODES = [("rated", "Rated"), ("theme", "Theme")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="puzzle_attempts")
    puzzle = models.ForeignKey(Puzzle, on_delete=models.PROTECT, related_name="attempts")
    mode = models.CharField(max_length=5, choices=MODES)
    theme = models.CharField(max_length=30, blank=True)
    served_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    solved = models.BooleanField(null=True)
    rated = models.BooleanField(default=True)
    learner_rating_before = models.FloatField(null=True, blank=True)
    rating_after = models.FloatField(null=True, blank=True)
    rd_after = models.FloatField(null=True, blank=True)
    played = ArrayField(models.CharField(max_length=5), default=list, blank=True)
    hints = models.IntegerField(default=0)
    solution_shown = models.BooleanField(default=False)
    ms = models.IntegerField(default=0)
    result = models.JSONField(null=True, blank=True)  # the finish response, returned again on a repeat call

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "puzzle"], condition=Q(rated=True),
                                               name="one_rated_attempt_per_puzzle")]
        indexes = [models.Index(fields=["learner", "finished_at"])]


class PuzzleRating(models.Model):
    """Cache of the learner's Glicko-2 puzzle rating; the ordered rated attempts are the truth."""

    learner = models.OneToOneField("accounts.Learner", on_delete=models.CASCADE, primary_key=True,
                                   related_name="puzzle_rating")
    rating = models.FloatField()
    rd = models.FloatField()
    volatility = models.FloatField()
    rated_count = models.IntegerField(default=0)
    solved_count = models.IntegerField(default=0)
    last_rated_on = models.DateField(null=True, blank=True)  # the learner's local day


class PuzzleReport(models.Model):
    REASONS = [("wrong_solution", "Wrong solution"), ("other", "Other")]

    learner = models.ForeignKey("accounts.Learner", on_delete=models.CASCADE, related_name="puzzle_reports")
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=16, choices=REASONS)
    note = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["learner", "puzzle"], name="one_report_per_learner")]
