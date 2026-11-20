"""Chess.com Published-Data API client. One request at a time, identified by User-Agent."""
import requests
from django.conf import settings

BASE = "https://api.chess.com/pub"
TIMEOUT = 15


class ChessComUnavailable(Exception):
    """Chess.com rate-limited us, failed, or timed out."""


def _get(url, headers=None):
    h = {"User-Agent": settings.CHESSCOM_USER_AGENT, **(headers or {})}
    try:
        return requests.get(url, headers=h, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ChessComUnavailable(str(exc)) from exc


def get_player(username: str) -> dict | None:
    r = _get(f"{BASE}/player/{username.strip().lower()}")
    if r.status_code in (404, 410):
        return None
    if r.status_code != 200:
        raise ChessComUnavailable(f"HTTP {r.status_code}")
    return r.json()
