from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import IntegrityError, transaction

from accounts.models import Learner
from accounts.signals import merge_learners
from gamification.domain.achievements import ProgressStats
from gamification.models import LearnerAchievement, XpEvent
from gamification.services import award_for_attempt, summary
from learning.services import start_attempt

pytestmark = pytest.mark.django_db
PARIS_2330 = datetime(2026, 11, 21, 22, 30, tzinfo=UTC)  # 23:30 in Paris, Nov 21
PARIS_0010 = datetime(2026, 11, 21, 23, 10, tzinfo=UTC)  # 00:10 in Paris, Nov 22 — same UTC day
STATS = ProgressStats(lessons_completed=1, units_completed=0, perfect_lessons=0)


@pytest.fixture
def paris():
    return Learner.objects.create(timezone="Europe/Paris")


@pytest.fixture
def lessons(lesson_factory, publish, valid_content):
    made = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2)]
    for lesson in made:
        publish(lesson, valid_content)
    return made


def award(learner, lesson, now, *, accuracy=1.0, first=True, completed=True, stats=STATS):
    attempt = start_attempt(learner, lesson, now)
    return award_for_attempt(learner, attempt, completed=completed, accuracy=accuracy, first_completion=first,
                             stats=stats, now=now)


def test_award_first_completion(paris, lessons):
    r = award(paris, lessons[0], PARIS_2330, accuracy=0.95)
    paris.refresh_from_db()
    assert r["xp"] == {"awarded": 15, "total": 15, "level": 1, "level_up": False}
    assert r["streak"] == {"current": 1, "longest": 1, "today_done": True}
    assert r["daily_goal"] == {"target": 20, "today_xp": 15}
    assert r["achievements"] == ["first_lesson"]
    assert (paris.xp_total, paris.current_streak, paris.last_active_date) == (15, 1, date(2026, 11, 21))
    assert sorted(XpEvent.objects.values_list("reason", "amount", "local_date")) == [
        ("accuracy_bonus", 5, date(2026, 11, 21)), ("lesson_first", 10, date(2026, 11, 21))]


def test_streak_across_paris_midnight(paris, lessons):
    award(paris, lessons[0], PARIS_2330)
    r = award(paris, lessons[0], PARIS_0010, first=False)
    assert r["streak"]["current"] == 2 and r["xp"]["awarded"] == 3
    assert r["daily_goal"]["today_xp"] == 3


def test_replay_xp_once_per_local_day(paris, lessons):
    award(paris, lessons[0], PARIS_2330, accuracy=0.5)
    later = PARIS_0010 + timedelta(hours=10)
    assert award(paris, lessons[0], later, first=False, accuracy=0.5)["xp"]["awarded"] == 3
    assert award(paris, lessons[0], later, first=False, accuracy=0.5)["xp"]["awarded"] == 0
    assert award(paris, lessons[0], later, first=False, accuracy=0.95)["xp"]["awarded"] == 5
    assert award(paris, lessons[0], later, first=False, accuracy=0.95)["xp"]["awarded"] == 0


def test_no_xp_keeps_streak_untouched(paris, lessons):
    r = award(paris, lessons[0], PARIS_2330, completed=False)
    paris.refresh_from_db()
    assert r["xp"]["awarded"] == 0 and paris.current_streak == 0 and paris.last_active_date is None


def test_level_up(paris, lessons):
    paris.xp_total = 45
    paris.save()
    r = award(paris, lessons[0], PARIS_2330)
    assert r["xp"] == {"awarded": 15, "total": 60, "level": 2, "level_up": True}


def test_duplicate_reason_for_attempt_is_rejected(paris, lessons):
    attempt = start_attempt(paris, lessons[0], PARIS_2330)
    XpEvent.objects.create(learner=paris, amount=10, reason="lesson_first", attempt=attempt,
                           lesson=lessons[0], local_date=date(2026, 11, 21))
    with pytest.raises(IntegrityError), transaction.atomic():
        XpEvent.objects.create(learner=paris, amount=10, reason="lesson_first", attempt=attempt,
                               lesson=lessons[0], local_date=date(2026, 11, 21))


def test_summary_shape(paris, lessons):
    award(paris, lessons[0], PARIS_2330, accuracy=0.95)
    s = summary(paris, PARIS_2330 + timedelta(days=2))  # a day was missed
    assert s == {"xp_total": 15, "level": 1, "level_floor": 0, "next_level_at": 50,
                 "streak": {"current": 0, "longest": 1, "today_done": False},
                 "daily_goal": {"target": 20, "today_xp": 0}}


def test_merge_no_double_first_completion(lessons):
    target = Learner.objects.create(timezone="UTC")
    source = Learner.objects.create(timezone="UTC", start_level="rules")  # both lessons open
    d1 = datetime(2026, 11, 20, 12, tzinfo=UTC)
    d2 = datetime(2026, 11, 21, 12, tzinfo=UTC)
    award(target, lessons[0], d1, accuracy=0.5)          # L first: 10, on D1
    award(source, lessons[0], d2, accuracy=1.0)          # L first + bonus: 15, on D2
    award(source, lessons[1], d2, accuracy=0.5)          # M first: 10, on D2
    LearnerAchievement.objects.create(learner=source, code="streak_3")
    merge_learners.send(sender=Learner, source=source, target=target)
    target.refresh_from_db()
    assert target.xp_total == 25 and target.current_streak == 2 and target.longest_streak == 2
    assert target.last_active_date == date(2026, 11, 21)
    assert sorted(XpEvent.objects.filter(learner=target).values_list("reason", flat=True)) == [
        "accuracy_bonus", "lesson_first", "lesson_first"]
    assert set(LearnerAchievement.objects.filter(learner=target).values_list("code", flat=True)) == {
        "first_lesson", "streak_3"}
