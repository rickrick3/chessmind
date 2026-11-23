"""The Train hub, the puzzle page and the unrated replay of a puzzle the learner has already seen."""
from django.http import Http404
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.templatetags.static import static
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET

from accounts.services import request_language
from skills.domain.areas import ALL_THEMES
from skills.labels import area_label, theme_label

from .domain.glicko2 import Rating
from .models import Puzzle, PuzzleAttempt, PuzzleRating
from .services import rating_view

PICKER = [
    ("tactics", ["fork", "pin", "skewer", "discoveredAttack", "hangingPiece", "sacrifice"]),
    ("mates", ["mateIn1", "mateIn2", "mateIn3", "backRankMate"]),
    ("calculation", ["long", "quietMove", "intermezzo"]),
    ("defense", ["defensiveMove"]),
    ("endgames", ["pawnEndgame", "rookEndgame"]),
]
RECENT = 10


def _rating(learner) -> dict | None:
    cached = PuzzleRating.objects.filter(learner=learner).first() if learner is not None else None
    if cached is None:
        return None
    return {**rating_view(Rating(cached.rating, cached.rd, cached.volatility)), "count": cached.rated_count}


def _picker() -> list[dict]:
    return [{"label": gettext("Mates") if key == "mates" else area_label(key),
             "themes": [{"key": t, "label": theme_label(t)} for t in themes]} for key, themes in PICKER]


def _strings() -> dict:
    g = gettext
    return {
        "whiteToPlay": g("White to play — find the best move."),
        "blackToPlay": g("Black to play — find the best move."),
        "missed": g("Not this time — this puzzle counts as missed. Keep going to learn the idea."),
        "showAnswer": g("Here is the move. Play it."), "alsoMates": g("That mates too!"),
        "solved": g("Solved!"), "notSolved": g("Missed"), "next": g("Next puzzle"),
        "report": g("Report a problem"), "reportWrong": g("The solution is wrong"), "reportOther": g("Something else"),
        "reported": g("Thanks, we'll check this puzzle."), "viewGame": g("See the game on Lichess"),
        "puzzleRating": g("Puzzle rating"), "yourRating": g("Your rating"), "settling": g("still settling"),
        "about": g("about {low}–{high}"), "loadError": g("The puzzle could not load. Try again in a moment."),
        "notSaved": g("Not saved"), "savedLater": g("We'll save this when you're back online."),
        "stillOffline": g("Your last puzzle isn't saved yet. Check your connection, then try again."),
        "replayDone": g("Line complete. This replay doesn't change your rating."),
    }


def _config(request, **extra) -> dict:
    learner = request.learner
    return {"csrfToken": get_token(request), "assets": static("vendor/cm-chessboard/assets/"),
            "lang": learner.language if learner is not None else request_language(request),
            "isGuest": learner is None or learner.is_guest, "signupUrl": "/signup/?next=/train/puzzles/",
            "i18n": _strings(), **extra}


@require_GET
def train(request):
    return render(request, "puzzles/train.html", {"rating": _rating(request.learner)})


@require_GET
def puzzles(request):
    wanted = request.GET.get("theme", "")
    theme = wanted if wanted in ALL_THEMES else ""
    learner = request.learner
    recent = (list(PuzzleAttempt.objects.filter(learner=learner, finished_at__isnull=False)
                   .order_by("-finished_at")[:RECENT]) if learner is not None else [])
    config = _config(request, nextUrl="/api/v1/puzzles/next", finishUrl="/api/v1/puzzle-attempts/{id}/finish",
                     reportUrl="/api/v1/puzzles/{id}/report", mode="theme" if theme else "rated", theme=theme)
    return render(request, "puzzles/puzzles.html", {
        "config": config, "rating": _rating(learner), "picker": _picker(), "theme": theme,
        "theme_label": theme_label(theme) if theme else "", "recent": recent})


@require_GET
def replay(request, lichess_id):
    learner = request.learner
    puzzle = Puzzle.objects.filter(lichess_id=lichess_id).first()
    if learner is None or puzzle is None or not PuzzleAttempt.objects.filter(learner=learner, puzzle=puzzle).exists():
        raise Http404
    config = _config(request, puzzle={"fen": puzzle.fen, "moves": puzzle.moves, "side": puzzle.side})
    return render(request, "puzzles/replay.html", {"config": config, "puzzle": puzzle,
                                                   "themes": [theme_label(t) for t in puzzle.themes]})


TITLE = _("Puzzles")  # keeps the page title in the translation catalogue next to the views that use it
