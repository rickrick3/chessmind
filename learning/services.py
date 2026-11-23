"""Learning use cases: what is unlocked, starting and finishing attempts, progress."""
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction

from curriculum.models import Lesson
from curriculum.services import published_content
from gamification.domain.achievements import ProgressStats
from gamification.services import award_for_attempt
from skills.services import recompute, record_lesson_evidence

from .domain.scoring import score_attempt
from .domain.unlock import LessonNode, lesson_states, next_up
from .models import LessonAttempt, LessonProgress, StepResult

START_LEVELS = ("new", "rules", "club")


class Locked(Exception):
    """The learner hasn't unlocked this lesson yet."""


class NotPublished(Exception):
    """The lesson has no published version."""


class Expired(Exception):
    """The attempt started too long ago to be finished."""


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


def progress_stats(learner) -> ProgressStats:
    done = LessonProgress.objects.filter(learner=learner, first_completed_at__isnull=False)
    done_slugs = set(done.values_list("lesson__slug", flat=True))
    units: dict[int, set[str]] = {}
    for unit_id, slug in published_lessons().values_list("unit_id", "slug"):
        units.setdefault(unit_id, set()).add(slug)
    return ProgressStats(lessons_completed=len(done_slugs),
                         units_completed=sum(1 for slugs in units.values() if slugs <= done_slugs),
                         perfect_lessons=done.filter(best_accuracy__gte=1.0).count())


def finish_attempt(learner, attempt_id, steps: list[dict], now: datetime) -> dict:
    """Score the tries against the pinned version, record progress and XP. A repeat call returns the same result."""
    with transaction.atomic():
        attempt = (LessonAttempt.objects.select_for_update(of=("self",)).select_related("version", "lesson")
                   .get(pk=attempt_id, learner=learner))
        if attempt.finished_at is not None:
            return attempt.result
        if now - attempt.started_at > timedelta(hours=settings.ATTEMPT_EXPIRY_HOURS):
            raise Expired(str(attempt_id))
        scored = score_attempt(attempt.version.content, steps)  # InvalidResult: nothing written yet

        nodes = path_nodes()
        before = states_for(learner, nodes)
        step_results = StepResult.objects.bulk_create([
            StepResult(attempt=attempt, step_id=s.step_id, step_type=s.step_type, correct=s.correct,
                       cleared=s.cleared, tries=s.tries, hints=s.hints, ms=s.ms, skills=s.skills)
            for s in scored.steps])
        progress, _ = LessonProgress.objects.select_for_update().get_or_create(learner=learner,
                                                                              lesson=attempt.lesson)
        first_completion = scored.completed and progress.first_completed_at is None
        if scored.completed:
            progress.completions += 1
            progress.best_accuracy = max(progress.best_accuracy, scored.accuracy)
            if first_completion:
                progress.first_completed_at = now
        progress.last_attempt_at = now
        progress.save()
        after = states_for(learner, nodes)
        unlocked = [n.slug for n in nodes if before.get(n.slug) == "locked" and after.get(n.slug) != "locked"]

        award = award_for_attempt(learner, attempt, completed=scored.completed, accuracy=scored.accuracy,
                                  first_completion=first_completion, stats=progress_stats(learner), now=now)
        result = {"completed": scored.completed, "accuracy": scored.accuracy, "xp": award["xp"],
                  "streak": award["streak"], "daily_goal": award["daily_goal"], "unlocked": unlocked,
                  "achievements": award["achievements"], "new_cards": 0}
        attempt.finished_at, attempt.completed, attempt.accuracy = now, scored.completed, scored.accuracy
        attempt.xp_awarded, attempt.result = award["xp"]["awarded"], result
        attempt.save(update_fields=["finished_at", "completed", "accuracy", "xp_awarded", "result"])
        record_lesson_evidence(attempt, step_results, learner.local_date(now))
        recompute(learner, now)
    return result
