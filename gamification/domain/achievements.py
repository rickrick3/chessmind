"""Achievements of the MVP. Each is earned once."""
from dataclasses import dataclass

CODES = ("first_lesson", "first_unit", "streak_3", "streak_7", "streak_30", "perfect_10")


@dataclass(frozen=True)
class ProgressStats:
    lessons_completed: int
    units_completed: int
    perfect_lessons: int  # lessons whose best first-try accuracy is 100%


def earned(stats: ProgressStats, current_streak: int, have: set[str]) -> list[str]:
    """Codes newly earned, in CODES order."""
    met = {
        "first_lesson": stats.lessons_completed >= 1,
        "first_unit": stats.units_completed >= 1,
        "streak_3": current_streak >= 3,
        "streak_7": current_streak >= 7,
        "streak_30": current_streak >= 30,
        "perfect_10": stats.perfect_lessons >= 10,
    }
    return [code for code in CODES if met[code] and code not in have]
