from django.contrib import admin

from .models import Evidence, SkillEstimate


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Evidence)
class EvidenceAdmin(ReadOnlyAdmin):
    list_display = ("learner", "area", "source", "success", "difficulty", "local_date")
    list_filter = ("area", "source")


@admin.register(SkillEstimate)
class SkillEstimateAdmin(ReadOnlyAdmin):
    list_display = ("learner", "kind", "key", "basis", "low", "high", "observations", "confidence", "status")
    list_filter = ("kind", "confidence", "status")
