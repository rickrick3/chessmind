from django.contrib import messages
from django.db.models import Avg
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from accounts.services import request_language
from curriculum.domain.schema import localize
from curriculum.models import Lesson, LessonVersion
from curriculum.services import published_content
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


def _player_strings() -> dict:
    g = gettext
    return {
        "continue": g("Continue"), "check": g("Check"), "hint": g("Hint"), "close": g("Close"),
        "excellent": g("Excellent!"), "notQuite": g("Not quite"), "tryAgain": g("Try again."),
        "showAnswer": g("Here is the move. Play it."), "alsoWorks": g("That also works. We'll follow the lesson's line."),
        "lineDone": g("Line complete"), "yourMove": g("Your move."), "loadError": g("This lesson could not load."),
        "lessonDone": g("Lesson complete!"), "lessonNotDone": g("Almost there. Try this lesson again."),
        "accuracy": g("Accuracy"), "time": g("Time"), "streak": g("Day streak"), "levelUp": g("Level up!"),
        "keepProgress": g("Create an account to keep your progress"), "createAccount": g("Create an account"),
        "backToPath": g("Continue"), "preview": g("Preview: nothing was saved."), "saving": g("Saving…"),
        "savedLater": g("We'll save this when you're back online."),
        "achievements": {"first_lesson": g("First lesson"), "first_unit": g("First unit complete"),
                         "streak_3": g("3-day streak"), "streak_7": g("7-day streak"), "streak_30": g("30-day streak"),
                         "perfect_10": g("10 perfect lessons")},
    }


@require_GET
def lesson_page(request, slug):
    lesson = get_object_or_404(Lesson.objects.select_related("published_version"), slug=slug)
    learner = request.learner
    wanted = request.GET.get("version", "")
    preview = (request.user.is_authenticated and request.user.is_staff and wanted.isdigit()
               and LessonVersion.objects.filter(pk=int(wanted), lesson=lesson).exists())
    if not preview:
        if published_content(lesson) is None:
            raise Http404
        if services.states_for(learner).get(slug, "locked") == "locked":
            messages.info(request, gettext("Finish the lessons before this one first."))
            return redirect("/learn/")
    lang = learner.language if learner is not None else request_language(request)
    lesson_url = f"/api/v1/lessons/{slug}" + (f"?version={wanted}" if preview else "")
    config = {
        "lessonUrl": lesson_url, "attemptsUrl": f"/api/v1/lessons/{slug}/attempts",
        "finishUrl": "/api/v1/attempts/{id}/finish", "preview": bool(preview),
        "versionId": int(wanted) if preview else None, "isGuest": learner is None or learner.is_guest,
        "signupUrl": "/signup/?next=/profile/", "pathUrl": "/learn/", "csrfToken": get_token(request),
        "assets": static("vendor/cm-chessboard/assets/"), "lang": lang, "i18n": _player_strings(),
    }
    version = LessonVersion.objects.get(pk=int(wanted)) if preview else lesson.published_version
    title = localize(version.content.get("meta", {}), lang).get("title") or lesson.slug
    return render(request, "learning/lesson.html", {"config": config, "lesson": lesson, "lesson_title": title})
