"""How much XP an attempt earns. XP rewards learning something new or remembering it, not repeating it."""
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class XpRules:
    lesson_first: int = 10
    accuracy_bonus: int = 5
    accuracy_bonus_min: float = 0.9
    lesson_replay: int = 3

    @classmethod
    def from_settings(cls) -> "XpRules":
        return cls(settings.XP_LESSON_FIRST, settings.XP_ACCURACY_BONUS, settings.XP_ACCURACY_BONUS_MIN,
                   settings.XP_LESSON_REPLAY)


@dataclass(frozen=True)
class XpContext:
    completed: bool
    accuracy: float
    first_completion: bool
    bonus_earned_before: bool  # the accuracy bonus for this lesson was already awarded
    replay_xp_today: bool  # replay XP for this lesson was already awarded on this local day


def xp_for_attempt(ctx: XpContext, rules: XpRules) -> list[tuple[str, int]]:
    if not ctx.completed:
        return []
    awards = []
    if ctx.first_completion:
        awards.append(("lesson_first", rules.lesson_first))
    elif not ctx.replay_xp_today:
        awards.append(("lesson_replay", rules.lesson_replay))
    if ctx.accuracy >= rules.accuracy_bonus_min and not ctx.bonus_earned_before:
        awards.append(("accuracy_bonus", rules.accuracy_bonus))
    return awards
