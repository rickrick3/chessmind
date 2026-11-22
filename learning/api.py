"""JSON endpoints for the lesson player (/api/v1/). Plain Django views; errors are {"error": {code, message}}."""
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from accounts.services import ensure_learner, request_language, update_settings
from curriculum.domain.schema import localize
from curriculum.models import Lesson, LessonVersion
from curriculum.services import published_content
from gamification.services import summary

from . import services
from .domain.scoring import InvalidResult
from .models import LessonAttempt


class BadRequest(Exception):
    pass


def json_error(code: str, message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def _body(request) -> dict:
    if len(request.body) > settings.API_MAX_BODY:
        raise BadRequest(_("The request is too large."))
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:  # RecursionError: absurdly deep nesting
        raise BadRequest(_("The request is not valid JSON.")) from exc
    if not isinstance(data, dict):
        raise BadRequest(_("The request must be a JSON object."))
    return data


def _bad_request(exc: BadRequest) -> JsonResponse:
    return json_error("bad_request", str(exc), 400)


def _me(learner) -> dict:
    if learner is None:
        return {"learner": None}
    return {"learner": {"is_guest": learner.is_guest, "display_name": learner.display_name,
                        "language": learner.language, "timezone": learner.timezone,
                        "start_level": learner.start_level, **summary(learner, timezone.now())}}


@require_GET
def me(request):
    return JsonResponse(_me(request.learner))


@require_POST
def start_level(request):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    if body.get("level") not in services.START_LEVELS:
        return json_error("bad_request", _("Pick one of the three levels."), 400)
    learner = ensure_learner(request, timezone=body.get("timezone"))
    return JsonResponse({"next_lesson": services.set_start_level(learner, body["level"])})


@require_POST
def me_settings(request):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    fields = {k: body[k] for k in ("display_name", "language", "daily_goal_xp", "timezone") if k in body}
    learner = ensure_learner(request)
    try:
        if "daily_goal_xp" in fields and not isinstance(fields["daily_goal_xp"], int):
            raise ValueError("daily_goal_xp")
        update_settings(learner, **fields)
    except (ValueError, TypeError) as exc:
        learner.refresh_from_db()
        return json_error("bad_request", _("Invalid value: %(field)s") % {"field": exc}, 400)
    return JsonResponse(_me(learner))


def _lesson_language(request) -> str:
    learner = request.learner
    return learner.language if learner is not None else request_language(request)


@require_GET
def lesson(request, slug):
    lesson = Lesson.objects.filter(slug=slug).select_related("published_version").first()
    if lesson is None:
        return json_error("not_found", _("This lesson does not exist."), 404)
    version = None
    preview = request.user.is_authenticated and request.user.is_staff and request.GET.get("version", "").isdigit()
    if preview:
        version = LessonVersion.objects.filter(pk=int(request.GET["version"]), lesson=lesson).first()
    if version is None:
        published = published_content(lesson)
        if published is None:
            return json_error("not_found", _("This lesson does not exist."), 404)
        version = published[0]
        if services.states_for(request.learner).get(slug, "locked") == "locked":
            return json_error("locked", _("Finish the lessons before this one first."), 403)
    content = localize(version.content, _lesson_language(request))
    meta = content.get("meta", {})
    return JsonResponse({
        "lesson": {"slug": lesson.slug, "kind": lesson.kind, "title": meta.get("title", ""),
                   "objectives": meta.get("objectives", []), "minutes": meta.get("estimated_minutes"),
                   "difficulty": meta.get("difficulty", lesson.difficulty),
                   "orientation": meta.get("orientation", "white")},
        "version_id": version.pk,
        "completion": content.get("completion", {"min_accuracy": 0}),
        "steps": content.get("steps", []),
    })


@require_POST
def attempts(request, slug):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    lesson = Lesson.objects.filter(slug=slug).first()
    if lesson is None:
        return json_error("not_found", _("This lesson does not exist."), 404)
    learner = ensure_learner(request, timezone=body.get("timezone"))
    try:
        attempt = services.start_attempt(learner, lesson, timezone.now())
    except services.NotPublished:
        return json_error("not_found", _("This lesson does not exist."), 404)
    except services.Locked:
        return json_error("locked", _("Finish the lessons before this one first."), 403)
    return JsonResponse({"attempt_id": str(attempt.id), "version_id": attempt.version_id}, status=201)


@require_POST
def finish(request, attempt_id):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    if request.learner is None:
        return json_error("not_found", _("This attempt does not exist."), 404)
    try:
        result = services.finish_attempt(request.learner, attempt_id, body.get("steps"), timezone.now())
    except LessonAttempt.DoesNotExist:
        return json_error("not_found", _("This attempt does not exist."), 404)
    except services.Expired:
        return json_error("expired", _("This lesson was started too long ago. Start it again."), 410)
    except InvalidResult:
        return json_error("invalid_result", _("These answers don't match the lesson."), 400)
    return JsonResponse(result)
