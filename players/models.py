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
