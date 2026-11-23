"""Serving, finishing and rating puzzles. Rules live in puzzles.domain; this module owns the transactions."""
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Exists, F, OuterRef
from django.db.models.functions import Abs

from accounts.models import Learner
from skills.domain.areas import ALL_THEMES

from .domain.glicko2 import Rating
from .domain.selection import target
from .models import Puzzle, PuzzleAttempt, PuzzleRating

MODES = ("rated", "theme")
DIFFICULTIES = ("easier", "normal", "harder")


class NoPuzzleLeft(Exception):
    """The learner has been served every active puzzle of this mode."""


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
