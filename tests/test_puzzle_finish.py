"""Finishing a puzzle: the server re-scores it, moves the Glicko-2 rating, awards XP and writes evidence."""
from datetime import UTC, date, datetime, timedelta

import pytest
from django.utils import timezone

from accounts.models import Learner
from gamification.models import XpEvent
from puzzles.domain.solution import InvalidPuzzleResult
from puzzles.models import Puzzle, PuzzleAttempt, PuzzleRating
from puzzles.services import Expired, finish_puzzle, rating_view
from puzzles.domain.glicko2 import Rating
from skills.models import Evidence, SkillEstimate
from tests.puzzle_data import MATE2, MISSED, SOLVED, serve

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def test_rating_view_rounds_to_a_range():
    assert rating_view(Rating(1312, 40, 0.06)) == {"value": 1312, "low": 1250, "high": 1350, "settling": False}
    assert rating_view(Rating(1000, 350, 0.06))["settling"] is True


def test_solved_puzzle_raises_rating_and_awards_xp(guest, puzzle_factory):
    r = finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, SOLVED, NOW)
    assert r["solved"] and r["rating"]["before"] == 1000 and r["rating"]["after"] > 1000 and r["rating"]["settling"]
    assert r["rating"]["change"] == r["rating"]["after"] - r["rating"]["before"]
    assert r["xp"]["awarded"] == 3 and r["streak"]["current"] == 1
    assert XpEvent.objects.get(learner=guest).reason == "puzzle"
    pr = PuzzleRating.objects.get(learner=guest)
    assert (pr.rated_count, pr.solved_count) == (1, 1)
    assert set(r) == {"solved", "rating", "xp", "streak", "daily_goal", "achievements", "puzzle"}
    assert {t["key"] for t in r["puzzle"]["themes"]} == set(MATE2["themes"])
    attempt = PuzzleAttempt.objects.get(learner=guest)
    assert attempt.finished_at == NOW and attempt.played == SOLVED["played"] and attempt.learner_rating_before == 1000


def test_missed_puzzle_lowers_rating_without_xp(guest, puzzle_factory):
    r = finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, MISSED, NOW)
    assert not r["solved"] and r["rating"]["after"] < 1000 and r["xp"]["awarded"] == 0
    assert not XpEvent.objects.exists()


def test_finish_is_idempotent(guest, puzzle_factory):  # Review Focus 2
    a = serve(guest, puzzle_factory())
    assert finish_puzzle(guest, a.pk, SOLVED, NOW) == finish_puzzle(guest, a.pk, SOLVED, NOW + timedelta(seconds=2))
    assert XpEvent.objects.filter(learner=guest).count() == 1
    assert PuzzleRating.objects.get(learner=guest).rated_count == 1


def test_invalid_body_writes_nothing(guest, puzzle_factory):
    a = serve(guest, puzzle_factory())
    with pytest.raises(InvalidPuzzleResult):
        finish_puzzle(guest, a.pk, {**SOLVED, "played": [MATE2["illegal_first"]]}, NOW)
    a.refresh_from_db()
    assert a.finished_at is None and not PuzzleRating.objects.exists() and not XpEvent.objects.exists()
    assert not Evidence.objects.exists()


def test_expired_attempt(guest, puzzle_factory):
    with pytest.raises(Expired):
        finish_puzzle(guest, serve(guest, puzzle_factory(), NOW - timedelta(hours=25)).pk, SOLVED, NOW)


def test_other_learner(guest, account, puzzle_factory):
    with pytest.raises(PuzzleAttempt.DoesNotExist):
        finish_puzzle(account.learner, serve(guest, puzzle_factory()).pk, SOLVED, NOW)


def test_idle_days_use_local_dates_and_grow_rd(puzzle_factory):  # Review Focus 3
    tz = "America/Montreal"
    a, b = Learner.objects.create(timezone=tz), Learner.objects.create(timezone=tz)
    late = datetime(2026, 11, 20, 4, 30, tzinfo=UTC)  # 23:30 on 19 Nov in Montreal
    for learner in (a, b):
        finish_puzzle(learner, serve(learner, puzzle_factory(), late).pk, SOLVED, late)
    assert PuzzleRating.objects.get(learner=a).last_rated_on == date(2026, 11, 19)
    for learner, second in ((a, late + timedelta(minutes=40)), (b, late + timedelta(days=10))):
        finish_puzzle(learner, serve(learner, puzzle_factory(), second).pk, SOLVED, second)
    assert PuzzleRating.objects.get(learner=a).last_rated_on == date(2026, 11, 20)
    assert PuzzleRating.objects.get(learner=b).rd > PuzzleRating.objects.get(learner=a).rd


def test_rd_never_goes_below_the_floor(guest, puzzle_factory):
    PuzzleRating.objects.create(learner=guest, rating=1500, rd=46, volatility=0.06, last_rated_on=NOW.date())
    finish_puzzle(guest, serve(guest, puzzle_factory(rating=1500)).pk, SOLVED, NOW)
    assert PuzzleRating.objects.get(learner=guest).rd >= 45


def test_deactivated_puzzle_can_still_be_finished(guest, puzzle_factory):  # Review Focus 4
    a = serve(guest, puzzle_factory())
    Puzzle.objects.filter(pk=a.puzzle_id).update(is_active=False)
    assert finish_puzzle(guest, a.pk, SOLVED, NOW)["solved"] is True


def test_start_level_only_matters_before_the_first_puzzle(guest, puzzle_factory):  # Review Focus 5
    first = finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert first["rating"]["before"] == 1000
    guest.start_level = "club"
    guest.save()
    second = finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert second["rating"]["before"] == first["rating"]["after"]


def test_unrated_attempt_changes_nothing(guest, puzzle_factory):
    a = serve(guest, puzzle_factory())
    PuzzleAttempt.objects.filter(pk=a.pk).update(rated=False)
    r = finish_puzzle(guest, a.pk, SOLVED, NOW)
    assert r["rating"]["change"] == 0 and r["xp"]["awarded"] == 0 and not Evidence.objects.exists()
    assert not PuzzleRating.objects.exists()


def test_evidence_and_estimates_written(guest, puzzle_factory):
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert Evidence.objects.filter(learner=guest, area="tactics").count() == 1
    assert SkillEstimate.objects.get(learner=guest, kind="area", key="tactics").observations == 1


def test_theme_labels_follow_the_learner_language(guest, puzzle_factory):
    guest.language = "fr"
    guest.save()
    r = finish_puzzle(guest, serve(guest, puzzle_factory(themes=["fork"])).pk, MISSED, NOW)
    assert r["puzzle"]["themes"] == [{"key": "fork", "label": "Fourchette"}]
