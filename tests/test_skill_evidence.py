"""The evidence ledger, skill recompute, lesson evidence and the backfill command."""
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from learning.services import finish_attempt, start_attempt
from puzzles.models import PuzzleAttempt
from skills.domain.areas import AREAS
from skills.models import Evidence, SkillEstimate, SkillHistory
from skills.services import recompute, record_puzzle_evidence
from tests.test_finish import perfect_steps

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def finished(learner, puzzle, solved, when, rated=True, before=1500):
    return PuzzleAttempt.objects.create(learner=learner, puzzle=puzzle, mode="rated", served_at=when,
                                        finished_at=when, solved=solved, rated=rated, learner_rating_before=before)


def test_puzzle_evidence_one_row_per_area(guest, puzzle_factory):
    p = puzzle_factory(themes=["long", "defensiveMove", "fork"], rating=1600)
    assert record_puzzle_evidence(finished(guest, p, True, NOW), NOW.date()) == 3
    rows = Evidence.objects.filter(learner=guest)
    assert set(rows.values_list("area", flat=True)) == {"tactics", "calculation", "defense"}
    assert all(r.success and r.difficulty == 1600 and r.source == "puzzle" and r.learner_rating == 1500 for r in rows)


def test_unrated_attempt_gives_no_evidence(guest, puzzle_factory):
    assert record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW, rated=False), NOW.date()) == 0


def test_puzzle_evidence_is_written_once(guest, puzzle_factory):
    attempt = finished(guest, puzzle_factory(), False, NOW)
    record_puzzle_evidence(attempt, NOW.date())
    assert record_puzzle_evidence(attempt, NOW.date()) == 0 and Evidence.objects.count() == 1


def test_lesson_finish_writes_evidence_on_first_attempt_only(guest, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = []
    lesson = lesson_factory("tac", kind="tactic")
    publish(lesson, valid_content)
    for _ in range(2):
        finish_attempt(guest, start_attempt(guest, lesson, NOW).id, perfect_steps(), NOW)
    rows = Evidence.objects.filter(learner=guest, source="lesson")
    assert rows.count() == 4 and set(rows.values_list("area", flat=True)) == {"tactics"} and all(r.success for r in rows)
    assert SkillEstimate.objects.get(learner=guest, kind="area", key="tactics").observations == 4


def test_recompute_writes_all_areas(guest, puzzle_factory):
    for i in range(12):
        record_puzzle_evidence(finished(guest, puzzle_factory(), i % 2 == 0, NOW), NOW.date())
    recompute(guest, NOW)
    by_key = {e.key: e for e in SkillEstimate.objects.filter(learner=guest, kind="area")}
    assert set(by_key) == set(AREAS)
    tactics = by_key["tactics"]
    assert (tactics.basis, tactics.confidence, tactics.observations) == ("puzzle", "early", 12)
    assert tactics.low is not None and tactics.high is not None and tactics.low < tactics.high
    assert by_key["openings"].basis == "none"


def test_theme_rows_only_for_motifs(guest, puzzle_factory):
    record_puzzle_evidence(finished(guest, puzzle_factory(themes=["fork", "short", "middlegame"]), False, NOW),
                           NOW.date())
    recompute(guest, NOW)
    assert list(SkillEstimate.objects.filter(learner=guest, kind="theme").values_list("key", flat=True)) == ["fork"]


def test_repeated_mistake_flag_on_theme(guest, puzzle_factory):
    for d in (0, 2, 5):
        when = NOW - timedelta(days=d)
        record_puzzle_evidence(finished(guest, puzzle_factory(themes=["pin"], rating=1400), False, when), when.date())
    recompute(guest, NOW)
    assert SkillEstimate.objects.get(learner=guest, kind="theme", key="pin").repeated_mistake is True


def test_stale_theme_rows_are_removed(guest, puzzle_factory):
    attempt = finished(guest, puzzle_factory(themes=["skewer"]), False, NOW)
    record_puzzle_evidence(attempt, NOW.date())
    recompute(guest, NOW)
    Evidence.objects.filter(puzzle_attempt=attempt).delete()
    recompute(guest, NOW)
    assert not SkillEstimate.objects.filter(learner=guest, kind="theme").exists()


def test_history_one_row_per_area_per_day(guest, puzzle_factory):
    for _ in range(10):
        record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW), NOW.date())
    recompute(guest, NOW)
    recompute(guest, NOW)
    assert SkillHistory.objects.filter(learner=guest, key="tactics").count() == 1
    recompute(guest, NOW + timedelta(days=1))
    assert SkillHistory.objects.filter(learner=guest, key="tactics").count() == 2
    assert not SkillHistory.objects.filter(learner=guest, key="openings").exists()


def test_backfill_maps_old_tags_and_is_idempotent(guest, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = ["defence"]
    lesson = lesson_factory("old", kind="concept")
    publish(lesson, valid_content)
    finish_attempt(guest, start_attempt(guest, lesson, NOW).id, perfect_steps(), NOW)
    finish_attempt(guest, start_attempt(guest, lesson, NOW + timedelta(minutes=5)).id, perfect_steps(),
                   NOW + timedelta(minutes=5))
    Evidence.objects.all().delete()  # as if recorded before this project
    call_command("backfill_evidence")
    call_command("backfill_evidence")
    assert Evidence.objects.filter(learner=guest, area="defense").count() == 4
    assert SkillEstimate.objects.filter(learner=guest, kind="area").count() == len(AREAS)


def test_deleting_the_learner_removes_evidence(guest, puzzle_factory):
    record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW), NOW.date())
    recompute(guest, NOW)
    guest.delete()
    assert not Evidence.objects.exists() and not SkillEstimate.objects.exists() and not SkillHistory.objects.exists()
