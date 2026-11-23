"""A guest logs into an account: puzzle attempts, rating and evidence follow; idle guests leave nothing behind."""
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from accounts.models import Learner
from accounts.signals import merge_learners
from accounts.tasks import delete_idle_guests
from learning.services import finish_attempt, start_attempt
from puzzles.domain.glicko2 import Game, Rating, rate
from puzzles.models import PuzzleAttempt, PuzzleRating
from puzzles.services import finish_puzzle, rebuild_rating
from skills.models import Evidence, SkillEstimate
from tests.puzzle_data import MISSED, SOLVED, serve
from tests.test_finish import perfect_steps

pytestmark = pytest.mark.django_db
NOW = timezone.now()
T0, T1, T2 = (datetime(2026, 11, d, 12, tzinfo=UTC) for d in (18, 19, 20))


def test_merge_moves_attempts_and_rebuilds_rating(guest, account, puzzle_factory):
    target = account.learner
    finish_puzzle(target, serve(target, puzzle_factory(rating=1000), T0).pk, MISSED, T0)
    for t in (T1, T2):
        finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000), t).pk, SOLVED, t)
    merge_learners.send(sender=Learner, source=guest, target=target)
    expected = rate(rate(rate(Rating(1000, 350, 0.06), [Game(1000, 80, 0)], 0.5), [Game(1000, 80, 1)], 0.5),
                    [Game(1000, 80, 1)], 0.5)
    pr = PuzzleRating.objects.get(learner=target)
    assert (pr.rated_count, pr.solved_count) == (3, 2) and pr.rating == pytest.approx(expected.rating, abs=0.01)
    assert pr.last_rated_on == T2.date() and not PuzzleRating.objects.filter(learner=guest).exists()
    assert PuzzleAttempt.objects.filter(learner=target).count() == 3
    assert SkillEstimate.objects.get(learner=target, kind="area", key="tactics").observations == 3


def test_rebuild_without_attempts_removes_the_cache(guest):
    PuzzleRating.objects.create(learner=guest, rating=1200, rd=100, volatility=0.06)
    assert rebuild_rating(guest) is None and not PuzzleRating.objects.filter(learner=guest).exists()


def test_same_puzzle_is_rated_once(guest, account, puzzle_factory):
    target, p = account.learner, puzzle_factory()
    finish_puzzle(target, serve(target, p, T0).pk, SOLVED, T0)
    finish_puzzle(guest, serve(guest, p, T1).pk, MISSED, T1)
    merge_learners.send(sender=Learner, source=guest, target=target)
    rated = PuzzleAttempt.objects.filter(learner=target, puzzle=p).order_by("served_at").values_list("rated", flat=True)
    assert list(rated) == [True, False]
    assert PuzzleRating.objects.get(learner=target).rated_count == 1
    assert Evidence.objects.filter(learner=target, source="puzzle").count() == 1


def test_lesson_evidence_kept_once(guest, account, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = []
    lesson = lesson_factory("tac", kind="tactic")
    publish(lesson, valid_content)
    target = account.learner
    finish_attempt(target, start_attempt(target, lesson, T0).id, perfect_steps(), T0)
    finish_attempt(guest, start_attempt(guest, lesson, T1).id, perfect_steps(), T1)
    merge_learners.send(sender=Learner, source=guest, target=target)
    rows = Evidence.objects.filter(learner=target, source="lesson")
    assert rows.count() == 4
    assert set(rows.values_list("step_result__attempt__finished_at", flat=True)) == {T0}


def test_login_merges_puzzles(client, account, puzzle_factory):
    puzzle_factory()
    attempt = client.post("/api/v1/puzzles/next", {"mode": "rated"}, content_type="application/json").json()[
        "attempt_id"]
    client.post(f"/api/v1/puzzle-attempts/{attempt}/finish", SOLVED, content_type="application/json")
    client.post("/login/", {"email": "farel@example.com", "password": "Chess-is-fun-42"})
    learner = Learner.objects.get(user=account)
    assert PuzzleAttempt.objects.get(pk=attempt).learner == learner
    assert learner.xp_events.filter(reason="puzzle").count() == 1 and learner.xp_total == 3
    assert PuzzleRating.objects.get(learner=learner).rated_count == 1


def test_idle_guest_cleanup_removes_puzzle_data(guest, puzzle_factory):
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    Learner.objects.filter(pk=guest.pk).update(last_seen_at=NOW - timedelta(days=181))
    delete_idle_guests()
    assert not PuzzleAttempt.objects.exists() and not PuzzleRating.objects.exists() and not Evidence.objects.exists()
    assert not SkillEstimate.objects.exists()


def test_merge_keeps_the_start_of_an_existing_rating(guest, account, puzzle_factory):  # Review Focus 5
    target = account.learner
    for t in (T0, T1):
        finish_puzzle(target, serve(target, puzzle_factory(rating=1000), t).pk, SOLVED, t)
    before = PuzzleRating.objects.get(learner=target).rating
    guest.start_level = "club"  # the guest chose a level; the account never did
    guest.save()
    merge_learners.send(sender=Learner, source=guest, target=target)
    assert PuzzleRating.objects.get(learner=target).rating == pytest.approx(before, abs=0.01)


def test_merge_keeps_the_guests_start_when_only_the_guest_has_a_rating(guest, account, puzzle_factory):
    guest.start_level = "new"
    guest.save()
    finish_puzzle(guest, serve(guest, puzzle_factory(rating=700), T0).pk, SOLVED, T0)
    before = PuzzleRating.objects.get(learner=guest).rating
    account.learner.start_level = "club"
    account.learner.save()
    merge_learners.send(sender=Learner, source=guest, target=account.learner)
    assert PuzzleRating.objects.get(learner=account.learner).rating == pytest.approx(before, abs=0.01)
