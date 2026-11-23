from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Learner
from accounts.signals import merge_learners
from learning import services
from learning.models import LessonAttempt, LessonProgress

pytestmark = pytest.mark.django_db
NOW = timezone.now()


@pytest.fixture
def path3(lesson_factory, publish, valid_content):
    lessons = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2, 3)]
    for lesson in lessons:
        publish(lesson, valid_content)
    return lessons


def done(learner, lesson, best=1.0, completions=1):
    return LessonProgress.objects.create(learner=learner, lesson=lesson, first_completed_at=NOW,
                                         best_accuracy=best, completions=completions, last_attempt_at=NOW)


def test_path_nodes_only_published(path3, lesson_factory):
    lesson_factory("draft-only", order=9)
    nodes = services.path_nodes()
    assert [n.slug for n in nodes] == ["lesson-1", "lesson-2", "lesson-3"]
    assert [n.position for n in nodes] == [0, 1, 2] and {n.unit_index for n in nodes} == {1}  # the unit's order


def test_states_for_guest_and_none(path3, guest):
    assert services.states_for(None)["lesson-1"] == "current"
    done(guest, path3[0])
    assert services.states_for(guest) == {"lesson-1": "done", "lesson-2": "current", "lesson-3": "locked"}


def test_set_start_level(path3, guest):
    assert services.set_start_level(guest, "rules") == "lesson-1"
    guest.refresh_from_db()
    assert guest.start_level == "rules" and services.states_for(guest)["lesson-3"] == "open"
    with pytest.raises(ValueError):
        services.set_start_level(guest, "grandmaster")


def test_start_attempt_locked_and_unpublished(path3, guest, lesson_factory):
    with pytest.raises(services.Locked):
        services.start_attempt(guest, path3[2], NOW)
    with pytest.raises(services.NotPublished):
        services.start_attempt(guest, lesson_factory("not-yet"), NOW)


def test_attempt_pins_version(path3, guest, publish, valid_content):
    attempt = services.start_attempt(guest, path3[0], NOW)
    v1 = attempt.version
    publish(path3[0], {**valid_content, "completion": {"min_accuracy": 0.5}})
    attempt.refresh_from_db()
    assert attempt.version == v1 and path3[0].published_version != v1
    assert attempt.learner == guest and attempt.started_at == NOW and attempt.finished_at is None


def test_merge_combines_progress(path3, guest):
    target = Learner.objects.create()
    done(target, path3[0], best=0.6, completions=1)
    later = NOW + timedelta(days=1)
    LessonProgress.objects.create(learner=guest, lesson=path3[0], first_completed_at=later, best_accuracy=0.9,
                                  completions=2, last_attempt_at=later)
    done(guest, path3[1], best=0.8)
    services.start_attempt(guest, path3[0], NOW)
    guest.start_level = "club"
    guest.save()
    merge_learners.send(sender=Learner, source=guest, target=target)
    p0 = LessonProgress.objects.get(learner=target, lesson=path3[0])
    assert (p0.best_accuracy, p0.completions, p0.first_completed_at, p0.last_attempt_at) == (0.9, 3, NOW, later)
    assert LessonProgress.objects.get(learner=target, lesson=path3[1]).best_accuracy == 0.8
    assert not LessonProgress.objects.filter(learner=guest).exists()
    assert LessonAttempt.objects.get().learner == target
    target.refresh_from_db()
    assert target.start_level == "club"
