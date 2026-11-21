"""Learning use cases: what is unlocked, starting and finishing attempts, progress."""
from datetime import datetime

from curriculum.models import Lesson
from curriculum.services import published_content

from .domain.unlock import LessonNode, lesson_states, next_up
from .models import LessonAttempt, LessonProgress

START_LEVELS = ("new", "rules", "club")


class Locked(Exception):
    """The learner hasn't unlocked this lesson yet."""


class NotPublished(Exception):
    """The lesson has no published version."""


def published_lessons():
    return (Lesson.objects.filter(published_version__status="published", unit__course__is_active=True)
            .select_related("unit__course", "published_version")
            .order_by("unit__course__order", "unit__course__id", "unit__order", "unit__id", "order", "id"))


def path_nodes() -> list[LessonNode]:
    """Every published lesson as an unlock node, numbered within its course."""
    lessons = list(published_lessons().prefetch_related("prerequisites"))
    published = {lesson.slug for lesson in lessons}
    nodes, unit_rank, position = [], {}, {}
    for lesson in lessons:
        course = lesson.unit.course_id
        ranks = unit_rank.setdefault(course, {})
        ranks.setdefault(lesson.unit_id, len(ranks))
        position[course] = position.get(course, -1) + 1
        nodes.append(LessonNode(lesson.slug, lesson.unit.course.track, ranks[lesson.unit_id], position[course],
                                frozenset(p.slug for p in lesson.prerequisites.all() if p.slug in published)))
    return nodes


def _completed(learner) -> set[str]:
    if learner is None:
        return set()
    return set(LessonProgress.objects.filter(learner=learner, first_completed_at__isnull=False)
               .values_list("lesson__slug", flat=True))


def states_for(learner, nodes: list[LessonNode] | None = None) -> dict[str, str]:
    nodes = path_nodes() if nodes is None else nodes
    return lesson_states(nodes, _completed(learner), learner.start_level if learner else "")


def best_accuracies(learner) -> dict[str, float]:
    if learner is None:
        return {}
    return dict(LessonProgress.objects.filter(learner=learner).values_list("lesson__slug", "best_accuracy"))


def next_lesson(learner) -> str | None:
    nodes = path_nodes()
    return next_up(states_for(learner, nodes), nodes, best_accuracies(learner))


def set_start_level(learner, level: str) -> str | None:
    if level not in START_LEVELS:
        raise ValueError("level")
    learner.start_level = level
    learner.save(update_fields=["start_level"])
    return next_lesson(learner)


def start_attempt(learner, lesson: Lesson, now: datetime) -> LessonAttempt:
    lesson = Lesson.objects.select_related("published_version").get(pk=lesson.pk)  # the version live right now
    if published_content(lesson) is None:
        raise NotPublished(lesson.slug)
    if states_for(learner).get(lesson.slug, "locked") == "locked":
        raise Locked(lesson.slug)
    return LessonAttempt.objects.create(learner=learner, lesson=lesson, version=lesson.published_version,
                                        started_at=now)


def on_merge(sender, source, target, **kwargs) -> None:
    """A guest logged into an account: move attempts, combine progress, keep the account's start level."""
    LessonAttempt.objects.filter(learner=source).update(learner=target)
    for theirs in LessonProgress.objects.filter(learner=source):
        ours = LessonProgress.objects.filter(learner=target, lesson_id=theirs.lesson_id).first()
        if ours is None:
            theirs.learner = target
            theirs.save(update_fields=["learner"])
            continue
        ours.best_accuracy = max(ours.best_accuracy, theirs.best_accuracy)
        ours.first_completed_at = min((d for d in (ours.first_completed_at, theirs.first_completed_at) if d),
                                      default=None)
        ours.completions += theirs.completions
        ours.last_attempt_at = max((d for d in (ours.last_attempt_at, theirs.last_attempt_at) if d), default=None)
        ours.save()
        theirs.delete()
    if not target.start_level and source.start_level:
        target.start_level = source.start_level
        target.save(update_fields=["start_level"])
