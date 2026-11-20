from datetime import UTC, datetime

import pytest

from players.limits import refund, try_consume
from players.models import Player, UsageCounter

pytestmark = pytest.mark.django_db


@pytest.fixture
def player():
    return Player.objects.create(chesscom_username="farel")


def test_limit_resets_next_iso_week(player):
    sunday = datetime(2026, 11, 22, 23, 0, tzinfo=UTC)  # ISO week 47
    monday = datetime(2026, 11, 23, 1, 0, tzinfo=UTC)  # ISO week 48
    assert all(try_consume(player, "reviews", sunday) for _ in range(5))
    assert not try_consume(player, "reviews", sunday)
    assert try_consume(player, "reviews", monday)


def test_explains_have_their_own_limit(player, settings):
    now = datetime(2026, 11, 20, tzinfo=UTC)
    assert sum(try_consume(player, "explains", now) for _ in range(25)) == settings.LIMIT_EXPLAINS_PER_WEEK
    assert try_consume(player, "reviews", now)


def test_refund_gives_one_back(player):
    now = datetime(2026, 11, 20, tzinfo=UTC)
    for _ in range(5):
        try_consume(player, "reviews", now)
    refund(player, "reviews", now)
    assert UsageCounter.objects.get().reviews_used == 4
    assert try_consume(player, "reviews", now)
