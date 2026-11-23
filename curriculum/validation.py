"""Engine checks on a lesson: every answer the lesson accepts must be a good move. Stockfish decides."""
import chess

from analysis import engine
from analysis.grading import grade_move, mover_wp_after, wp_of

from .domain.schema import Issue, player_move_indexes

GOOD = ("best", "good")
EQUAL_CP = 50  # an engine line this close to the best one is as good an answer


def _as_good_as_best(best: dict, line: dict) -> bool:
    if best["mate"] is not None:
        return line["mate"] == best["mate"]
    return line["cp"] is not None and best["cp"] - line["cp"] <= EQUAL_CP


def _unaccepted_answers(board: chess.Board, taken: set[str]) -> list[str]:
    """Moves from the engine's lines that are as good as its best one but the step doesn't accept."""
    lines = [line for line in engine.analyse(board).lines if line.get("uci")]
    if not lines:
        return []
    return [line["uci"][0] for line in lines if line["uci"][0] not in taken and _as_good_as_best(lines[0], line)]


def grade(board: chess.Board, uci: str) -> str:
    """The grade game review would give this move: best, good, inaccuracy, mistake or blunder."""
    before = engine.analyse(board)
    after_board = board.copy()
    after_board.push(chess.Move.from_uci(uci))
    after = engine.analyse(after_board)
    is_best = bool(before.lines) and before.lines[0]["uci"][:1] == [uci]
    return grade_move(wp_of(before), mover_wp_after(after), is_best)


def _san(board: chess.Board, uci: str) -> str:
    return board.san(chess.Move.from_uci(uci))


def engine_issues(content: dict) -> list[Issue]:
    """Run only on content that passed check_structure: every move here is legal."""
    issues: list[Issue] = []
    for step in content["steps"]:
        sid, kind = step["id"], step["type"]
        if kind == "find_move":
            board = chess.Board(step["fen"])
            for uci in list(step["accept"]) + [g["uci"] for g in step.get("also_good", [])]:
                g = grade(board, uci)
                if g not in GOOD:
                    issues.append(Issue("answer_refuted", "fail", f"{_san(board, uci)} grades {g}", sid))
            for w in step.get("wrong", []):
                g = grade(board, w["uci"])
                if g in GOOD:
                    issues.append(Issue("wrong_move_is_fine", "warn", f"{_san(board, w['uci'])} grades {g}", sid))
            taken = set(step["accept"]) | {g["uci"] for g in step.get("also_good", [])}
            for uci in _unaccepted_answers(board, taken):
                issues.append(Issue("unaccepted_good_answer", "warn",
                                    f"{_san(board, uci)} is as good as the answer", sid))
        elif kind == "play_line":
            issues += _line_issues(step)
    return issues


def _line_issues(step: dict) -> list[Issue]:
    issues: list[Issue] = []
    board = chess.Board(step["fen"])
    players = set(player_move_indexes(step))
    alts = step.get("also_accept", {})
    for i, uci in enumerate(step["moves"]):
        if i in players:
            for candidate in [uci, *alts.get(str(i), [])]:
                g = grade(board, candidate)
                if g == "inaccuracy":
                    issues.append(Issue("inaccurate_line_move", "warn",
                                        f"move {i + 1} {_san(board, candidate)} grades {g}", step["id"]))
                elif g not in GOOD:
                    issues.append(Issue("line_move_refuted", "fail",
                                        f"move {i + 1} {_san(board, candidate)} grades {g}", step["id"]))
        board.push(chess.Move.from_uci(uci))
    return issues
