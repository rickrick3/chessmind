"""Awarding XP, streaks and achievements, always from the ledger and inside the caller's transaction."""
from datetime import datetime

from django.db.models import Sum

from accounts.models import Learner

from .domain.achievements import ProgressStats, earned
from .domain.levels import level_floor, level_for
from .domain.streak import Streak, advance, displayed, from_dates
from .domain.xp import XpContext, XpRules, xp_for_attempt
from .models import LearnerAchievement, XpEvent

ONCE_PER_LESSON = ("lesson_first", "accuracy_bonus")


def _streak(learner: Learner) -> Streak:
    return Streak(learner.current_streak, learner.longest_streak, learner.last_active_date)


def _streak_view(learner: Learner, today) -> dict:
    s = _streak(learner)
    return {"current": displayed(s, today), "longest": s.longest, "today_done": s.last_active == today}


def _daily_goal(learner: Learner, today) -> dict:
    today_xp = XpEvent.objects.filter(learner=learner, local_date=today).aggregate(s=Sum("amount"))["s"] or 0
    return {"target": learner.daily_goal_xp, "today_xp": today_xp}


def award_for_attempt(learner: Learner, attempt, *, completed: bool, accuracy: float, first_completion: bool,
                      stats: ProgressStats, now: datetime) -> dict:
    """Write the XP an attempt earns, move the streak, grant achievements. Call inside a transaction."""
    locked = Learner.objects.select_for_update().get(pk=learner.pk)
    today = locked.local_date(now)
    for_lesson = XpEvent.objects.filter(learner=locked, lesson=attempt.lesson)
    ctx = XpContext(completed, accuracy, first_completion,
                    bonus_earned_before=for_lesson.filter(reason="accuracy_bonus").exists(),
                    replay_xp_today=for_lesson.filter(reason="lesson_replay", local_date=today).exists())
    awards = xp_for_attempt(ctx, XpRules.from_settings())
    for reason, amount in awards:
        XpEvent.objects.create(learner=locked, amount=amount, reason=reason, lesson=attempt.lesson,
                               attempt=attempt, local_date=today)
    total = sum(amount for _reason, amount in awards)
    old_level = level_for(locked.xp_total)
    if total > 0:
        s = advance(_streak(locked), today)
        locked.xp_total += total
        locked.current_streak, locked.longest_streak, locked.last_active_date = s.current, s.longest, s.last_active
        locked.save(update_fields=["xp_total", "current_streak", "longest_streak", "last_active_date"])
    have = set(LearnerAchievement.objects.filter(learner=locked).values_list("code", flat=True))
    new = earned(stats, displayed(_streak(locked), today), have)
    LearnerAchievement.objects.bulk_create([LearnerAchievement(learner=locked, code=c) for c in new])
    for field in ("xp_total", "current_streak", "longest_streak", "last_active_date"):
        setattr(learner, field, getattr(locked, field))
    level = level_for(locked.xp_total)
    return {"xp": {"awarded": total, "total": locked.xp_total, "level": level, "level_up": level > old_level},
            "streak": _streak_view(locked, today), "daily_goal": _daily_goal(locked, today), "achievements": new}


def summary(learner: Learner, now: datetime) -> dict:
    today = learner.local_date(now)
    level = level_for(learner.xp_total)
    return {"xp_total": learner.xp_total, "level": level, "level_floor": level_floor(level),
            "next_level_at": level_floor(level + 1), "streak": _streak_view(learner, today),
            "daily_goal": _daily_goal(learner, today)}


def on_merge(sender, source: Learner, target: Learner, **kwargs) -> None:
    """A guest logged into an account: move XP (no lesson counted twice) and achievements, rebuild the caches."""
    target_once = set(XpEvent.objects.filter(learner=target, reason__in=ONCE_PER_LESSON)
                      .values_list("lesson_id", "reason"))
    replay_days = set(XpEvent.objects.filter(learner__in=(source, target), reason="lesson_replay")
                      .values_list("lesson_id", "local_date"))
    for event in XpEvent.objects.filter(learner=source).order_by("created_at", "id"):
        duplicate = event.reason in ONCE_PER_LESSON and (event.lesson_id, event.reason) in target_once
        if duplicate and event.reason == "lesson_first" and (event.lesson_id, event.local_date) not in replay_days:
            # The account already completed this lesson: for the account it was a replay. Keeping it as one keeps
            # the guest's day in the ledger, so the rebuilt streak doesn't lose it.
            event.reason, event.amount, event.learner = "lesson_replay", XpRules.from_settings().lesson_replay, target
            event.save(update_fields=["reason", "amount", "learner"])
            replay_days.add((event.lesson_id, event.local_date))
        elif duplicate:
            event.delete()
        else:
            event.learner = target
            event.save(update_fields=["learner"])
    have = set(LearnerAchievement.objects.filter(learner=target).values_list("code", flat=True))
    LearnerAchievement.objects.filter(learner=source, code__in=have).delete()
    LearnerAchievement.objects.filter(learner=source).update(learner=target)
    ledger = XpEvent.objects.filter(learner=target)
    s = from_dates(ledger.values_list("local_date", flat=True))
    target.xp_total = ledger.aggregate(t=Sum("amount"))["t"] or 0
    target.current_streak, target.longest_streak, target.last_active_date = s.current, s.longest, s.last_active
    target.save(update_fields=["xp_total", "current_streak", "longest_streak", "last_active_date"])
