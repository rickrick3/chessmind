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


def get_month_games(username: str, year: int, month: int, etag: str | None = None) -> tuple[list[dict], str | None]:
    """Return (games, etag). On 304 Not Modified returns ([], etag)."""
    headers = {"If-None-Match": etag} if etag else {}
    r = _get(f"{BASE}/player/{username.strip().lower()}/games/{year}/{month:02d}", headers)
    if r.status_code == 304:
        return [], etag
    if r.status_code == 404:
        return [], None
    if r.status_code != 200:
        raise ChessComUnavailable(f"HTTP {r.status_code}")
    return r.json().get("games", []), r.headers.get("ETag")
