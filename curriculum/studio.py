"""Staff pages: list lessons, edit a version's JSON, read its report and history, move it through the workflow."""
import json
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .domain.workflow import (APPROVED, DRAFT, EDITABLE, PENDING_REVIEW, PUBLISHED, REJECTED, VALIDATING,
                              IllegalTransition)
from .models import Course, Lesson, LessonVersion


def staff_only(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


@staff_only
def lesson_list(request):
    courses = Course.objects.prefetch_related("units__lessons__versions", "units__lessons__published_version")
    return render(request, "studio/lesson_list.html", {"courses": courses})


ACTIONS = {
    DRAFT: [(VALIDATING, "Validate")],
    PENDING_REVIEW: [(APPROVED, "Approve"), (REJECTED, "Reject")],
    APPROVED: [(PUBLISHED, "Publish")],
}


@staff_only
def version_page(request, pk):
    version = get_object_or_404(LessonVersion.objects.select_related("lesson"), pk=pk)
    return render(request, "studio/version.html", {
        "version": version,
        "lesson": version.lesson,
        "editable": version.status in EDITABLE,
        "content_json": json.dumps(version.content, ensure_ascii=False, indent=2),
        "issues": version.validation_report.get("issues", []),
        "events": version.events.select_related("actor"),
        "actions": ACTIONS.get(version.status, []),
    })


@staff_only
@require_POST
def version_content(request, pk):
    version = get_object_or_404(LessonVersion, pk=pk)
    try:
        content = json.loads(request.POST.get("content", ""))
    except json.JSONDecodeError as exc:
        messages.error(request, f"Not valid JSON: {exc}")
        return redirect("studio_version", pk=pk)
    try:
        services.edit_content(version, content, request.user)
        messages.success(request, "Saved.")
    except IllegalTransition as exc:
        messages.error(request, f"Not saved: {exc}")
    return redirect("studio_version", pk=pk)


@staff_only
@require_POST
def version_transition(request, pk):
    version = get_object_or_404(LessonVersion, pk=pk)
    to, note = request.POST.get("to", ""), request.POST.get("note", "")
    try:
        services.transition(version, to, request.user, note=note)
        messages.success(request, f"Moved to {to}.")
    except ValueError:
        messages.error(request, "Rejecting needs a note that says why.")
    except IllegalTransition as exc:
        messages.error(request, f"Not allowed: {exc}")
    return redirect("studio_version", pk=pk)


@staff_only
@require_POST
def new_version(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug)
    version = services.new_version(lesson, request.user)
    return redirect("studio_version", pk=version.pk)
