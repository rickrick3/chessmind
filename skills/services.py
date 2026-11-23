"""The evidence ledger and the skill profile built from it. Callers own the transaction."""
from datetime import date, datetime

from accounts.models import Learner
from learning.models import LessonAttempt, StepResult
from puzzles.models import PuzzleAttempt, PuzzleRating

from .domain.areas import AREAS, canonical_tags, diagnosable, lesson_step_areas, puzzle_areas
from .domain.diagnosis import repeated_mistake, status
from .domain.estimate import Estimate, Observation, SkillRules, estimate
from .models import Evidence, SkillEstimate, SkillHistory

ESTIMATE_FIELDS = ["basis", "value", "low", "high", "observations", "days", "confidence", "comparison", "status",
                   "repeated_mistake"]


def _insert(rows: list[Evidence], existing) -> int:
    """Insert, skipping rows the ledger already has; returns how many were new."""
    before = existing.count()
    Evidence.objects.bulk_create(rows, ignore_conflicts=True)
    return existing.count() - before


def record_puzzle_evidence(attempt: PuzzleAttempt, local_date: date) -> int:
    """One evidence row per skill area the puzzle shows. Only rated, finished attempts count."""
    if not attempt.rated or attempt.finished_at is None:
        return 0
    puzzle = attempt.puzzle
    rows = [Evidence(learner_id=attempt.learner_id, area=area, source="puzzle", puzzle_attempt=attempt,
                     success=bool(attempt.solved), difficulty=puzzle.rating,
                     learner_rating=attempt.learner_rating_before, tags=list(puzzle.themes),
                     local_date=local_date, created_at=attempt.finished_at)
            for area in sorted(puzzle_areas(puzzle.themes))]
    return _insert(rows, Evidence.objects.filter(puzzle_attempt=attempt))


def _is_first_finish(attempt: LessonAttempt) -> bool:
    """No other attempt at this lesson finished earlier, and none already gave evidence (a replay finished at the
    same instant, or after the lesson was republished with new tags, still counts as a replay)."""
    others = (LessonAttempt.objects.filter(learner_id=attempt.learner_id, lesson_id=attempt.lesson_id,
                                           finished_at__isnull=False).exclude(pk=attempt.pk))
    if others.filter(finished_at__lt=attempt.finished_at).exists():
        return False
    return not Evidence.objects.filter(source="lesson", step_result__attempt__in=others).exists()


def record_lesson_evidence(attempt: LessonAttempt, step_results: list[StepResult], local_date: date) -> int:
    """Evidence from a lesson's scored steps, for the learner's first finished attempt at that lesson only."""
    if attempt.finished_at is None or not _is_first_finish(attempt):
        return 0
    kind = attempt.lesson.kind
    rows = [Evidence(learner_id=attempt.learner_id, area=area, source="lesson", step_result=sr, success=sr.correct,
                     tags=canonical_tags(sr.skills or []), local_date=local_date, created_at=attempt.finished_at)
            for sr in step_results for area in sorted(lesson_step_areas(sr.skills or [], kind))]
    return _insert(rows, Evidence.objects.filter(step_result__in=step_results))


def _observation(e: Evidence) -> Observation:
    return Observation(e.success, e.local_date, e.difficulty, e.learner_rating, tuple(e.tags))


def _row(learner: Learner, kind: str, key: str, est: Estimate, st: str, repeated: bool = False) -> SkillEstimate:
    return SkillEstimate(learner=learner, kind=kind, key=key, basis=est.basis, value=est.value, low=est.low,
                         high=est.high, observations=est.observations, days=est.days, confidence=est.confidence,
                         comparison=est.comparison, status=st, repeated_mistake=repeated)


def recompute(learner: Learner, now: datetime) -> None:
    """Rebuild the learner's area and theme estimates (and today's history) from the whole ledger."""
    rules = SkillRules.from_settings()
    today = learner.local_date(now)
    overall = PuzzleRating.objects.filter(learner=learner).values_list("rating", flat=True).first()
    puzzle_obs: dict[str, list[Observation]] = {a: [] for a in AREAS}
    lesson_obs: dict[str, list[Observation]] = {a: [] for a in AREAS}
    theme_obs: dict[str, list[Observation]] = {}
    for e in Evidence.objects.filter(learner=learner).order_by("created_at", "id"):
        o = _observation(e)
        (puzzle_obs if e.source == "puzzle" else lesson_obs)[e.area].append(o)
        if e.source == "puzzle" and e.area == "tactics":  # every puzzle has exactly one tactics row
            for theme in e.tags:
                if diagnosable(theme):
                    theme_obs.setdefault(theme, []).append(o)

    rows, history = [], []
    for area in AREAS:
        est = estimate(puzzle_obs[area], lesson_obs[area], overall, rules)
        rows.append(_row(learner, "area", area, est, status(est, puzzle_obs[area], lesson_obs[area], rules)))
        if est.basis != "none":
            history.append(SkillHistory(learner=learner, key=area, local_date=today, basis=est.basis, value=est.value,
                                        low=est.low, high=est.high, confidence=est.confidence))
    for theme, observations in sorted(theme_obs.items()):
        est = estimate(observations, [], overall, rules)
        rows.append(_row(learner, "theme", theme, est, status(est, observations, [], rules),
                         repeated_mistake(observations, today, rules)))

    SkillEstimate.objects.bulk_create(rows, update_conflicts=True, unique_fields=["learner", "kind", "key"],
                                      update_fields=ESTIMATE_FIELDS)
    SkillEstimate.objects.filter(learner=learner, kind="theme").exclude(key__in=list(theme_obs)).delete()
    if history:
        SkillHistory.objects.bulk_create(history, update_conflicts=True,
                                         unique_fields=["learner", "key", "local_date"],
                                         update_fields=["basis", "value", "low", "high", "confidence"])
