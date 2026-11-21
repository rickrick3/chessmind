"""Engine checks on a lesson: every answer the lesson accepts must be a good move. Stockfish decides."""
import chess

from analysis import engine
from analysis.grading import grade_move, mover_wp_after, wp_of

from .domain.schema import Issue, player_move_indexes

GOOD = ("best", "good")


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
