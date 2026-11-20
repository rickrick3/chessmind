from django.db import models


class Game(models.Model):
    chesscom_url = models.URLField(unique=True)
    pgn = models.TextField()
    white = models.CharField(max_length=50)
    black = models.CharField(max_length=50)
    white_rating = models.IntegerField(null=True)
    black_rating = models.IntegerField(null=True)
    result = models.CharField(max_length=10)
    time_control = models.CharField(max_length=20, blank=True)
    time_class = models.CharField(max_length=20, blank=True)
    eco = models.CharField(max_length=5, blank=True)
    opening_name = models.CharField(max_length=200, blank=True)
    played_at = models.DateTimeField()

    class Meta:
        ordering = ["-played_at"]

    def __str__(self):
        return f"{self.white} vs {self.black} ({self.played_at:%Y-%m-%d})"


class ArchiveETag(models.Model):
    """Last ETag seen for one player's monthly archive, so repeat imports cost Chess.com nothing."""

    username = models.CharField(max_length=50)
    year = models.IntegerField()
    month = models.IntegerField()
    etag = models.CharField(max_length=200)

    class Meta:
        unique_together = [("username", "year", "month")]
