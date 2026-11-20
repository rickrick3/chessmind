import pytest
from django.utils import timezone

from analysis.models import GameReview
from analysis.tasks import start_review
from games.models import Game
from players.models import Player, UsageCounter

pytestmark = pytest.mark.django_db
SHORT = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Na5 1-0"
SCHOLARS = "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"


def make_game(i, moves=SHORT, white="farel", black="opp"):
    return Game.objects.create(chesscom_url=f"https://www.chess.com/game/live/{i}", pgn=moves, white=white,
                               black=black, result="1-0", played_at=timezone.now())


@pytest.fixture
def player():
    return Player.objects.create(chesscom_username="farel", language="en")


@pytest.fixture
def opponent():
    return Player.objects.create(chesscom_username="opp", language="fr")


def test_sixth_review_in_week_refused(player):
    results = [start_review(player, make_game(i, SCHOLARS)) for i in range(6)]
    assert sum(r is not None for r in results) == 5


def test_same_game_twice_counts_once(player):
    g = make_game(1, SCHOLARS)
    start_review(player, g)
    start_review(player, g)
    assert UsageCounter.objects.get().reviews_used == 1
    assert GameReview.objects.count() == 1


def test_opponent_review_of_done_game_is_free(player, opponent):
    g = make_game(1, SCHOLARS, black="opp")
    start_review(player, g)
    r = start_review(opponent, g)
    r.refresh_from_db()
    assert r.status == "done" and r.language == "fr"
    assert not UsageCounter.objects.filter(player=opponent, reviews_used__gt=0).exists()


def test_run_review_fills_every_ply(player):
    r = start_review(player, make_game(1))
    r.refresh_from_db()
    assert r.status == "done" and len(r.moves) == 10
    assert all(m["explanation_id"] for m in r.moves)
    assert [m["san"] for m in r.moves[:3]] == ["e4", "e5", "Nf3"]
    assert sum(r.counts.values()) == 10
    first = r.moves[0]
    assert set(first) >= {"ply", "san", "uci", "fen_before", "grade", "key_moment", "explanation_id", "best_uci",
                          "replies_uci"}


def test_game_ending_in_mate_reviews(player):
    r = start_review(player, make_game(1, SCHOLARS))
    r.refresh_from_db()
    assert r.status == "done" and r.moves[-1]["san"] == "Qxf7#"
    assert r.moves[-1]["replies_uci"] == []


def test_failure_refunds(player, mocker):
    mocker.patch("analysis.tasks.analyse", side_effect=RuntimeError("boom"))
    r = start_review(player, make_game(1))
    r.refresh_from_db()
    assert r.status == "failed" and "boom" in r.error
    assert UsageCounter.objects.get().reviews_used == 0


def test_failed_review_can_be_retried(player, mocker):
    g = make_game(1, SCHOLARS)
    mocker.patch("analysis.tasks.analyse", side_effect=RuntimeError("boom"))
    start_review(player, g)
    mocker.stopall()
    r = start_review(player, g)
    r.refresh_from_db()
    assert r.status == "done" and UsageCounter.objects.get().reviews_used == 1
