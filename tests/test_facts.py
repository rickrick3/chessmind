import chess
import pytest

from analysis.engine import analyse
from analysis.facts import build_fact_packet

pytestmark = pytest.mark.django_db


def packet(fen, san, ply=1):
    b = chess.Board(fen)
    move = b.parse_san(san)
    before = analyse(b)
    after_board = b.copy()
    after_board.push(move)
    return build_fact_packet(b, move, before, analyse(after_board), ply), after_board


def test_hanging_queen_detected():
    p, _ = packet("4k3/8/8/2n5/8/8/8/3QK3 w - - 0 1", "Qd3")
    assert p.hanging_after == ["queen on d3"]
    assert p.grade == "blunder" and p.key_moment


def test_knight_fork_detected():
    p, _ = packet("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "Nc7+")
    assert p.forks == ["king on e8", "rook on a8"]
    assert p.is_check


def test_capture_named():
    p, _ = packet("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3", "Bxf7+")
    assert p.captured == "pawn" and p.mover == "white"


def test_best_move_is_none_when_played():
    b = chess.Board()
    best_uci = analyse(b).lines[0]["uci"][0]
    p, _ = packet(chess.STARTING_FEN, b.san(chess.Move.from_uci(best_uci)))
    assert p.best_san is None and p.grade == "best"


def test_replies_are_opponent_moves_in_san():
    p, after = packet(chess.STARTING_FEN, "e4")
    assert 1 <= len(p.replies_san) <= 3
    for san in p.replies_san:
        after.parse_san(san)  # raises if illegal


def test_best_line_starts_from_position_before():
    p, _ = packet("4k3/8/8/2n5/8/8/8/3QK3 w - - 0 1", "Qd3")
    assert p.best_san == p.best_line_san[0] and len(p.best_line_san) <= 6
    chess.Board("4k3/8/8/2n5/8/8/8/3QK3 w - - 0 1").parse_san(p.best_san)


def test_material_diff_from_mover_side():
    p, _ = packet("4k3/8/8/2n5/8/8/8/3QK3 w - - 0 1", "Qd3")
    assert p.material_diff == 6  # queen 9 vs knight 3


def test_allowed_san_covers_all_lists():
    p, _ = packet("4k3/8/8/2n5/8/8/8/3QK3 w - - 0 1", "Qd3")
    assert {p.san, p.best_san, *p.best_line_san, *p.replies_san} <= p.allowed_san()
