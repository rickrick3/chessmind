from datetime import datetime

from django.conf import settings
from django.db.models import F

from .models import UsageCounter

LIMITS = {"reviews": "LIMIT_REVIEWS_PER_WEEK", "explains": "LIMIT_EXPLAINS_PER_WEEK"}


def _counter(player, now: datetime) -> UsageCounter:
    year, week, _day = now.isocalendar()
    counter, _ = UsageCounter.objects.get_or_create(player=player, iso_year=year, iso_week=week)
    return counter


def used(player, kind: str, now: datetime) -> int:
    return getattr(_counter(player, now), f"{kind}_used")


def try_consume(player, kind: str, now: datetime) -> bool:
    """Use one unit of this week's allowance. False when the limit is reached. Safe under concurrency."""
    field = f"{kind}_used"
    limit = getattr(settings, LIMITS[kind])
    c = _counter(player, now)
    return UsageCounter.objects.filter(pk=c.pk, **{f"{field}__lt": limit}).update(**{field: F(field) + 1}) == 1


def refund(player, kind: str, now: datetime) -> None:
    field = f"{kind}_used"
    c = _counter(player, now)
    UsageCounter.objects.filter(pk=c.pk, **{f"{field}__gt": 0}).update(**{field: F(field) - 1})
