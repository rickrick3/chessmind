from django.conf import settings
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from games.models import Game
from players.views import current_player

from .models import GameReview, MoveExplanation
from .tasks import start_review


def _own_review(request, review_id):
    player = current_player(request)
    if not player:
        return None, None
    review = get_object_or_404(GameReview.objects.select_related("game"), id=review_id)
    if review.player_id != player.id:
        raise Http404
    return player, review


@require_POST
def start_review_view(request, game_id):
    player = current_player(request)
    if not player:
        return redirect("chesscom_link")
    game = get_object_or_404(Game, id=game_id)
    if player.chesscom_username not in (game.white, game.black):
        raise Http404
    review = start_review(player, game)
    if review is None:
        messages.warning(request, _("You've used your %(n)s reviews this week. New ones open on Monday.")
                         % {"n": settings.LIMIT_REVIEWS_PER_WEEK})
        return redirect("game_list")
    return redirect("review_page", review_id=review.id)


def review_page(request, review_id):
    player, review = _own_review(request, review_id)
    if not player:
        return redirect("chesscom_link")
    return render(request, "review.html", {"review": review, "game": review.game})


def review_status(request, review_id):
    player, review = _own_review(request, review_id)
    if not player:
        return redirect("chesscom_link")
    texts = dict(MoveExplanation.objects.filter(id__in=[m["explanation_id"] for m in review.moves])
                 .values_list("id", "text"))
    moves = [{
        "ply": m["ply"], "san": m["san"], "fen_before": m["fen_before"], "grade": m["grade"],
        "key_moment": m["key_moment"], "best_uci": m["best_uci"], "replies_uci": m["replies_uci"],
        "text": texts.get(m["explanation_id"], ""),
    } for m in review.moves]
    return JsonResponse({"status": review.status, "counts": review.counts, "moves": moves})
