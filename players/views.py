from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .models import Player


def current_player(request) -> Player | None:
    """The Chess.com player linked to this request's learner, if any."""
    learner = getattr(request, "learner", None)
    return learner.player if learner is not None else None


def _with_language(response, lang):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=365 * 24 * 3600)
    return response


@require_POST
def set_language(request):
    lang = request.POST.get("lang")
    if lang not in ("fr", "en"):
        lang = "en"
    learner = getattr(request, "learner", None)
    if learner is not None:
        learner.language = lang
        learner.save(update_fields=["language"])
    player = current_player(request)
    if player:
        player.language = lang
        player.save(update_fields=["language"])
    return _with_language(redirect(request.POST.get("next") or "/"), lang)
