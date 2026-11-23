from django.contrib import admin

from .models import Puzzle, PuzzleAttempt, PuzzleRating, PuzzleReport


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("lichess_id", "rating", "is_active", "themes")
    list_filter = ("is_active",)
    search_fields = ("lichess_id",)
    actions = ["deactivate"]

    @admin.action(description="Deactivate selected puzzles")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(PuzzleReport)
class PuzzleReportAdmin(admin.ModelAdmin):
    list_display = ("puzzle", "reason", "note", "created_at")
    list_filter = ("reason",)
    actions = ["deactivate_puzzles"]

    @admin.action(description="Deactivate the reported puzzles")
    def deactivate_puzzles(self, request, queryset):
        Puzzle.objects.filter(reports__in=queryset).update(is_active=False)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PuzzleAttempt)
class PuzzleAttemptAdmin(ReadOnlyAdmin):
    list_display = ("id", "learner", "puzzle", "mode", "served_at", "finished_at", "solved", "rated")


@admin.register(PuzzleRating)
class PuzzleRatingAdmin(ReadOnlyAdmin):
    list_display = ("learner", "rating", "rd", "rated_count", "last_rated_on")
