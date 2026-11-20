import io
from collections import Counter

import chess
import chess.pgn
from celery import shared_task
from django.utils import timezone

from players.limits import refund, try_consume

from . import explain
from .ai import ProviderError, QuotaExceeded
from .engine import analyse
from .facts import FactPacket, build_fact_packet
from .models import GameReview, MoveExplanation


def start_review(player, game) -> GameReview | None:
    """Create (or reuse) this player's review and queue it. None when the weekly limit is reached.
    Free when someone already finished a review of the same game: everything is cached."""
    review, created = GameReview.objects.get_or_create(game=game, player=player, defaults={"language": player.language})
    if not created and review.status != "failed":
        return review
    free = GameReview.objects.filter(game=game, status="done").exists()
    if not free and not try_consume(player, "reviews", timezone.now()):
        if created:
            review.delete()
        return None
    review.charged = not free
    review.status, review.error, review.language = "queued", "", player.language
    review.save()
    run_review.delay(review.id)
    return review


@shared_task
def run_review(review_id: int) -> None:
    review = GameReview.objects.select_related("player", "game").get(id=review_id)
    review.status = "running"
    review.save(update_fields=["status"])
    try:
        game = chess.pgn.read_game(io.StringIO(review.game.pgn))
        board = game.board()
        moves, counts = [], Counter()
        for ply, move in enumerate(game.mainline_moves(), start=1):
            before = analyse(board)
            fen_before = board.fen()
            after_board = board.copy()
            after_board.push(move)
            after = analyse(after_board)
            p = build_fact_packet(board, move, before, after, ply)
            e = explain.get_explanation(before, move.uci(), p, review.language)
            moves.append({
                "ply": ply, "san": p.san, "uci": move.uci(), "fen_before": fen_before, "grade": p.grade,
                "key_moment": p.key_moment, "explanation_id": e.id,
                "best_uci": before.lines[0]["uci"][0] if p.best_san and before.lines else None,
                "replies_uci": [line["uci"][0] for line in after.lines[:3] if line["uci"]],
            })
            counts[p.grade] += 1
            board = after_board
        review.moves, review.counts, review.status = moves, dict(counts), "done"
        review.finished_at = timezone.now()
        review.save()
    except Exception as exc:  # noqa: BLE001 — any failure must leave the review in a visible state
        review.status, review.error = "failed", str(exc)[:500]
        if review.charged:
            refund(review.player, "reviews", timezone.now())
            review.charged = False
        review.save()


@shared_task
def upgrade_pending_explanations() -> int:
    """Replace template stand-ins with AI text, oldest first, until the quota runs out. Returns how many."""
    provider = explain.get_provider()
    done = 0
    for e in MoveExplanation.objects.filter(needs_ai=True).order_by("created_at", "id"):
        p = FactPacket(**e.facts)
        try:
            text = explain.ai_text(provider, p, e.language)
        except QuotaExceeded:
            break
        except ProviderError:
            continue
        if text:
            e.text, e.source, e.model, e.needs_ai = text, "ai", provider.name, False
            e.save(update_fields=["text", "source", "model", "needs_ai"])
            done += 1
    return done
