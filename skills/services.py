"""The evidence ledger and the skill profile built from it. Callers own the transaction."""
from dataclasses import dataclass
from datetime import date, datetime

from django.utils.translation import gettext

from accounts.models import Learner
from learning.models import LessonAttempt, StepResult
from puzzles.models import PuzzleAttempt, PuzzleRating

from .domain.areas import (
    AREAS, ENDGAME_TYPES, MOTIF_THEMES, PUZZLE_AREA_THEMES, TACTICS_THEMES, canonical_tags, diagnosable,
    lesson_step_areas, puzzle_areas,
)
from .domain.diagnosis import repeated_mistake, status
from .domain.estimate import Estimate, Observation, SkillRules, estimate
from .labels import area_label, theme_label
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


def on_merge(sender, source: Learner, target: Learner, **kwargs) -> None:
    """A guest logged into an account (runs after the learning and puzzles receivers): evidence moves, evidence
    of attempts that no longer count is dropped, and the profile is rebuilt."""
    from django.utils import timezone

    Evidence.objects.filter(learner=source).update(learner=target)
    Evidence.objects.filter(learner=target, source="puzzle", puzzle_attempt__rated=False).delete()
    firsts: dict[int, object] = {}
    for lesson_id, attempt_id in (LessonAttempt.objects.filter(learner=target, finished_at__isnull=False)
                                  .order_by("finished_at").values_list("lesson_id", "id")):
        firsts.setdefault(lesson_id, attempt_id)
    (Evidence.objects.filter(learner=target, source="lesson")
     .exclude(step_result__attempt_id__in=list(firsts.values())).delete())
    SkillEstimate.objects.filter(learner=source).delete()
    SkillHistory.objects.filter(learner=source).delete()
    recompute(target, timezone.now())


# --- what the Skills pages show ------------------------------------------------------------------------------

RECENT = 20


@dataclass(frozen=True)
class AreaRow:
    key: str
    label: str
    basis: str
    low: int | None
    high: int | None
    percent: int | None
    observations: int
    confidence: str
    comparison: str
    status: str


def _area_themes(area: str) -> frozenset[str]:
    if area == "tactics":
        return TACTICS_THEMES
    if area == "calculation":
        return PUZZLE_AREA_THEMES["calculation"] & MOTIF_THEMES
    if area == "defense":
        return frozenset({"defensiveMove"})
    if area == "endgames":
        return ENDGAME_TYPES | {"zugzwang"}
    return frozenset()


def _as_row(key: str, label: str, est: SkillEstimate | None) -> AreaRow:
    if est is None:
        return AreaRow(key, label, "none", None, None, None, 0, "none", "", "")
    percent = round(est.value * 100) if est.basis == "lesson" and est.value is not None else None
    return AreaRow(key, label, est.basis, est.low, est.high, percent, est.observations, est.confidence,
                   est.comparison, est.status)


def overview(learner: Learner) -> dict:
    from puzzles.domain.glicko2 import Rating
    from puzzles.services import rating_view

    cached = PuzzleRating.objects.filter(learner=learner).first()
    rating = rating_view(Rating(cached.rating, cached.rd, cached.volatility)) if cached else None
    estimates = {e.key: e for e in SkillEstimate.objects.filter(learner=learner, kind="area")}
    return {"rating": rating, "rated_count": cached.rated_count if cached else 0,
            "areas": [_as_row(a, area_label(a), estimates.get(a)) for a in AREAS],
            "has_evidence": Evidence.objects.filter(learner=learner).exists()}


def area_detail(learner: Learner, area: str) -> dict:
    """The area's estimate, its themes, where its evidence came from and the last observations. KeyError if the
    area does not exist."""
    if area not in AREAS:
        raise KeyError(area)
    est = SkillEstimate.objects.filter(learner=learner, kind="area", key=area).first()
    keys = _area_themes(area)
    themes = [_as_row(e.key, theme_label(e.key), e)
              for e in SkillEstimate.objects.filter(learner=learner, kind="theme", key__in=list(keys)).order_by("key")]
    rows = Evidence.objects.filter(learner=learner, area=area)
    sources = {"puzzle": rows.filter(source="puzzle").count(), "lesson": rows.filter(source="lesson").count()}
    recent = []
    for e in (rows.select_related("puzzle_attempt__puzzle", "step_result__attempt__lesson__published_version")
              .order_by("-created_at", "-id")[:RECENT]):
        if e.source == "puzzle":
            puzzle = e.puzzle_attempt.puzzle
            label = " · ".join([gettext("Puzzle"), str(puzzle.rating)] + [theme_label(t) for t in puzzle.themes
                                                                         if diagnosable(t)])
            url = f"/train/puzzles/{puzzle.lichess_id}/"
        else:
            lesson = e.step_result.attempt.lesson
            label, url = _lesson_title(lesson, learner.language), f"/lessons/{lesson.slug}/"
        recent.append({"date": e.local_date, "success": e.success, "source": e.source, "label": label, "url": url})
    return {"area": _as_row(area, area_label(area), est), "themes": themes, "sources": sources, "recent": recent}


def _lesson_title(lesson, lang: str) -> str:
    version = lesson.published_version
    title = (version.content.get("meta", {}).get("title") if version else None) or {}
    return (title.get(lang) or title.get("en") or lesson.slug) if isinstance(title, dict) else str(title)
