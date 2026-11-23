from datetime import date, datetime
from zoneinfo import ZoneInfo

from gamification.domain.streak import Streak, advance, displayed, from_dates

EMPTY = Streak(0, 0, None)


def test_first_day():
    assert advance(EMPTY, date(2026, 11, 21)) == Streak(1, 1, date(2026, 11, 21))


def test_same_day_counts_once():
    s = advance(EMPTY, date(2026, 11, 21))
    assert advance(s, date(2026, 11, 21)) == s


def test_streak_across_local_midnight_same_utc_day():
    paris = ZoneInfo("Europe/Paris")
    d1 = datetime(2026, 11, 21, 23, 30, tzinfo=paris).date()
    d2 = datetime(2026, 11, 22, 0, 10, tzinfo=paris).date()
    assert advance(advance(EMPTY, d1), d2).current == 2


def test_streak_across_dst_change():
    # Europe/Paris moves its clocks on 2027-03-28; the local days are still consecutive.
    s = advance(advance(EMPTY, date(2027, 3, 27)), date(2027, 3, 28))
    assert s.current == 2


def test_gap_resets_to_one_and_keeps_longest():
    s = from_dates([date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)])
    s = advance(s, date(2026, 11, 5))
    assert (s.current, s.longest, s.last_active) == (1, 3, date(2026, 11, 5))


def test_older_day_is_ignored():
    s = advance(EMPTY, date(2026, 11, 21))
    assert advance(s, date(2026, 11, 20)) == s


def test_display():
    s = Streak(4, 6, date(2026, 11, 21))
    assert displayed(s, date(2026, 11, 21)) == 4
    assert displayed(s, date(2026, 11, 22)) == 4
    assert displayed(s, date(2026, 11, 23)) == 0
    assert displayed(EMPTY, date(2026, 11, 23)) == 0


def test_from_dates_unordered_with_duplicates():
    days = [date(2026, 11, 3), date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 2), date(2026, 10, 20)]
    assert from_dates(days) == Streak(3, 3, date(2026, 11, 3))
    assert from_dates([]) == EMPTY
