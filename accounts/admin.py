from django.contrib import admin

from .models import Learner


@admin.register(Learner)
class LearnerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "display_name", "language", "xp_total", "current_streak", "last_seen_at")
    search_fields = ("user__email", "display_name")
    raw_id_fields = ("user", "player")
