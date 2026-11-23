"""The server's check of a puzzle result: pure, no database."""
import pytest

from puzzles.domain.solution import InvalidPuzzleResult, learner_move_count, score_puzzle
from tests.puzzle_data import ALT_MATE, MATE2, PROMOTION


def body(played, hints=0, shown=False, ms=1000):
    return {"played": played, "hints": hints, "solution_shown": shown, "ms": ms}


def test_learner_move_count():
    assert learner_move_count(MATE2["moves"]) == 2 and learner_move_count(ALT_MATE["moves"]) == 1


def test_solved_line():
    out = score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6", "f7f8"], ms=9000))
    assert out.solved is True and out.played == ("a2e6", "f7f8") and out.ms == 9000


@pytest.mark.parametrize("data", [ALT_MATE, PROMOTION])
def test_alternative_mate_solves(data):
    assert score_puzzle(data["fen"], data["moves"], body([data["alternative"]])).solved is True


def test_wrong_move_is_missed():
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body([MATE2["wrong_first"]])).solved is False
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6", MATE2["wrong_second"]])).solved is False


def test_hint_or_solution_is_missed():
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body([], hints=1)).solved is False
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6"], shown=True)).solved is False


@pytest.mark.parametrize("b", [
    body([MATE2["illegal_first"]]), body([MATE2["wrong_first"], "a2e6"]), body(["a2e6", "f7f8", "f8f7"]),
    body(["a2e6"]), body([]), body(["a2e6"], hints=True), body([], hints=11), {"played": "a2e6"},
    body(["a2e6", "f7f8"], ms=-1), body([42]),
])
def test_rejects(b):
    with pytest.raises(InvalidPuzzleResult):
        score_puzzle(MATE2["fen"], MATE2["moves"], b)
