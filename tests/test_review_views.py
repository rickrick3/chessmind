import pytest
from django.utils import timezone

from analysis.models import GameReview, MoveExplanation, PositionAnalysis
from games.models import Game
from players.models import Player, UsageCounter

pytestmark = pytest.mark.django_db


def sign_in(client, player):
    s = client.session
    s["player_id"] = player.id
    s.save()
    client.cookies["django_language"] = player.language


@pytest.fixture
def farel():
    return Player.objects.create(chesscom_username="farel", language="en")


@pytest.fixture
def farel_fr():
    return Player.objects.create(chesscom_username="farel", language="fr")


@pytest.fixture
def game():
    return Game.objects.create(chesscom_url="https://www.chess.com/game/live/1", pgn="1. e4 e5 1-0", white="farel",
                               black="opp", result="1-0", played_at=timezone.now())


def done_review_for(player, game, lang):
    pos = PositionAnalysis.objects.create(fen=f"f-{lang}", depth=8, lines=[], cp=0)
    e = MoveExplanation.objects.create(position=pos, move_uci="e2e4", language=lang, depth="short",
                                       text=f"text-{lang}", source="template")
    move = {"ply": 1, "san": "e4", "uci": "e2e4", "fen_before": "start", "grade": "best", "key_moment": False,
            "explanation_id": e.id, "best_uci": None, "replies_uci": ["e7e5"]}
    return GameReview.objects.create(game=game, player=player, language=lang, status="done", moves=[move],
                                     counts={"best": 1})


def test_status_json_shape(client, farel, game):
    r = done_review_for(farel, game, "en")
    sign_in(client, farel)
    d = client.get(f"/reviews/{r.id}/status.json").json()
    assert d["status"] == "done" and d["counts"] == {"best": 1}
    assert set(d["moves"][0]) == {"ply", "san", "fen_before", "grade", "key_moment", "best_uci", "replies_uci",
                                  "text"}


def test_status_text_in_review_language(client, farel_fr, game):
    r = done_review_for(farel_fr, game, "fr")
    sign_in(client, farel_fr)
    d = client.get(f"/reviews/{r.id}/status.json").json()
    assert d["moves"][0]["text"] == "text-fr"


def test_other_players_review_is_404(client, farel, game):
    other = Player.objects.create(chesscom_username="opp")
    r = done_review_for(other, game, "en")
    sign_in(client, farel)
    assert client.get(f"/reviews/{r.id}/status.json").status_code == 404
    assert client.get(f"/reviews/{r.id}/").status_code == 404


def test_signed_out_redirects_to_signin(client, farel, game):
    r = done_review_for(farel, game, "en")
    resp = client.get(f"/reviews/{r.id}/")
    assert resp.status_code == 302 and resp.url == "/"


def test_start_review_redirects_to_page(client, farel, game):
    sign_in(client, farel)
    resp = client.post(f"/games/{game.id}/review/")
    review = GameReview.objects.get()
    assert resp.status_code == 302 and resp.url == f"/reviews/{review.id}/"


def test_cannot_review_someone_elses_game(client, game):
    stranger = Player.objects.create(chesscom_username="stranger")
    sign_in(client, stranger)
    assert client.post(f"/games/{game.id}/review/").status_code == 404


def test_over_limit_message_fr(client, farel_fr, game):
    now = timezone.now()
    year, week, _ = now.isocalendar()
    UsageCounter.objects.create(player=farel_fr, iso_year=year, iso_week=week, reviews_used=5)
    sign_in(client, farel_fr)
    r = client.post(f"/games/{game.id}/review/", follow=True)
    assert "Tu as utilisé tes 5 analyses de la semaine" in r.content.decode()


def test_review_page_loads_board_assets(client, farel, game):
    r = done_review_for(farel, game, "en")
    sign_in(client, farel)
    html = client.get(f"/reviews/{r.id}/").content.decode()
    assert "cm-chessboard" in html and "review.js" in html and f"/reviews/{r.id}/status.json" in html
