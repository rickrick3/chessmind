"""Server Stockfish over UCI (separate GPL process), with a shared cache keyed by normalised FEN."""
import threading

import chess
import chess.engine
from django.conf import settings
from django.db import IntegrityError, transaction

from .models import PositionAnalysis

_engine = None


def normalize_fen(board: chess.Board) -> str:
    return " ".join(board.fen().split(" ")[:4])


def get_engine() -> chess.engine.SimpleEngine:
    """One engine process per worker, opened on first use."""
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(settings.ENGINE_PATH)
        # python-chess talks to Stockfish on a non-daemon thread, which Python waits for at exit before plain
        # atexit handlers run. This hook (the one concurrent.futures uses) runs first, so scripts and management
        # commands that use the engine can exit.
        threading._register_atexit(close_engine)
    return _engine


def _cached(fen: str) -> PositionAnalysis | None:
    return PositionAnalysis.objects.filter(fen=fen).first()


def _run(board: chess.Board) -> dict:
    if board.is_checkmate():
        return {"depth": 0, "lines": [], "cp": None, "mate": 0, "engine_version": ""}
    if board.is_game_over(claim_draw=False):
        return {"depth": 0, "lines": [], "cp": 0, "mate": None, "engine_version": ""}
    eng = get_engine()
    infos = eng.analyse(board, chess.engine.Limit(depth=settings.ENGINE_DEPTH), multipv=settings.ENGINE_MULTIPV)
    lines = []
    for info in infos:
        score = info["score"].relative
        lines.append({"uci": [m.uci() for m in info.get("pv", [])], "cp": score.score(), "mate": score.mate()})
    return {"depth": settings.ENGINE_DEPTH, "lines": lines, "cp": lines[0]["cp"], "mate": lines[0]["mate"],
            "engine_version": eng.id.get("name", "")}


def analyse(board: chess.Board) -> PositionAnalysis:
    fen = normalize_fen(board)
    hit = _cached(fen)
    if hit:
        return hit
    data = _run(board)
    try:
        with transaction.atomic():
            return PositionAnalysis.objects.create(fen=fen, **data)
    except IntegrityError:  # another worker stored it first
        return PositionAnalysis.objects.get(fen=fen)


def close_engine() -> None:
    """Quit the engine process. Called when a test session or a Celery worker shuts down."""
    global _engine
    if _engine is not None:
        _engine.quit()
        _engine = None
