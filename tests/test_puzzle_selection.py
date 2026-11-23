"""Choosing the next puzzle at the learner's level."""
from datetime import timedelta

import pytest
from django.utils import timezone

from puzzles.domain.selection import target
from puzzles.models import Puzzle, PuzzleAttempt
from puzzles.services import NoPuzzleLeft, current_rating, next_puzzle, start_rating

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def test_target_offsets():
    offsets = {"easier": -300, "normal": -100, "harder": 200}
    assert [target(1300, d, offsets) for d in ("easier", "normal", "harder")] == [1000, 1200, 1500]
    with pytest.raises(ValueError):
        target(1300, "hard", offsets)


def test_start_rating_by_level(guest):
    assert (start_rating(guest).rating, start_rating(guest).rd, start_rating(guest).volatility) == (1000, 350, 0.06)
    guest.start_level = "club"
    assert start_rating(guest).rating == 1500 and current_rating(guest).rating == 1500


def test_first_puzzle_uses_start_level(guest, puzzle_factory):
    guest.start_level = "new"
    guest.save()
    low, _ = puzzle_factory(rating=600), puzzle_factory(rating=1500)
    attempt = next_puzzle(guest, mode="rated", now=NOW)
    assert attempt.puzzle == low and attempt.rated and attempt.mode == "rated" and attempt.served_at == NOW


def test_difficulty_moves_the_target(guest, puzzle_factory):
    puzzle_factory(rating=900)
    hard = puzzle_factory(rating=1200)
    assert next_puzzle(guest, mode="rated", difficulty="harder", now=NOW).puzzle == hard


def test_never_serves_an_attempted_puzzle(guest, puzzle_factory):
    a, b = puzzle_factory(rating=900), puzzle_factory(rating=900)
    first = next_puzzle(guest, mode="rated", now=NOW)
    PuzzleAttempt.objects.filter(pk=first.pk).update(finished_at=NOW, solved=True)
    second = next_puzzle(guest, mode="rated", now=NOW)
    assert {first.puzzle, second.puzzle} == {a, b}
    PuzzleAttempt.objects.filter(pk=second.pk).update(finished_at=NOW, solved=True)
    with pytest.raises(NoPuzzleLeft):
        next_puzzle(guest, mode="rated", now=NOW)


def test_open_attempt_is_served_again(guest, puzzle_factory):
    puzzle_factory()
    puzzle_factory()
    assert next_puzzle(guest, mode="rated", now=NOW).pk == next_puzzle(guest, mode="rated", now=NOW).pk


def test_open_attempt_expires_after_24h(guest, puzzle_factory):
    puzzle_factory()
    puzzle_factory()
    old = next_puzzle(guest, mode="rated", now=NOW - timedelta(hours=25))
    new = next_puzzle(guest, mode="rated", now=NOW)
    assert new.pk != old.pk and new.puzzle != old.puzzle


def test_far_puzzle_is_still_served(guest, puzzle_factory):  # Review Focus 1
    far = puzzle_factory(rating=2700)
    assert next_puzzle(guest, mode="rated", now=NOW).puzzle == far


def test_theme_mode(guest, puzzle_factory):
    fork = puzzle_factory(themes=["fork", "short"])
    pin = puzzle_factory(themes=["pin"])
    themed = next_puzzle(guest, mode="theme", theme="fork", now=NOW)
    rated = next_puzzle(guest, mode="rated", now=NOW)  # the open theme attempt is not reused in rated mode
    assert themed.puzzle == fork and themed.theme == "fork" and rated.puzzle == pin and rated.pk != themed.pk
    with pytest.raises(NoPuzzleLeft):
        PuzzleAttempt.objects.filter(pk=themed.pk).update(finished_at=NOW, solved=True)
        next_puzzle(guest, mode="theme", theme="fork", now=NOW)


def test_inactive_puzzle_never_served(guest, puzzle_factory):  # Review Focus 4
    puzzle_factory()
    puzzle_factory()
    first = next_puzzle(guest, mode="rated", now=NOW)
    Puzzle.objects.filter(pk=first.puzzle_id).update(is_active=False)
    assert next_puzzle(guest, mode="rated", now=NOW).puzzle_id != first.puzzle_id


@pytest.mark.parametrize("kw", [{"mode": "x"}, {"mode": "theme", "theme": "nonsense"}, {"mode": "theme"},
                                {"mode": "rated", "theme": "fork"}, {"mode": "rated", "difficulty": "hard"}])
def test_bad_arguments(guest, kw):
    with pytest.raises(ValueError):
        next_puzzle(guest, now=NOW, **kw)
