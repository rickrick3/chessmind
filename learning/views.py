from django.db.models import Avg
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from gamification.services import summary

from . import services
from .models import LessonProgress

TRACK_LABELS = {"path": _("Path"), "openings": _("Openings"), "endgames": _("Endgames"), "tactics": _("Tactics")}
PROFILE_TABS = ("performance", "mastery", "settings")


def _text(value, lang: str) -> str:
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or ""
    return value or ""


def _lesson_title(lesson, lang: str) -> str:
    return _text(lesson.published_version.content.get("meta", {}).get("title"), lang) or lesson.slug


def _units(learner, states: dict[str, str], track: str | None = None) -> list[dict]:
    """Published lessons grouped by unit, in order, with each lesson's state for this learner."""
    lang = learner.language
    lessons = services.published_lessons()
    if track:
        lessons = lessons.filter(unit__course__track=track)
    units: dict[int, dict] = {}
    for lesson in lessons:
        unit = units.setdefault(lesson.unit_id, {
            "course": _text(lesson.unit.course.title, lang), "title": _text(lesson.unit.title, lang),
            "track": lesson.unit.course.track, "lessons": []})
        state = states.get(lesson.slug, "locked")
        unit["lessons"].append({"slug": lesson.slug, "title": _lesson_title(lesson, lang), "state": state,
                                "offset": len(unit["lessons"]) % 4})
    for number, unit in enumerate(units.values(), start=1):
        unit["number"] = number
        unit["done"] = sum(1 for item in unit["lessons"] if item["state"] == "done")
        unit["total"] = len(unit["lessons"])
        upcoming = next((i for i in unit["lessons"] if i["state"] in ("current", "open")), None)
        unit["next_title"] = upcoming["title"] if upcoming else ""
        unit["percent"] = round(100 * unit["done"] / unit["total"]) if unit["total"] else 0
    return list(units.values())


@require_GET
def landing(request):
    learner = request.learner
    if learner is not None and (not learner.is_guest or LessonProgress.objects.filter(learner=learner).exists()):
        return redirect("/learn/")
    return render(request, "learning/landing.html")


@require_GET
def start(request):
    return render(request, "learning/start.html")


@require_GET
def path(request):
    learner = request.learner
    if learner is None:
        return redirect("/start/")
    states = services.states_for(learner)
    return render(request, "learning/path.html", {"units": _units(learner, states, track="path")})


@require_GET
def profile(request):
    learner = request.learner
    if learner is None:
        return redirect("/start/")
    tab = request.GET.get("tab") if request.GET.get("tab") in PROFILE_TABS else "performance"
    by_track = (LessonProgress.objects.filter(learner=learner, first_completed_at__isnull=False)
                .values("lesson__unit__course__track").annotate(avg=Avg("best_accuracy"))
                .order_by("lesson__unit__course__track"))
    accuracy = [{"label": TRACK_LABELS.get(row["lesson__unit__course__track"], row["lesson__unit__course__track"]),
                 "percent": round(100 * row["avg"])} for row in by_track]
    return render(request, "learning/profile.html", {
        "tab": tab, "tabs": PROFILE_TABS, "me": summary(learner, timezone.now()),
        "stats": services.progress_stats(learner), "accuracy": accuracy,
        "units": _units(learner, services.states_for(learner)) if tab == "mastery" else [],
    })
