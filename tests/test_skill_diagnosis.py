"""Strengths and weaknesses (PRD 5.2): pure, no database."""
from datetime import date, timedelta

from skills.domain.diagnosis import repeated_mistake, status
from skills.domain.estimate import Observation, SkillRules, estimate
from tests.skill_obs import obs

R = SkillRules()


def test_single_miss_is_never_a_weakness():
    e = estimate(obs(1), [], 1600, R)
    assert status(e, obs(1), [], R) == ""


def test_emerging_then_confirmed_weakness():
    few = obs(12, solved={3, 9}, days=2)
    assert status(estimate(few, [], 1600, R), few, [], R) == "emerging_weakness"
    many = obs(30, solved={2, 8, 16, 22, 28}, days=3)
    assert status(estimate(many, [], 1600, R), many, [], R) == "confirmed_weakness"


def test_stable_strength():
    o = obs(30, solved=set(range(30)) - {0, 15, 29}, days=4)
    assert status(estimate(o, [], 1300, R), o, [], R) == "stable_strength"


def test_strength_needs_reliable_confidence():
    o = obs(12, solved=set(range(12)) - {0}, days=2)
    assert status(estimate(o, [], 1300, R), o, [], R) == ""


def test_improving():
    o = obs(30, solved={0, 5, 10} | set(range(15, 27)), days=4)
    assert status(estimate(o, [], 1500, R), o, [], R) == "improving"


def test_lesson_basis_states():
    weak = obs(12, solved={0, 4, 8, 11}, days=2)
    assert status(estimate([], weak, None, R), [], weak, R) == "emerging_weakness"
    strong = obs(30, solved=set(range(30)) - {5, 17, 25}, days=3)
    assert status(estimate([], strong, None, R), [], strong, R) == "stable_strength"


def test_repeated_mistake_counts_only_expected_solves():
    today = date(2026, 11, 22)

    def misses(diff, ago):
        return [Observation(False, today - timedelta(days=d), diff, 1500) for d in ago]

    assert repeated_mistake(misses(1400, (0, 3, 10)), today, R) is True
    assert repeated_mistake(misses(1700, (0, 3, 10)), today, R) is False
    assert repeated_mistake(misses(1400, (0, 10, 20)), today, R) is False


def test_small_swings_are_not_improving():
    # 6 of 15, then 9 of 15: about 140 points better, within the noise of 15 puzzles each.
    o = obs(30, solved={0, 2, 4, 6, 8, 10} | {15, 16, 17, 19, 21, 23, 25, 27, 29}, days=4)
    assert status(estimate(o, [], 1500, R), o, [], R) == ""
