"""Re-score a puzzle from the moves the learner played. The browser's own verdict is never trusted. Pure.

The finish body is {"played": [uci, ...], "hints": int, "solution_shown": bool, "ms": int}: the learner's moves up to
the moment the outcome was decided. Rated play stops at the first wrong move, so a wrong move is always the last one.
Any checkmating move counts as correct, as on Lichess.
"""
from dataclasses import dataclass

import chess

from learning.domain.scoring import MAX_MS

MAX_HINTS = 10


class InvalidPuzzleResult(ValueError):
    """The submission does not fit the puzzle (shape, sizes, illegal or impossible moves)."""


@dataclass(frozen=True)
class Outcome:
    solved: bool
    played: tuple[str, ...]
    hints: int
    solution_shown: bool
    ms: int


def learner_move_count(moves: list[str]) -> int:
    return len(moves) // 2


def _int(value, high: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= high:
        raise InvalidPuzzleResult(f"expected an integer from 0 to {high}, got {value!r}")
    return value


def score_puzzle(fen: str, moves: list[str], body: dict) -> Outcome:
    if not isinstance(body, dict):
        raise InvalidPuzzleResult("the body must be an object")
    played, shown = body.get("played"), body.get("solution_shown", False)
    hints, ms = _int(body.get("hints", 0), MAX_HINTS), _int(body.get("ms", 0), MAX_MS)
    if not isinstance(shown, bool):
        raise InvalidPuzzleResult("solution_shown must be true or false")
    count = learner_move_count(moves)
    if not isinstance(played, list) or len(played) > count or not all(isinstance(u, str) for u in played):
        raise InvalidPuzzleResult(f"played must be a list of at most {count} moves")

    board = chess.Board(fen)
    board.push_uci(moves[0])
    wrong = mated = False
    for k, uci in enumerate(played):
        if wrong or mated:
            raise InvalidPuzzleResult("no move can follow a wrong or mating move")
        try:
            move = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise InvalidPuzzleResult(f"not a move: {uci!r}") from exc
        if move not in board.legal_moves:
            raise InvalidPuzzleResult(f"illegal move {uci!r}")
        board.push(move)
        mated = board.is_checkmate()
        if uci != moves[2 * k + 1] and not mated:
            wrong = True
            continue
        if not mated and 2 * k + 2 < len(moves):
            board.pop()
            board.push_uci(moves[2 * k + 1])
            board.push_uci(moves[2 * k + 2])  # the opponent's reply from the solution

    if wrong or hints > 0 or shown:
        solved = False
    elif mated or len(played) == count:
        solved = True
    else:
        raise InvalidPuzzleResult("the puzzle is not decided yet")
    return Outcome(solved, tuple(played), hints, shown, ms)
