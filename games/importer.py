import io
from datetime import date, datetime, timezone

import chess.pgn
from django.db.models import Q

from . import chesscom
from .models import ArchiveETag, Game


def _months(today: date) -> list[tuple[int, int]]:
    prev = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return [(today.year, today.month), prev]


def _parse(raw: dict) -> dict | None:
    if raw.get("rules") != "chess":
        return None
    pgn_text = raw.get("pgn") or ""
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    if parsed is None or parsed.errors or parsed.next() is None:
        return None
    h = parsed.headers
    eco_url = h.get("ECOUrl", "")
    return {
        "pgn": pgn_text,
        "white": raw["white"]["username"].lower(),
        "black": raw["black"]["username"].lower(),
        "white_rating": raw["white"].get("rating"),
        "black_rating": raw["black"].get("rating"),
        "result": h.get("Result", "*"),
        "time_control": raw.get("time_control", ""),
        "time_class": raw.get("time_class", ""),
        "eco": h.get("ECO", "")[:5],
        "opening_name": eco_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ") if eco_url else "",
        "played_at": datetime.fromtimestamp(raw["end_time"], tz=timezone.utc),
    }


def import_recent_games(player, today: date) -> list[Game]:
    """Fetch the current and previous month, one request at a time; store standard games only."""
    for year, month in _months(today):
        tag = ArchiveETag.objects.filter(username=player.chesscom_username, year=year, month=month).first()
        raws, etag = chesscom.get_month_games(player.chesscom_username, year, month, tag.etag if tag else None)
        if etag and (not tag or tag.etag != etag):
            ArchiveETag.objects.update_or_create(
                username=player.chesscom_username, year=year, month=month, defaults={"etag": etag})
        for raw in raws:
            fields = _parse(raw)
            if fields:
                Game.objects.update_or_create(chesscom_url=raw["url"], defaults=fields)
    name = player.chesscom_username
    return list(Game.objects.filter(player_games_q(name)).order_by("-played_at"))


def player_games_q(username):
    return Q(white=username) | Q(black=username)
