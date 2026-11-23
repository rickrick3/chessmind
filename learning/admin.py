from django.contrib import admin

from .models import LessonAttempt, LessonProgress


@admin.register(LessonAttempt)
class LessonAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "learner", "lesson", "started_at", "completed", "accuracy", "xp_awarded")
    raw_id_fields = ("learner", "lesson", "version")


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("learner", "lesson", "first_completed_at", "best_accuracy", "completions")
    raw_id_fields = ("learner", "lesson")
