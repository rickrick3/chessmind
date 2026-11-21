from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from games import chesscom

from .models import Player


def current_player(request) -> Player | None:
    """The Chess.com player linked to this request's learner, if any."""
    learner = getattr(request, "learner", None)
    return learner.player if learner is not None else None


def _with_language(response, lang):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=365 * 24 * 3600)
    return response


def signin(request):
    if request.method != "POST":
        if current_player(request):
            return redirect("game_list")
        return render(request, "signin.html")
    username = request.POST.get("username", "").strip().lower()
    if not username:
        return render(request, "signin.html", {"error": _("Type your Chess.com username.")})
    try:
        data = chesscom.get_player(username)
    except chesscom.ChessComUnavailable:
        return render(request, "signin.html", {
            "error": _("Chess.com is not answering, try again in a minute."), "username": username})
    if data is None:
        return render(request, "signin.html", {
            "error": _("No Chess.com player named “%(name)s”.") % {"name": username}, "username": username})
    lang = "fr" if request.LANGUAGE_CODE == "fr" else "en"
    player, _created = Player.objects.get_or_create(chesscom_username=username, defaults={"language": lang})
    request.session["player_id"] = player.id
    return _with_language(redirect("game_list"), player.language)


def signout(request):
    request.session.flush()
    return redirect("signin")


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
    return _with_language(redirect(request.POST.get("next") or "signin"), lang)
