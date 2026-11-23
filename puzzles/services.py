"""Serving, finishing and rating puzzles. Rules live in puzzles.domain; this module owns the transactions."""
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef
from django.db.models.functions import Abs
from django.utils import translation

from accounts.models import Learner
from gamification.services import award_for_puzzle
from learning.services import progress_stats
from skills.domain.areas import ALL_THEMES
from skills.domain.estimate import round50
from skills.labels import theme_label
from skills.services import recompute, record_puzzle_evidence

from .domain.glicko2 import Game, Rating, idle, rate
from .domain.selection import target
from .domain.solution import score_puzzle
from .models import Puzzle, PuzzleAttempt, PuzzleRating

MODES = ("rated", "theme")
DIFFICULTIES = ("easier", "normal", "harder")


class NoPuzzleLeft(Exception):
    """The learner has been served every active puzzle of this mode."""


class Expired(Exception):
    """The puzzle was served more than ATTEMPT_EXPIRY_HOURS ago."""


def start_rating(learner: Learner) -> Rating:
    rating = settings.PUZZLE_START_RATINGS.get(learner.start_level, settings.PUZZLE_DEFAULT_START)
    return Rating(rating, settings.PUZZLE_START_RD, settings.PUZZLE_START_VOLATILITY)


def current_rating(learner: Learner) -> Rating:
    cached = PuzzleRating.objects.filter(learner=learner).first()
    if cached is None:
        return start_rating(learner)
    return Rating(cached.rating, cached.rd, cached.volatility)


def _open_attempt(learner: Learner, mode: str, theme: str, now: datetime) -> PuzzleAttempt | None:
    since = now - timedelta(hours=settings.ATTEMPT_EXPIRY_HOURS)
    return (PuzzleAttempt.objects.filter(learner=learner, mode=mode, theme=theme, finished_at__isnull=True,
                                         served_at__gt=since, served_at__lte=now, puzzle__is_active=True)
            .select_related("puzzle").order_by("-served_at").first())


def _pick(learner: Learner, theme: str, aim: int) -> Puzzle | None:
    unseen = (Puzzle.objects.filter(is_active=True)
              .filter(~Exists(PuzzleAttempt.objects.filter(learner=learner, puzzle=OuterRef("pk")))))
    if theme:
        unseen = unseen.filter(themes__contains=[theme])
    for window in settings.PUZZLE_WINDOWS:
        found = unseen.filter(rating__gte=aim - window, rating__lte=aim + window).order_by("?").first()
        if found is not None:
            return found
    return unseen.annotate(gap=Abs(F("rating") - aim)).order_by("gap", "id").first()


def next_puzzle(learner: Learner, *, mode: str, theme: str = "", difficulty: str = "normal",
                now: datetime) -> PuzzleAttempt:
    """The learner's open attempt in this mode, or a new one on an unseen puzzle near their level."""
    if mode not in MODES or difficulty not in DIFFICULTIES:
        raise ValueError("unknown mode or difficulty")
    if (mode == "theme") != bool(theme) or (theme and theme not in ALL_THEMES):
        raise ValueError("theme mode needs a known theme, rated mode none")
    attempt = _open_attempt(learner, mode, theme, now)
    if attempt is not None:
        return attempt
    aim = target(current_rating(learner).rating, difficulty, settings.PUZZLE_DIFFICULTY_OFFSETS)
    for _ in range(2):  # a concurrent request may take the same puzzle: pick again once
        puzzle = _pick(learner, theme, aim)
        if puzzle is None:
            raise NoPuzzleLeft(mode)
        try:
            with transaction.atomic():
                return PuzzleAttempt.objects.create(learner=learner, puzzle=puzzle, mode=mode, theme=theme,
                                                    served_at=now, rated=True)
        except IntegrityError:
            continue
    raise NoPuzzleLeft(mode)


def rating_view(rating: Rating) -> dict:
    """How a rating is shown: a range rounded to 50, never one exact number."""
    return {"value": round(rating.rating), "low": round50(rating.rating - rating.rd),
            "high": round50(rating.rating + rating.rd), "settling": rating.rd > settings.PUZZLE_SETTLING_RD}


def idle_periods(last_rated_on, today) -> int:
    """One Glicko-2 rating period per local day without puzzles."""
    return 0 if last_rated_on is None else max(0, (today - last_rated_on).days - 1)


def updated_rating(before: Rating, puzzle: Puzzle, solved: bool, periods: int) -> Rating:
    after = rate(idle(before, periods, settings.PUZZLE_RD_MAX),
                 [Game(puzzle.rating, puzzle.rating_deviation, 1.0 if solved else 0.0)], settings.PUZZLE_TAU)
    return Rating(after.rating, max(after.rd, settings.PUZZLE_RD_FLOOR), after.volatility)


def _rating_result(before: Rating, after: Rating) -> dict:
    view = rating_view(after)
    return {"before": round(before.rating), "after": round(after.rating),
            "change": round(after.rating) - round(before.rating), "low": view["low"], "high": view["high"],
            "settling": view["settling"]}


