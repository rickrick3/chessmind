"""Re-score a finished lesson from the moves the learner tried. The browser's own verdict is never trusted.

A submission is a list of {"id", "tries", "hints", "ms"}:
  find_move  tries: [uci, ...]            hints: int
  choice     tries: [option index, ...]   hints: int
  play_line  tries: [[uci, ...], ...]     hints: [int, ...]  (one list per learner move)
"""
from dataclasses import dataclass, field

import chess

from curriculum.domain.schema import player_move_indexes

MAX_TRIES = 10
MAX_ENTRIES = 50
SCORED = ("find_move", "choice", "play_line")


class InvalidResult(ValueError):
    """The submission does not fit the lesson (shape, ids, sizes or illegal moves)."""


@dataclass(frozen=True)
class StepScore:
    step_id: str
    step_type: str
    items: int
    correct_items: int
    cleared: bool
    tries: list = field(default_factory=list)
    hints: int | list = 0
    ms: int = 0
    skills: list = field(default_factory=list)

    @property
    def correct(self) -> bool:
        return self.items > 0 and self.correct_items == self.items


@dataclass(frozen=True)
class Scored:
    steps: list[StepScore]
    items: int
    correct_items: int
    accuracy: float
    completed: bool


def _int(value, low=0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < low:
        raise InvalidResult(f"expected an integer >= {low}, got {value!r}")
    return value


def _tries(value) -> list:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_TRIES:
        raise InvalidResult(f"tries must be a list of 1 to {MAX_TRIES}")
    return value


def _check_legal(board: chess.Board, ucis: list) -> None:
    for uci in ucis:
        try:
            move = chess.Move.from_uci(uci) if isinstance(uci, str) else None
        except ValueError:
            move = None
        if move is None or move not in board.legal_moves:
            raise InvalidResult(f"illegal move {uci!r}")


def _score_find_move(step, e) -> tuple[int, int, bool]:
    tries = _tries(e.get("tries"))
    _check_legal(chess.Board(step["fen"]), tries)
    right = set(step["accept"]) | {g["uci"] for g in step.get("also_good", [])}
    hints = _int(e.get("hints", 0))
    return 1, int(tries[0] in right and hints == 0), tries[-1] in right


def _score_choice(step, e) -> tuple[int, int, bool]:
    tries = _tries(e.get("tries"))
    for t in tries:
        if _int(t) >= len(step["options"]):
            raise InvalidResult(f"option {t} out of range")
    hints = _int(e.get("hints", 0))
    return 1, int(tries[0] == step["answer"] and hints == 0), tries[-1] == step["answer"]


def _score_play_line(step, e) -> tuple[int, int, bool]:
    players = player_move_indexes(step)
    tries, hints = e.get("tries"), e.get("hints")
    if not isinstance(tries, list) or len(tries) != len(players):
        raise InvalidResult(f"play_line needs {len(players)} lists of tries")
    if not isinstance(hints, list) or len(hints) != len(players):
        raise InvalidResult(f"play_line needs {len(players)} hint counts")
    board = chess.Board(step["fen"])
    alts = step.get("also_accept", {})
    correct, cleared = 0, True
    for i, uci in enumerate(step["moves"]):
        if i in players:
            k = players.index(i)
            attempts = _tries(tries[k])
            _check_legal(board, attempts)
            right = {uci, *alts.get(str(i), [])}
            correct += int(attempts[0] in right and _int(hints[k]) == 0)
            cleared = cleared and attempts[-1] in right
        board.push(chess.Move.from_uci(uci))
    return len(players), correct, cleared


SCORERS = {"find_move": _score_find_move, "choice": _score_choice, "play_line": _score_play_line}


def score_attempt(content: dict, submitted) -> Scored:
    if not isinstance(submitted, list) or len(submitted) > MAX_ENTRIES:
        raise InvalidResult(f"steps must be a list of at most {MAX_ENTRIES}")
    steps = {s["id"]: s for s in content["steps"]}
    by_id: dict[str, dict] = {}
    for e in submitted:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            raise InvalidResult("each entry needs an id")
        if e["id"] not in steps:
            raise InvalidResult(f"unknown step {e['id']!r}")
        if e["id"] in by_id:
            raise InvalidResult(f"step {e['id']!r} sent twice")
        _int(e.get("ms", 0))
        by_id[e["id"]] = e

    scores: list[StepScore] = []
    for step in content["steps"]:
        kind = step["type"]
        if kind not in SCORED:
            continue
        e = by_id.get(step["id"])
        if e is None:
            n = len(player_move_indexes(step)) if kind == "play_line" else 1
            scores.append(StepScore(step["id"], kind, n, 0, False, skills=step.get("skills", [])))
            continue
        items, correct, cleared = SCORERS[kind](step, e)
        scores.append(StepScore(step["id"], kind, items, correct, cleared, e.get("tries"), e.get("hints", 0),
                                e.get("ms", 0), step.get("skills", [])))

    items = sum(s.items for s in scores)
    correct_items = sum(s.correct_items for s in scores)
    accuracy = round(correct_items / items, 4) if items else 1.0
    min_accuracy = (content.get("completion") or {}).get("min_accuracy", 0)
    completed = all(s.cleared for s in scores) and accuracy >= min_accuracy
    return Scored(scores, items, correct_items, accuracy, completed)
