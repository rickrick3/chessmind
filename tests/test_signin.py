import pytest
import responses

from players.models import Player

pytestmark = pytest.mark.django_db


@pytest.fixture
def mocked_farel():
    with responses.RequestsMock() as rsps:
        rsps.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
        yield rsps


@responses.activate
def test_signin_unknown_username_shows_error(client):
    responses.get("https://api.chess.com/pub/player/nobody_xyz", status=404)
    r = client.post("/", {"username": "nobody_xyz"})
    assert r.status_code == 200 and "nobody_xyz" in r.content.decode()
    assert Player.objects.count() == 0


@responses.activate
def test_signin_case_insensitive_one_player(client):
    responses.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
    client.post("/", {"username": "Farel"})
    client.post("/", {"username": "farel"})
    assert Player.objects.get().chesscom_username == "farel"


def test_language_guessed_from_browser(client, mocked_farel):
    client.post("/", {"username": "farel"}, HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9")
    assert Player.objects.get().language == "fr"


def test_signin_redirects_to_games(client, mocked_farel):
    r = client.post("/", {"username": "farel"})
    assert r.status_code == 302 and r.url == "/games/"
    assert client.session["player_id"] == Player.objects.get().id


@responses.activate
def test_chesscom_down_shows_message(client):
    responses.get("https://api.chess.com/pub/player/farel", status=503)
    r = client.post("/", {"username": "farel"})
    assert "Chess.com" in r.content.decode() and Player.objects.count() == 0
