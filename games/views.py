from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from django.conf import settings

from players.limits import used
from players.views import current_player

from . import chesscom
from .importer import import_recent_games, player_games_q
from .models import Game


def game_list(request):
    player = current_player(request)
    if not player:
        return redirect("signin")
    try:
        games = import_recent_games(player, timezone.now().date())
    except chesscom.ChessComUnavailable:
        messages.warning(request, _("Chess.com is not answering, showing the games already imported."))
        games = list(Game.objects.filter(player_games_q(player.chesscom_username)))
    left = max(0, settings.LIMIT_REVIEWS_PER_WEEK - used(player, "reviews", timezone.now()))
    return render(request, "game_list.html", {"games": games, "reviews_left": left})
