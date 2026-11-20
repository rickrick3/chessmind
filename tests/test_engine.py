import chess
import pytest

from analysis import engine as engine_mod
from analysis.engine import analyse, normalize_fen
from analysis.models import PositionAnalysis

pytestmark = pytest.mark.django_db
FOOLS_MATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


def test_normalize_drops_counters():
    b = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert normalize_fen(b) == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"


def test_analyse_returns_three_lines():
    pa = analyse(chess.Board())
    assert len(pa.lines) == 3 and pa.depth == 8
    assert all(line["uci"] and chess.Move.from_uci(line["uci"][0]) in chess.Board().legal_moves for line in pa.lines)


def test_analyse_is_cached(mocker):
    analyse(chess.Board())
    spy = mocker.spy(engine_mod, "get_engine")
    analyse(chess.Board())
    spy.assert_not_called()


def test_checkmate_position_needs_no_engine(mocker):
    spy = mocker.spy(engine_mod, "get_engine")
    pa = analyse(chess.Board(FOOLS_MATE))
    assert pa.lines == [] and pa.mate_for_side_to_move() == 0
    spy.assert_not_called()


def test_stalemate_is_a_draw(mocker):
    spy = mocker.spy(engine_mod, "get_engine")
    pa = analyse(chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"))
    assert pa.best_cp() == 0 and pa.mate_for_side_to_move() is None
    spy.assert_not_called()


def test_winning_position_has_positive_score_for_side_to_move():
    pa = analyse(chess.Board("4k3/8/8/8/8/8/8/QQQQK3 w - - 0 1"))
    assert (pa.best_cp() or 0) > 500 or (pa.mate_for_side_to_move() or 0) > 0


def test_concurrent_insert_same_fen_keeps_one_row(mocker):
    existing = PositionAnalysis.objects.create(fen=normalize_fen(chess.Board()), depth=8, lines=[], cp=20)
    mocker.patch.object(engine_mod, "_cached", return_value=None)
    pa = analyse(chess.Board())
    assert pa.pk == existing.pk and PositionAnalysis.objects.count() == 1
