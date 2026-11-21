import pytest

from gamification.domain.achievements import ProgressStats, earned
from gamification.domain.levels import level_floor, level_for
from gamification.domain.xp import XpContext, XpRules, xp_for_attempt


@pytest.mark.parametrize("ctx,expected", [
    (XpContext(True, 0.85, True, False, False), [("lesson_first", 10)]),
    (XpContext(True, 0.95, True, False, False), [("lesson_first", 10), ("accuracy_bonus", 5)]),
    (XpContext(True, 0.90, True, False, False), [("lesson_first", 10), ("accuracy_bonus", 5)]),
    (XpContext(True, 0.70, False, False, False), [("lesson_replay", 3)]),
    (XpContext(True, 0.70, False, False, True), []),
    (XpContext(True, 0.95, False, False, True), [("accuracy_bonus", 5)]),
    (XpContext(True, 0.95, False, True, False), [("lesson_replay", 3)]),
    (XpContext(False, 1.0, True, False, False), []),
])
def test_xp_rules(ctx, expected):
    assert xp_for_attempt(ctx, XpRules()) == expected


def test_rules_come_from_settings(settings):
    settings.XP_LESSON_FIRST = 20
    settings.XP_LESSON_REPLAY = 1
    rules = XpRules.from_settings()
    assert xp_for_attempt(XpContext(True, 0.5, True, False, False), rules) == [("lesson_first", 20)]
    assert xp_for_attempt(XpContext(True, 0.5, False, False, False), rules) == [("lesson_replay", 1)]


@pytest.mark.parametrize("xp,level", [(0, 1), (49, 1), (50, 2), (149, 2), (150, 3), (299, 3), (300, 4), (500, 5)])
def test_levels(xp, level):
    assert level_for(xp) == level


def test_level_floor():
    assert [level_floor(n) for n in (1, 2, 3, 4, 5)] == [0, 50, 150, 300, 500]


def test_achievements_once_and_in_order():
    stats = ProgressStats(lessons_completed=1, units_completed=1, perfect_lessons=10)
    assert earned(stats, 3, set()) == ["first_lesson", "first_unit", "streak_3", "perfect_10"]
    assert earned(stats, 3, {"first_lesson", "first_unit", "streak_3", "perfect_10"}) == []
    assert earned(ProgressStats(0, 0, 9), 2, set()) == []
    assert earned(ProgressStats(5, 0, 0), 30, {"first_lesson"}) == ["streak_3", "streak_7", "streak_30"]