def finish_puzzle(learner: Learner, attempt_id, body: dict, now: datetime) -> dict:
    """Score the moves against the puzzle, then rate, award and record evidence. A repeat call returns the same
    result. Raises PuzzleAttempt.DoesNotExist, Expired or InvalidPuzzleResult (then nothing is written)."""
    with transaction.atomic():
        attempt = (PuzzleAttempt.objects.select_for_update(of=("self",)).select_related("puzzle")
                   .get(pk=attempt_id, learner=learner))
        if attempt.finished_at is not None:
            return attempt.result
        if now - attempt.served_at > timedelta(hours=settings.ATTEMPT_EXPIRY_HOURS):
            raise Expired(str(attempt_id))
        puzzle = attempt.puzzle
        outcome = score_puzzle(puzzle.fen, puzzle.moves, body)
        today = learner.local_date(now)

        attempt.played, attempt.hints = list(outcome.played), outcome.hints
        attempt.solution_shown, attempt.ms = outcome.solution_shown, outcome.ms
        attempt.solved, attempt.finished_at = outcome.solved, now
        if attempt.rated:
            start = start_rating(learner)
            cache, _ = PuzzleRating.objects.select_for_update().get_or_create(
                learner=learner, defaults={"rating": start.rating, "rd": start.rd, "volatility": start.volatility,
                                           "start": start.rating})
            before = Rating(cache.rating, cache.rd, cache.volatility)
            after = updated_rating(before, puzzle, outcome.solved, idle_periods(cache.last_rated_on, today))
            cache.rating, cache.rd, cache.volatility = after.rating, after.rd, after.volatility
            cache.rated_count += 1
            cache.solved_count += int(outcome.solved)
            cache.last_rated_on = today
            cache.save()
            attempt.learner_rating_before, attempt.rating_after, attempt.rd_after = before.rating, after.rating, after.rd
            award = award_for_puzzle(learner, attempt, solved=outcome.solved, stats=progress_stats(learner), now=now)
        else:
            before = after = current_rating(learner)
            award = award_for_puzzle(learner, attempt, solved=False, stats=progress_stats(learner), now=now)
        attempt.save()
        if attempt.rated:
            record_puzzle_evidence(attempt, today)
            recompute(learner, now)
        with translation.override(learner.language):
            themes = [{"key": t, "label": theme_label(t)} for t in puzzle.themes]
        result = {"solved": outcome.solved, "rating": _rating_result(before, after), **award,
                  "puzzle": {"id": puzzle.lichess_id, "rating": puzzle.rating, "themes": themes,
                             "game_url": puzzle.game_url}}
        attempt.result = result
        attempt.save(update_fields=["result"])
    return result


def rebuild_rating(learner: Learner, start: float | None = None) -> PuzzleRating | None:
    """Replay the learner's rated, finished attempts in order from their start rating; the cache follows.
    The start is `start`, else the one the cache recorded, else the learner's start level."""
    attempts = list(PuzzleAttempt.objects.filter(learner=learner, rated=True, finished_at__isnull=False)
                    .select_related("puzzle").order_by("finished_at", "served_at"))
    if not attempts:
        PuzzleRating.objects.filter(learner=learner).delete()
        return None
    if start is None:
        start = PuzzleRating.objects.filter(learner=learner).values_list("start", flat=True).first()
    if start is None:
        start = start_rating(learner).rating
    rating = Rating(start, settings.PUZZLE_START_RD, settings.PUZZLE_START_VOLATILITY)
    last, solved = None, 0
    for a in attempts:
        day = learner.local_date(a.finished_at)
        rating = updated_rating(rating, a.puzzle, bool(a.solved), idle_periods(last, day))
        last, solved = day, solved + int(bool(a.solved))
    cache, _ = PuzzleRating.objects.update_or_create(learner=learner, defaults={
        "rating": rating.rating, "rd": rating.rd, "volatility": rating.volatility, "start": start,
        "rated_count": len(attempts), "solved_count": solved, "last_rated_on": last})
    return cache


def on_merge(sender, source: Learner, target: Learner, **kwargs) -> None:
    """A guest logged into an account: a puzzle both did stays rated once (the earlier attempt), attempts and
    reports move, and the rating is rebuilt from the combined history. XP events are moved by gamification."""
    from .models import PuzzleReport

    shared = (set(PuzzleAttempt.objects.filter(learner=source, rated=True).values_list("puzzle_id", flat=True))
              & set(PuzzleAttempt.objects.filter(learner=target, rated=True).values_list("puzzle_id", flat=True)))
    for puzzle_id in shared:
        pair = list(PuzzleAttempt.objects.filter(learner__in=(source, target), puzzle_id=puzzle_id, rated=True))
        pair.sort(key=lambda a: (a.finished_at is None, a.finished_at or a.served_at, a.served_at))
        PuzzleAttempt.objects.filter(pk__in=[a.pk for a in pair[1:]]).update(rated=False)
    PuzzleAttempt.objects.filter(learner=source).update(learner=target)
    reported = PuzzleReport.objects.filter(learner=target).values_list("puzzle_id", flat=True)
    PuzzleReport.objects.filter(learner=source, puzzle_id__in=list(reported)).delete()
    PuzzleReport.objects.filter(learner=source).update(learner=target)
    # An existing rating keeps its start: the account's if it had one, else the guest's. A start level the
    # account only now adopts from the guest must not rebase a rating that already exists.
    starts = dict(PuzzleRating.objects.filter(learner__in=(source, target)).values_list("learner_id", "start"))
    start = starts.get(target.pk) if target.pk in starts else starts.get(source.pk)
    PuzzleRating.objects.filter(learner=source).delete()
    rebuild_rating(target, start)
