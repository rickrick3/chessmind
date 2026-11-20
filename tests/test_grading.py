import pytest

from analysis.grading import grade_move, is_key_moment, mover_wp_after, wp_of
from analysis.models import PositionAnalysis
from analysis.grading import win_percent


def test_win_percent_values():
    assert win_percent(0, None) == pytest.approx(50.0)
    assert win_percent(100, None) == pytest.approx(59.1, abs=0.1)
    assert win_percent(None, 3) == 100.0
    assert win_percent(None, -2) == 0.0
    assert win_percent(None, 0) == 0.0  # side to move is mated


@pytest.mark.parametrize("before,after,best,expected", [
    (60, 60, True, "best"), (60, 52, False, "good"), (60, 50, False, "inaccuracy"),
    (60, 40, False, "mistake"), (60, 30, False, "blunder")])
def test_grade_thresholds(before, after, best, expected):
    assert grade_move(before, after, best) == expected


@pytest.mark.parametrize("grade,expected", [
    ("best", False), ("good", False), ("inaccuracy", True), ("mistake", True), ("blunder", True)])
def test_key_moment(grade, expected):
    assert is_key_moment(grade) is expected


def test_mover_wp_after_flips_point_of_view():
    after = PositionAnalysis(fen="x", depth=8, cp=100, mate=None)  # opponent to move, +1 for them
    assert mover_wp_after(after) == pytest.approx(100 - 59.1, abs=0.1)


def test_mover_wp_after_when_opponent_is_mated():
    after = PositionAnalysis(fen="x", depth=0, cp=None, mate=0)
    assert mover_wp_after(after) == 100.0
    assert wp_of(after) == 0.0
