from django.conf import settings
from django.db import models

from .domain import workflow


class Course(models.Model):
    TRACKS = [("path", "Path"), ("openings", "Openings"), ("endgames", "Endgames"), ("tactics", "Tactics")]

    slug = models.SlugField(max_length=60, unique=True)
    track = models.CharField(max_length=10, choices=TRACKS)
    order = models.IntegerField(default=0)
    title = models.JSONField(default=dict)  # {"fr": ..., "en": ...}
    description = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["track", "order", "id"]

    def __str__(self):
        return self.slug


class Unit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    order = models.IntegerField(default=0)
    slug = models.SlugField(max_length=60)
    title = models.JSONField(default=dict)
    description = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["course", "order", "id"]
        constraints = [models.UniqueConstraint(fields=["course", "slug"], name="unique_unit_slug_per_course")]

    def __str__(self):
        return f"{self.course.slug}/{self.slug}"


class Lesson(models.Model):
    KINDS = [("concept", "Concept"), ("tactic", "Tactic"), ("opening", "Opening"), ("endgame", "Endgame")]
    SIDES = [("white", "White"), ("black", "Black"), ("both", "Both")]

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="lessons")
    order = models.IntegerField(default=0)
    slug = models.SlugField(max_length=80, unique=True)
    kind = models.CharField(max_length=10, choices=KINDS)
    difficulty = models.PositiveSmallIntegerField(default=1)
    side = models.CharField(max_length=5, choices=SIDES, default="both")
    eco = models.CharField(max_length=5, blank=True)
    prerequisites = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="unlocks")
    published_version = models.ForeignKey("LessonVersion", null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["unit", "order", "id"]

    def __str__(self):
        return self.slug


class LessonVersion(models.Model):
    STATUS_CHOICES = [(s, s) for s in workflow.STATUSES]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=workflow.DRAFT, db_index=True)
    brief = models.JSONField(default=dict, blank=True)  # generation inputs (milestone 2)
    content = models.JSONField(default=dict, blank=True)  # the lesson document, see curriculum.domain.schema
    validation_report = models.JSONField(default=dict, blank=True)
    generator = models.JSONField(default=dict, blank=True)  # {model, prompt_version, sources}
    error = models.TextField(blank=True)
    retry_after = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["lesson", "-number"]
        constraints = [models.UniqueConstraint(fields=["lesson", "number"], name="unique_version_number")]

    def __str__(self):
        return f"{self.lesson.slug} v{self.number} ({self.status})"


class VersionEvent(models.Model):
    """Append-only audit trail: every status change and every content edit, with who did it."""

    KINDS = [("transition", "Transition"), ("edit", "Edit")]

    version = models.ForeignKey(LessonVersion, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")  # None = the system
    kind = models.CharField(max_length=10, choices=KINDS)
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    note = models.TextField(blank=True)
    content_snapshot = models.JSONField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "id"]
