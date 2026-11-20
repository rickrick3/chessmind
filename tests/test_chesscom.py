import responses

from games import chesscom


@responses.activate
def test_get_player_404_returns_none():
    responses.get("https://api.chess.com/pub/player/nobody_xyz", status=404)
    assert chesscom.get_player("nobody_xyz") is None


@responses.activate
def test_get_player_sends_user_agent(settings):
    responses.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
    chesscom.get_player("Farel")
    assert responses.calls[0].request.headers["User-Agent"] == settings.CHESSCOM_USER_AGENT
    assert responses.calls[0].request.url.endswith("/player/farel")


@responses.activate
def test_get_player_429_raises_unavailable():
    import pytest

    responses.get("https://api.chess.com/pub/player/farel", status=429)
    with pytest.raises(chesscom.ChessComUnavailable):
        chesscom.get_player("farel")
