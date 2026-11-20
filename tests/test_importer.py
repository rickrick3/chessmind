import json
from datetime import date
from pathlib import Path

import pytest
import responses

from games.importer import import_recent_games
from games.models import Game
from players.models import Player

pytestmark = pytest.mark.django_db
FIX = Path(__file__).parent / "fixtures"
API = "https://api.chess.com/pub/player/farel/games"


@pytest.fixture
def player():
    return Player.objects.create(chesscom_username="farel")


@pytest.fixture
def mock_archive():
    nov = json.loads((FIX / "archive_2026_11.json").read_text())
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.get(f"{API}/2026/11", json=nov, headers={"ETag": '"nov1"'})
        rsps.get(f"{API}/2026/10", json={"games": []})
        yield rsps


def test_import_skips_variants_and_empty_games(player, mock_archive):
    games = import_recent_games(player, date(2026, 11, 20))
    assert len(games) == 2
    assert all("[Variant" not in g.pgn for g in games)


def test_import_fetches_two_months_serially(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    urls = [c.request.url for c in mock_archive.calls]
    assert urls[-2:] == [f"{API}/2026/11", f"{API}/2026/10"]


def test_import_twice_no_duplicates(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    import_recent_games(player, date(2026, 11, 20))
    assert Game.objects.count() == 2


def test_second_import_sends_etag(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    import_recent_games(player, date(2026, 11, 20))
    nov_calls = [c for c in mock_archive.calls if c.request.url.endswith("/2026/11")]
    assert nov_calls[1].request.headers.get("If-None-Match") == '"nov1"'


def test_import_fills_opening_and_players(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    g = Game.objects.get(chesscom_url="https://www.chess.com/game/live/4")
    assert (g.white, g.black, g.eco) == ("opp4", "farel", "D37")
    assert g.opening_name == "Queens Gambit Declined"


def test_january_reaches_back_to_december(player):
    with responses.RequestsMock() as rsps:
        rsps.get(f"{API}/2027/01", json={"games": []})
        rsps.get(f"{API}/2026/12", json={"games": []})
        import_recent_games(player, date(2027, 1, 3))
        assert rsps.calls[1].request.url.endswith("/2026/12")


def test_game_list_newest_first(client, player, mock_archive):
    session = client.session
    session["player_id"] = player.id
    session.save()
    r = client.get("/games/")
    games = r.context["games"]
    assert len(games) == 2 and games[0].played_at > games[1].played_at


def test_game_list_requires_signin(client):
    r = client.get("/games/")
    assert r.status_code == 302 and r.url == "/"
