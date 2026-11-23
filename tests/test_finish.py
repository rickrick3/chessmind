import copy
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Learner
from gamification.models import XpEvent
from learning.domain.scoring import InvalidResult
from learning.models import LessonAttempt, LessonProgress, StepResult
from learning.services import Expired, finish_attempt, progress_stats, start_attempt

pytestmark = pytest.mark.django_db
NOW = timezone.now()
KEYS = {"completed", "accuracy", "xp", "streak", "daily_goal", "unlocked", "achievements", "new_cards"}


def perfect_steps():
    return [
        {"id": "s3", "tries": ["b8c6"], "hints": 0, "ms": 4000},
        {"id": "s4", "tries": [0], "hints": 0, "ms": 3000},
        {"id": "s5", "tries": [["e2e4"], ["g1f3"], ["f1c4"]], "hints": [0, 0, 0], "ms": 9000},
        {"id": "s6", "tries": [0], "hints": 0, "ms": 2000},
    ]


@pytest.fixture
def path2(lesson_factory, publish, valid_content):
    lessons = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2)]
    for lesson in lessons:
        publish(lesson, valid_content)
    return lessons


@pytest.fixture
def learner():
    return Learner.objects.create(timezone="Europe/Paris")


def test_finish_awards_and_unlocks(learner, path2):
    a = start_attempt(learner, path2[0], NOW)
    r = finish_attempt(learner, a.id, perfect_steps(), NOW)
    assert set(r) == KEYS and r["completed"] is True and r["accuracy"] == 1.0
    assert r["xp"]["awarded"] == 15 and r["unlocked"] == ["lesson-2"] and r["new_cards"] == 0
    assert r["achievements"] == ["first_lesson"] and r["streak"]["current"] == 1
    p = LessonProgress.objects.get(learner=learner, lesson=path2[0])
    assert (p.completions, p.best_accuracy, p.first_completed_at) == (1, 1.0, NOW)
    assert StepResult.objects.filter(attempt=a).count() == 4
    a.refresh_from_db()
    assert a.finished_at == NOW and a.xp_awarded == 15 and a.result == r and a.completed is True


def test_finish_is_idempotent(learner, path2):
    a = start_attempt(learner, path2[0], NOW)
    first = finish_attempt(learner, a.id, perfect_steps(), NOW)
    again = finish_attempt(learner, a.id, perfect_steps(), NOW + timedelta(minutes=1))
    assert again == first and XpEvent.objects.count() == 2 and StepResult.objects.count() == 4
    assert LessonProgress.objects.get().completions == 1


def test_replay_earns_replay_xp(learner, path2):
    finish_attempt(learner, start_attempt(learner, path2[0], NOW).id, perfect_steps(), NOW)
    r = finish_attempt(learner, start_attempt(learner, path2[0], NOW).id, perfect_steps(), NOW)
    assert r["xp"]["awarded"] == 3 and r["unlocked"] == [] and LessonProgress.objects.get().completions == 2


def test_incomplete_attempt(learner, path2):
    steps = perfect_steps()
    steps[0]["tries"] = ["d7d5", "f7f6"]
    r = finish_attempt(learner, start_attempt(learner, path2[0], NOW).id, steps, NOW)
    p = LessonProgress.objects.get()
    assert r["completed"] is False and r["xp"]["awarded"] == 0 and r["unlocked"] == []
    assert (p.completions, p.first_completed_at, p.best_accuracy) == (0, None, 0.0)


def test_finish_expires_after_24h(learner, path2):
    a = start_attempt(learner, path2[0], NOW - timedelta(hours=24, seconds=1))
    with pytest.raises(Expired):
        finish_attempt(learner, a.id, perfect_steps(), NOW)
    assert StepResult.objects.count() == 0


def test_finish_scores_pinned_version(learner, path2, publish, valid_content):
    a = start_attempt(learner, path2[0], NOW)
    v2 = copy.deepcopy(valid_content)
    v2["steps"][2]["accept"] = ["d7d6"]
    v2["steps"][2]["also_good"] = []
    publish(path2[0], v2)
    r = finish_attempt(learner, a.id, perfect_steps(), NOW)
    assert r["completed"] is True and r["accuracy"] == 1.0


def test_invalid_result_writes_nothing(learner, path2):
    a = start_attempt(learner, path2[0], NOW)
    steps = perfect_steps()
    steps[0]["tries"] = ["e2e5"]
    with pytest.raises(InvalidResult):
        finish_attempt(learner, a.id, steps, NOW)
    a.refresh_from_db()
    assert a.finished_at is None and not StepResult.objects.exists() and not XpEvent.objects.exists()
    assert not LessonProgress.objects.exists()


def test_other_learner_cannot_finish(learner, path2):
    a = start_attempt(learner, path2[0], NOW)
    with pytest.raises(LessonAttempt.DoesNotExist):
        finish_attempt(Learner.objects.create(), a.id, perfect_steps(), NOW)


def test_progress_stats(learner, path2):
    assert progress_stats(learner).lessons_completed == 0
    finish_attempt(learner, start_attempt(learner, path2[0], NOW).id, perfect_steps(), NOW)
    s = progress_stats(learner)
    assert (s.lessons_completed, s.units_completed, s.perfect_lessons) == (1, 0, 1)
    finish_attempt(learner, start_attempt(learner, path2[1], NOW).id, perfect_steps(), NOW)
    assert progress_stats(learner).units_completed == 1


def test_finish_locks_only_the_attempt_row(learner, path2):
    """Locking the joined lesson/version rows would queue every learner finishing that lesson, and can deadlock
    with a publish (which locks lesson, then versions)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    a = start_attempt(learner, path2[0], NOW)
    with CaptureQueriesContext(connection) as ctx:
        finish_attempt(learner, a.id, perfect_steps(), NOW)
    locks = [q["sql"] for q in ctx.captured_queries if "FOR UPDATE" in q["sql"] and '"learning_lessonattempt"' in q["sql"]]
    assert locks and all('FOR UPDATE OF "learning_lessonattempt"' in sql for sql in locks)
