"""Glicko-2 (Glickman, "Example of the Glicko-2 system"): pure, no database."""
import pytest

from puzzles.domain.glicko2 import Game, Rating, expected, idle, rate


def test_glickman_example():
    r = rate(Rating(1500, 200, 0.06), [Game(1400, 30, 1), Game(1550, 100, 0), Game(1700, 300, 0)], tau=0.5)
    assert r.rating == pytest.approx(1464.06, abs=0.01)
    assert r.rd == pytest.approx(151.52, abs=0.01)
    assert r.volatility == pytest.approx(0.05999, abs=1e-5)


def test_win_raises_and_loss_lowers():
    p = Rating(1500, 100, 0.06)
    assert rate(p, [Game(1500, 80, 1)], 0.5).rating > 1500 > rate(p, [Game(1500, 80, 0)], 0.5).rating


def test_no_games_only_grows_rd():
    p = Rating(1500, 100, 0.06)
    r = rate(p, [], 0.5)
    assert r.rating == 1500 and r.rd > 100 and r.volatility == 0.06


def test_idle_grows_rd_and_caps():
    p = Rating(1500, 50, 0.06)
    assert idle(p, 0, 350) == p and idle(p, 10, 350).rd > 50 and idle(p, 100_000, 350).rd == 350


def test_expected():
    assert expected(1500, 1500, 0) == pytest.approx(0.5) and expected(1700, 1500, 80) > 0.5
