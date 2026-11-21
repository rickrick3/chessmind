"""Lesson versions and the publication workflow. Every change is logged as a VersionEvent."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .domain.workflow import (APPROVED, ARCHIVED, DRAFT, EDITABLE, PENDING_REVIEW, PUBLISHED, REJECTED,
                              VALIDATING, IllegalTransition, check_transition)
from .models import Lesson, LessonVersion, VersionEvent


def _check_actor(actor) -> None:
    if actor is not None and not actor.is_staff:
        raise PermissionDenied("staff only")


def _log(version, actor, kind, from_status="", to_status="", note="", snapshot=None) -> None:
    VersionEvent.objects.create(version=version, actor=actor, kind=kind, from_status=from_status,
                                to_status=to_status, note=note, content_snapshot=snapshot)


def new_version(lesson: Lesson, actor, content: dict | None = None) -> LessonVersion:
    """A new draft, numbered after the last one. Without content, it copies the latest version's."""
    _check_actor(actor)
    with transaction.atomic():
        Lesson.objects.select_for_update().get(pk=lesson.pk)
        last = lesson.versions.order_by("-number").first()
        if content is None:
            content = last.content if last else {}
        number = (lesson.versions.aggregate(m=Max("number"))["m"] or 0) + 1
        version = LessonVersion.objects.create(lesson=lesson, number=number, status=DRAFT, content=content,
                                               created_by=actor)
        _log(version, actor, "transition", "", DRAFT)
    return version


def edit_content(version: LessonVersion, content: dict, actor) -> LessonVersion:
    """Replace the content of a draft or a version under review. Under review, it goes back to validation."""
    _check_actor(actor)
    with transaction.atomic():
        locked = LessonVersion.objects.select_for_update().get(pk=version.pk)
        if locked.status not in EDITABLE:
            raise IllegalTransition(f"cannot edit a version in {locked.status}")
        locked.content = content
        locked.save(update_fields=["content"])
        _log(locked, actor, "edit", locked.status, locked.status, snapshot=content)
        _refresh(version, locked)
        if locked.status == PENDING_REVIEW:
            transition(version, VALIDATING, actor)
    return version


def transition(version: LessonVersion, to: str, actor, note: str = "") -> LessonVersion:
    """Move a version to another status. actor=None means the system (validation results)."""
    _check_actor(actor)
    if to == PUBLISHED:
        return publish(version, actor)
    if to == REJECTED and not note.strip():
        raise ValueError("note")
    with transaction.atomic():
        locked = LessonVersion.objects.select_for_update().get(pk=version.pk)
        check_transition(locked.status, to)
        previous = locked.status
        locked.status = to
        fields = ["status"]
        if to == APPROVED:
            locked.reviewed_by, locked.reviewed_at = actor, timezone.now()
            fields += ["reviewed_by", "reviewed_at"]
        locked.save(update_fields=fields)
        _log(locked, actor, "transition", previous, to, note.strip())
    _refresh(version, locked)
    return version


def publish(version: LessonVersion, actor) -> LessonVersion:
    """Make an approved version the one learners get; the previously published one is archived."""
    _check_actor(actor)
    with transaction.atomic():
        lesson = Lesson.objects.select_for_update().get(pk=version.lesson_id)
        locked = LessonVersion.objects.select_for_update().get(pk=version.pk)
        check_transition(locked.status, PUBLISHED)
        old = lesson.published_version
        if old is not None and old.pk != locked.pk:
            LessonVersion.objects.filter(pk=old.pk).update(status=ARCHIVED)
            _log(old, actor, "transition", PUBLISHED, ARCHIVED, f"replaced by v{locked.number}")
        locked.status, locked.published_at = PUBLISHED, timezone.now()
        locked.save(update_fields=["status", "published_at"])
        lesson.published_version = locked
        lesson.save(update_fields=["published_version"])
        _log(locked, actor, "transition", APPROVED, PUBLISHED)
    _refresh(version, locked)
    return version


def published_content(lesson: Lesson) -> tuple[LessonVersion, dict] | None:
    """The version learners get, with its content; None while nothing is published."""
    version = lesson.published_version
    if version is None or version.status != PUBLISHED:
        return None
    return version, version.content


def _refresh(target: LessonVersion, source: LessonVersion) -> None:
    for field in ("status", "reviewed_by_id", "reviewed_at", "published_at", "content"):
        setattr(target, field, getattr(source, field))
