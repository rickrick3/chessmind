"""JSON endpoints for the puzzle board (/api/v1/). Same conventions as the lesson API (learning/api.py)."""
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.services import ensure_learner
from learning.api import BadRequest, _bad_request, _body, json_error

from . import services
from .domain.solution import InvalidPuzzleResult
from .models import Puzzle, PuzzleAttempt, PuzzleReport

MAX_NOTE = 500


@require_POST
def next_puzzle(request):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    mode, theme, difficulty = body.get("mode"), body.get("theme") or "", body.get("difficulty") or "normal"
    if not all(isinstance(v, str) for v in (mode, theme, difficulty)):
        return json_error("bad_request", _("Unknown mode, theme or difficulty."), 400)
    learner = ensure_learner(request, timezone=body.get("timezone"))
    try:
        attempt = services.next_puzzle(learner, mode=mode, theme=theme, difficulty=difficulty, now=timezone.now())
    except ValueError:
        return json_error("bad_request", _("Unknown mode, theme or difficulty."), 400)
    except services.NoPuzzleLeft:
        return json_error("no_puzzle", _("You've seen every puzzle here. Try another theme or difficulty."), 404)
    p = attempt.puzzle
    return JsonResponse({"attempt_id": str(attempt.id), "mode": attempt.mode, "theme": attempt.theme,
                         "puzzle": {"fen": p.fen, "moves": p.moves, "side": p.side}})


@require_POST
def finish(request, attempt_id):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    if request.learner is None:
        return json_error("not_found", _("This puzzle does not exist."), 404)
    try:
        result = services.finish_puzzle(request.learner, attempt_id, body, timezone.now())
    except PuzzleAttempt.DoesNotExist:
        return json_error("not_found", _("This puzzle does not exist."), 404)
    except services.Expired:
        return json_error("expired", _("This puzzle was opened too long ago."), 410)
    except InvalidPuzzleResult:
        return json_error("invalid_result", _("These moves don't match the puzzle."), 400)
    return JsonResponse(result)


@require_POST
def report(request, lichess_id):
    try:
        body = _body(request)
    except BadRequest as exc:
        return _bad_request(exc)
    reason, note = body.get("reason"), body.get("note") or ""
    if reason not in dict(PuzzleReport.REASONS) or not isinstance(note, str) or len(note) > MAX_NOTE:
        return json_error("bad_request", _("Pick a reason; the note can be up to 500 characters."), 400)
    learner = request.learner
    puzzle = Puzzle.objects.filter(lichess_id=lichess_id).first()
    if learner is None or puzzle is None or not PuzzleAttempt.objects.filter(learner=learner, puzzle=puzzle).exists():
        return json_error("not_found", _("This puzzle does not exist."), 404)
    _report, created = PuzzleReport.objects.get_or_create(learner=learner, puzzle=puzzle,
                                                          defaults={"reason": reason, "note": note})
    return JsonResponse({"reported": True}, status=201 if created else 200)
