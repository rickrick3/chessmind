import itertools

import pytest
from django.core.exceptions import PermissionDenied

from curriculum import services
from curriculum.domain.workflow import (ALLOWED, APPROVED, ARCHIVED, DRAFT, PENDING_REVIEW, PUBLISHED, REJECTED,
                                        STATUSES, VALIDATING, IllegalTransition, check_transition)
from curriculum.models import LessonVersion

pytestmark = pytest.mark.django_db


def at(version, status):
    """Put a version straight into a status (test setup only)."""
    LessonVersion.objects.filter(pk=version.pk).update(status=status)
    version.refresh_from_db()
    return version


@pytest.mark.parametrize("current,target", list(itertools.product(STATUSES, STATUSES)))
def test_transition_table(current, target):
    if target in ALLOWED[current]:
        check_transition(current, target)
    else:
        with pytest.raises(IllegalTransition):
            check_transition(current, target)


def test_rejected_and_archived_are_final():
    assert ALLOWED[REJECTED] == set() and ALLOWED[ARCHIVED] == set()


def test_new_version_numbers_and_copies(lesson_factory, staff):
    lesson = lesson_factory()
    v1 = services.new_version(lesson, staff, content={"schema": 1, "steps": []})
    v2 = services.new_version(lesson, staff)
    assert (v1.number, v2.number) == (1, 2) and v2.content == {"schema": 1, "steps": []}
    assert v2.status == DRAFT and v2.created_by == staff
    assert [(e.from_status, e.to_status) for e in v2.events.all()] == [("", DRAFT)]


def test_reject_needs_note(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={}), PENDING_REVIEW)
    with pytest.raises(ValueError):
        services.transition(v, REJECTED, staff, note="  ")
    v.refresh_from_db()
    assert v.status == PENDING_REVIEW
    services.transition(v, REJECTED, staff, note="Wrong idea on step 3")
    assert v.status == REJECTED and v.events.last().note == "Wrong idea on step 3"


def test_non_staff_cannot_approve(lesson_factory, staff, account):
    v = at(services.new_version(lesson_factory(), staff, content={}), PENDING_REVIEW)
    with pytest.raises(PermissionDenied):
        services.transition(v, APPROVED, account)
    v.refresh_from_db()
    assert v.status == PENDING_REVIEW


def test_system_can_move_validation_results(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={}), VALIDATING)
    services.transition(v, PENDING_REVIEW, None)
    assert v.status == PENDING_REVIEW and v.events.last().actor is None


def test_approve_records_reviewer(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={}), PENDING_REVIEW)
    services.transition(v, APPROVED, staff)
    v.refresh_from_db()
    assert v.reviewed_by == staff and v.reviewed_at is not None


def test_publish_archives_previous(lesson_factory, staff):
    lesson = lesson_factory()
    v1 = at(services.new_version(lesson, staff, content={"n": 1}), APPROVED)
    services.publish(v1, staff)
    v2 = at(services.new_version(lesson, staff, content={"n": 2}), APPROVED)
    services.transition(v2, PUBLISHED, staff)
    lesson.refresh_from_db()
    v1.refresh_from_db()
    assert lesson.published_version == v2 and v1.status == ARCHIVED and v2.published_at is not None
    assert services.published_content(lesson) == (v2, {"n": 2})


def test_publish_needs_approval(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={}), PENDING_REVIEW)
    with pytest.raises(IllegalTransition):
        services.publish(v, staff)


def test_every_change_is_logged(lesson_factory, staff):
    v = services.new_version(lesson_factory(), staff, content={})
    services.transition(v, VALIDATING, staff)
    services.transition(v, PENDING_REVIEW, None)
    services.transition(v, APPROVED, staff)
    services.transition(v, PUBLISHED, staff)
    log = [(e.from_status, e.to_status, e.actor_id) for e in v.events.all()]
    assert log == [("", DRAFT, staff.id), (DRAFT, VALIDATING, staff.id), (VALIDATING, PENDING_REVIEW, None),
                   (PENDING_REVIEW, APPROVED, staff.id), (APPROVED, PUBLISHED, staff.id)]


def test_edit_only_when_editable(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={"a": 1}), APPROVED)
    with pytest.raises(IllegalTransition):
        services.edit_content(v, {"a": 2}, staff)
    assert LessonVersion.objects.get(pk=v.pk).content == {"a": 1}


def test_edit_in_draft_keeps_draft_and_logs_snapshot(lesson_factory, staff):
    v = services.new_version(lesson_factory(), staff, content={"a": 1})
    services.edit_content(v, {"a": 2}, staff)
    v.refresh_from_db()
    edit = v.events.filter(kind="edit").get()
    assert v.status == DRAFT and v.content == {"a": 2} and edit.content_snapshot == {"a": 2}


def test_edit_in_review_sends_back_to_validation(lesson_factory, staff):
    v = at(services.new_version(lesson_factory(), staff, content={"a": 1}), PENDING_REVIEW)
    services.edit_content(v, {"a": 2}, staff)
    v.refresh_from_db()
    assert v.status == VALIDATING


def test_unpublished_lesson_has_no_content(lesson_factory, staff):
    lesson = lesson_factory()
    at(services.new_version(lesson, staff, content={"a": 1}), PENDING_REVIEW)
    assert services.published_content(lesson) is None
