from django.contrib import admin

from .models import LearnerAchievement, XpEvent


@admin.register(XpEvent)
class XpEventAdmin(admin.ModelAdmin):
    list_display = ("learner", "amount", "reason", "lesson", "local_date", "created_at")
    list_filter = ("reason",)
    raw_id_fields = ("learner", "lesson", "attempt")


@admin.register(LearnerAchievement)
class LearnerAchievementAdmin(admin.ModelAdmin):
    list_display = ("learner", "code", "earned_at")
    raw_id_fields = ("learner",)
