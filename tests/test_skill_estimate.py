"""Skill estimates and confidence: pure, no database."""
import pytest

from skills.domain.estimate import SkillRules, confidence, estimate, margin, performance, round50
from tests.skill_obs import obs

R = SkillRules()


def test_rules_from_settings():
    assert SkillRules.from_settings() == R and (R.puzzle_window, R.min_observations, R.reliable_days) == (40, 10, 3)


def test_performance():
    assert performance([(1500, True), (1500, False)]) == pytest.approx(1500, abs=1)
    assert performance([(1200, True), (1400, True)]) == 1800 and performance([(1200, False), (1400, False)]) == 800
    assert performance([(1500, True), (1500, True), (1500, False)]) > performance([(1500, True), (1500, False)])


def test_margin_and_round50():
    assert (margin(10), margin(25), margin(40)) == (110, 70, 60) and (round50(1420), round50(1580)) == (1400, 1600)


def test_confidence_function():
    assert (confidence(9, 5, R), confidence(24, 5, R), confidence(25, 2, R), confidence(25, 3, R)) == (
        "none", "early", "early", "reliable")


def test_not_enough_evidence():
    e = estimate(obs(9, solved=range(5)), [], 1500, R)
    assert (e.basis, e.value, e.confidence, e.observations) == ("none", None, "none", 9)


@pytest.mark.parametrize("n,days,expected_conf", [(25, 2, "early"), (25, 3, "reliable"), (10, 5, "early")])
def test_confidence_levels(n, days, expected_conf):
    assert estimate(obs(n, solved=range(0, n, 2), days=days), [], 1500, R).confidence == expected_conf


def test_puzzle_basis_wins_at_ten():
    assert estimate(obs(10, solved={1}), obs(30, solved=range(30)), None, R).basis == "puzzle"
    e = estimate(obs(9), obs(12, solved=range(6)), None, R)
    assert (e.basis, e.value, e.observations, e.low, e.comparison) == ("lesson", 0.5, 12, None, "")


def test_window_uses_newest_40():
    e = estimate(obs(50, solved=range(10, 50)), [], None, R)
    assert e.value == 1900 and e.observations == 40


def test_range_and_comparison():
    e = estimate(obs(20, solved=range(10)), [], 1800, R)
    assert e.value == pytest.approx(1500, abs=1) and (e.low, e.high, e.comparison) == (1400, 1600, "weaker")
    assert estimate(obs(20, solved=range(10)), [], 1560, R).comparison == "same"
    assert estimate(obs(20, solved=range(10)), [], 1300, R).comparison == "stronger"
    assert estimate(obs(20, solved=range(10)), [], None, R).comparison == ""
