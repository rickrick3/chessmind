"""The skill vocabulary: the PRD's nine skill areas, the Lichess puzzle themes, and lesson step tags. Pure.

Every puzzle is evidence for tactics; some themes also feed calculation, defence or endgames. Lesson step tags are area
keys or Lichess theme keys; ALIASES maps the tags the milestone 1 seed lessons were written with.
"""
from collections.abc import Iterable

AREAS = ("tactics", "calculation", "openings", "positional", "strategy", "endgames", "defense", "decisions", "time")

TACTIC_MOTIFS = frozenset({
    "fork", "pin", "skewer", "discoveredAttack", "discoveredCheck", "doubleCheck", "hangingPiece", "trappedPiece",
    "deflection", "attraction", "clearance", "interference", "xRayAttack", "capturingDefender", "sacrifice",
    "intermezzo", "quietMove", "zugzwang", "defensiveMove", "attackingF2F7", "exposedKing", "promotion",
    "underPromotion", "advancedPawn",
})
NAMED_MATES = frozenset({
    "anastasiaMate", "arabianMate", "backRankMate", "balestraMate", "blindSwineMate", "bodenMate", "cornerMate",
    "doubleBishopMate", "dovetailMate", "epauletteMate", "hookMate", "killBoxMate", "morphysMate", "operaMate",
    "pillsburysMate", "smotheredMate", "swallowstailMate", "triangleMate", "vukovicMate",
})
MATES = NAMED_MATES | {"mate", "mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5"}
ENDGAME_TYPES = frozenset({"bishopEndgame", "knightEndgame", "pawnEndgame", "queenEndgame", "queenRookEndgame",
                           "rookEndgame"})

MOTIF_THEMES = TACTIC_MOTIFS | MATES | ENDGAME_TYPES  # the themes that can be diagnosed
TACTICS_THEMES = TACTIC_MOTIFS | MATES
# Phase, length, evaluation and source themes, plus themes about a kind of move or a side of the board: they feed
# areas through PUZZLE_AREA_THEMES but are never diagnosed on their own.
NOT_DIAGNOSED = frozenset({
    "opening", "middlegame", "endgame", "oneMove", "short", "long", "veryLong", "advantage", "crushing", "equality",
    "master", "masterVsMaster", "superGM", "castling", "enPassant", "collinearMove", "kingsideAttack",
    "queensideAttack",
})
ALL_THEMES = MOTIF_THEMES | NOT_DIAGNOSED

PUZZLE_AREA_THEMES = {
    "calculation": frozenset({"long", "veryLong", "mateIn3", "mateIn4", "mateIn5", "intermezzo", "quietMove"}),
    "defense": frozenset({"defensiveMove", "equality"}),
    "endgames": frozenset({"endgame", "zugzwang"}) | ENDGAME_TYPES,
}

ALIASES: dict[str, str | None] = {
    "defence": "defense", "threats": "defense", "defenders": "defense", "back-rank": "backRankMate",
    "smothered": "smotheredMate", "cct": "tactics", "checks": "tactics", "captures": "tactics",
    "piece-values": None, "trades": None, "queen": None,
}

LESSON_KIND_AREA = {"tactic": "tactics", "opening": "openings", "endgame": "endgames"}


def puzzle_areas(themes: Iterable[str]) -> set[str]:
    found = set(themes)
    return {"tactics"} | {area for area, keys in PUZZLE_AREA_THEMES.items() if keys & found}


def canonical_tags(tags: Iterable[str]) -> list[str]:
    """Aliases applied; tags that map to nothing and unknown tags dropped; first-seen order, no duplicates."""
    out: list[str] = []
    for tag in tags:
        tag = ALIASES.get(tag, tag)
        if tag is not None and (tag in AREAS or tag in ALL_THEMES) and tag not in out:
            out.append(tag)
    return out


def unknown_tags(tags: Iterable[str]) -> list[str]:
    return [t for t in tags if t not in AREAS and t not in ALL_THEMES and t not in ALIASES]


def _theme_areas(theme: str) -> set[str]:
    areas = {"tactics"} if theme in TACTICS_THEMES else set()
    return areas | {area for area, keys in PUZZLE_AREA_THEMES.items() if theme in keys}


def lesson_step_areas(tags: Iterable[str], lesson_kind: str) -> set[str]:
    areas: set[str] = set()
    for tag in canonical_tags(tags):
        areas |= {tag} if tag in AREAS else _theme_areas(tag)
    if not areas and lesson_kind in LESSON_KIND_AREA:
        areas = {LESSON_KIND_AREA[lesson_kind]}
    return areas


def diagnosable(theme: str) -> bool:
    return theme in MOTIF_THEMES
