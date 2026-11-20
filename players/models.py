from django.db import models


class Player(models.Model):
    chesscom_username = models.CharField(max_length=50, unique=True)
    language = models.CharField(max_length=2, choices=[("fr", "Français"), ("en", "English")], default="en")
    rating = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.chesscom_username = self.chesscom_username.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.chesscom_username


class UsageCounter(models.Model):
    """How much of the weekly free allowance a player has used (ISO week, UTC)."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    iso_year = models.IntegerField()
    iso_week = models.IntegerField()
    reviews_used = models.IntegerField(default=0)
    explains_used = models.IntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "iso_year", "iso_week"], name="one_counter_per_week")]
