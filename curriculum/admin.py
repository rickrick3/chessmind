from django.contrib import admin

from .models import Course, Lesson, LessonVersion, Unit, VersionEvent


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("slug", "track", "order", "is_active")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("slug", "course", "order")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("slug", "unit", "order", "kind", "published_version")
    raw_id_fields = ("published_version",)


class EventInline(admin.TabularInline):
    model = VersionEvent
    extra = 0
    can_delete = False
    readonly_fields = ("at", "actor", "kind", "from_status", "to_status", "note")
    exclude = ("content_snapshot",)


@admin.register(LessonVersion)
class LessonVersionAdmin(admin.ModelAdmin):
    list_display = ("lesson", "number", "status", "created_at", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("content", "validation_report", "brief", "generator")
    inlines = [EventInline]
