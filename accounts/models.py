from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.utils import timezone as dj_timezone


def default_daily_goal() -> int:
    return settings.DAILY_GOAL_DEFAULT


class Learner(models.Model):
    """One person learning on ChessMind: a guest (no user) or an account holder."""

    LANGUAGES = [("fr", "Français"), ("en", "English")]
    START_LEVELS = [("new", "New to chess"), ("rules", "Knows the rules"), ("club", "Club player")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="learner")
    player = models.ForeignKey("players.Player", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="learners")
    display_name = models.CharField(max_length=40, blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGES, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    daily_goal_xp = models.PositiveSmallIntegerField(default=default_daily_goal)
    start_level = models.CharField(max_length=5, choices=START_LEVELS, blank=True)
    # Caches of the XP ledger, kept in step by gamification in the same transaction.
    xp_total = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=dj_timezone.now)

    @property
    def is_guest(self) -> bool:
        return self.user_id is None

    def local_date(self, now: datetime) -> date:
        return now.astimezone(ZoneInfo(self.timezone or "UTC")).date()

    def __str__(self):
        return self.user.email if self.user_id else f"guest {self.pk}"
