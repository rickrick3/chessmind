"""Facts about one move, computed in code. The AI may only put these into words."""
from dataclasses import dataclass

import chess

from .grading import grade_move, is_key_moment, mover_wp_after, wp_of

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}


@dataclass(frozen=True)
class FactPacket:
    ply: int
    mover: str
    san: str
    grade: str
    key_moment: bool
    wp_before: float
    wp_after: float
    best_san: str | None
    best_line_san: list[str]
    replies_san: list[str]
    is_check: bool
    captured: str | None
    hanging_after: list[str]
    forks: list[str]
    material_diff: int

    def allowed_san(self) -> set[str]:
        moves = {self.san, *self.best_line_san, *self.replies_san}
        if self.best_san:
            moves.add(self.best_san)
        return moves


def _name(board: chess.Board, square: int) -> str:
    return f"{chess.piece_name(board.piece_type_at(square))} on {chess.square_name(square)}"


def _line_san(board: chess.Board, ucis: list[str], limit: int) -> list[str]:
    b, out = board.copy(), []
    for u in ucis[:limit]:
        move = chess.Move.from_uci(u)
        if move not in b.legal_moves:
            break
        out.append(b.san(move))
        b.push(move)
    return out


def _material(board: chess.Board, color: bool) -> int:
    return sum(VALUES[p] * len(board.pieces(p, color)) for p in VALUES if p != chess.KING)


def _hanging(board: chess.Board, color: bool) -> list[str]:
    out = []
    for sq, piece in board.piece_map().items():
        if piece.color == color and piece.piece_type != chess.KING:
            if board.attackers(not color, sq) and not board.attackers(color, sq):
                out.append((-VALUES[piece.piece_type], sq))
    return [_name(board, sq) for _v, sq in sorted(out)]


def _forks(board: chess.Board, square: int, color: bool) -> list[str]:
    targets = [
        (-VALUES[board.piece_type_at(t)], t)
        for t in board.attacks(square)
        if board.color_at(t) == (not color) and VALUES[board.piece_type_at(t)] > 1
    ]
    return [_name(board, t) for _v, t in sorted(targets)] if len(targets) >= 2 else []


def build_fact_packet(board_before: chess.Board, move: chess.Move, before, after, ply: int) -> FactPacket:
    color = board_before.turn
    after_board = board_before.copy()
    after_board.push(move)
    best_line = before.lines[0]["uci"] if before.lines else []
    is_best = bool(best_line) and best_line[0] == move.uci()
    wp_before, wp_after = wp_of(before), mover_wp_after(after)
    grade = grade_move(wp_before, wp_after, is_best)
    captured = None
    if board_before.is_capture(move):
        cap_sq = move.to_square if not board_before.is_en_passant(move) else chess.square(
            chess.square_file(move.to_square), chess.square_rank(move.from_square))
        captured = chess.piece_name(board_before.piece_type_at(cap_sq))
    best_line_san = _line_san(board_before, best_line, 6)
    return FactPacket(
        ply=ply,
        mover="white" if color == chess.WHITE else "black",
        san=board_before.san(move),
        grade=grade,
        key_moment=is_key_moment(grade),
        wp_before=round(wp_before, 1),
        wp_after=round(wp_after, 1),
        best_san=None if is_best or not best_line_san else best_line_san[0],
        best_line_san=best_line_san,
        replies_san=[s[0] for s in (_line_san(after_board, line["uci"], 1) for line in after.lines[:3]) if s],
        is_check=after_board.is_check(),
        captured=captured,
        hanging_after=_hanging(after_board, color),
        forks=_forks(after_board, move.to_square, color),
        material_diff=_material(after_board, color) - _material(after_board, not color),
    )
