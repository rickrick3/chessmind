"""Daily streak, counted in the learner's own local days: any XP on a day counts that day."""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class Streak:
    current: int  # length of the run of days ending at last_active
    longest: int
    last_active: date | None


def advance(s: Streak, day: date) -> Streak:
    """The streak after earning XP on `day`. The day after the last active day adds one; a gap restarts at 1."""
    if s.last_active is not None and day <= s.last_active:
        return s
    current = s.current + 1 if s.last_active == day - ONE_DAY else 1
    return Streak(current, max(s.longest, current), day)


def displayed(s: Streak, today: date) -> int:
    """What the learner sees: the run is still alive today and yesterday, 0 once a day was missed."""
    return s.current if s.last_active is not None and s.last_active >= today - ONE_DAY else 0


def from_dates(days: Iterable[date]) -> Streak:
    s = Streak(0, 0, None)
    for day in sorted(set(days)):
        s = advance(s, day)
    return s
