"""From evidence to a skill estimate with its confidence (design 5.7). Pure: no database.

Puzzle and lesson evidence are never mixed into one number: lesson steps have no rating. An area with enough puzzle
observations gets a performance rating shown as a range; otherwise enough lesson answers give a success rate;
otherwise there is not enough evidence yet.
"""
import math
from dataclasses import dataclass, fields
from datetime import date

from django.conf import settings

from puzzles.domain.glicko2 import expected

PERFORMANCE_SPREAD = 400  # the performance stays within this many points of the puzzles it was measured on


@dataclass(frozen=True)
class SkillRules:
    puzzle_window: int = 40
    lesson_window: int = 30
    min_observations: int = 10
    reliable_observations: int = 25
    reliable_days: int = 3
    improving_split: int = 15
    improving_points: int = 100
    improving_rate: float = 0.20
    lesson_weak: float = 0.5
    lesson_strong: float = 0.85
    repeated_misses: int = 3
    repeated_days: int = 14

    @classmethod
    def from_settings(cls) -> "SkillRules":
        return cls(**{f.name: getattr(settings, f"SKILL_{f.name.upper()}") for f in fields(cls)})


@dataclass(frozen=True)
class Observation:
    success: bool
    local_date: date
    difficulty: int | None = None  # the puzzle's rating; None for a lesson answer
    learner_rating: float | None = None  # the learner's puzzle rating before the attempt
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Estimate:
    basis: str  # "puzzle", "lesson" or "none"
    value: float | None  # a performance rating, or a success rate from 0 to 1
    low: int | None
    high: int | None
    observations: int
    days: int
    confidence: str  # "none", "early" or "reliable"
    comparison: str  # "", "stronger", "same" or "weaker" (against the overall puzzle rating)


def performance(results: list[tuple[int, bool]]) -> float:
    """The rating R at which the expected score against these puzzles equals the number solved."""
    ratings = [r for r, _ in results]
    lo, hi = min(ratings) - PERFORMANCE_SPREAD, max(ratings) + PERFORMANCE_SPREAD
    solved = sum(1 for _, ok in results if ok)
    if solved == 0:
        return float(lo)
    if solved == len(results):
        return float(hi)
    while hi - lo > 0.5:
        mid = (lo + hi) / 2
        if sum(expected(mid, r, 0) for r in ratings) < solved:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def margin(n: int) -> int:
    return int(round(350 / math.sqrt(n), -1))


def round50(x: float) -> int:
    return int(round(x / 50) * 50)


def confidence(n: int, days: int, rules: SkillRules) -> str:
    if n < rules.min_observations:
        return "none"
    if n >= rules.reliable_observations and days >= rules.reliable_days:
        return "reliable"
    return "early"


def _days(observations: list[Observation]) -> int:
    return len({o.local_date for o in observations})


def estimate(puzzle_obs: list[Observation], lesson_obs: list[Observation], overall: float | None,
             rules: SkillRules) -> Estimate:
    """Observations are ordered oldest first; only the newest ones of the window count."""
    if len(puzzle_obs) >= rules.min_observations:
        window = puzzle_obs[-rules.puzzle_window:]
        n, value = len(window), performance([(o.difficulty, o.success) for o in window])
        m = margin(n)
        comparison = ""
        if overall is not None:
            comparison = "weaker" if value < overall - m else "stronger" if value > overall + m else "same"
        days = _days(window)
        return Estimate("puzzle", value, round50(value - m), round50(value + m), n, days,
                        confidence(n, days, rules), comparison)
    if len(lesson_obs) >= rules.min_observations:
        window = lesson_obs[-rules.lesson_window:]
        n, days = len(window), _days(window)
        rate = sum(1 for o in window if o.success) / n
        return Estimate("lesson", rate, None, None, n, days, confidence(n, days, rules), "")
    n = max(len(puzzle_obs), len(lesson_obs))
    return Estimate("none", None, None, None, n, 0, "none", "")
