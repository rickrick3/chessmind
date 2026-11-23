"""What learners read for skill areas and puzzle themes: our own wording, in English and French (locale/fr)."""
from django.utils.translation import gettext_lazy as _

AREA_LABELS = {
    "tactics": _("Tactics"), "calculation": _("Calculation"), "openings": _("Openings"),
    "positional": _("Positional play"), "strategy": _("Strategy"), "endgames": _("Endgames"),
    "defense": _("Defence"), "decisions": _("Decisions"), "time": _("Time management"),
}

THEME_LABELS = {
    "advancedPawn": _("Advanced pawn"), "advantage": _("Winning an advantage"), "anastasiaMate": _("Anastasia's mate"),
    "arabianMate": _("Arabian mate"), "attackingF2F7": _("Attacking f2 or f7"), "attraction": _("Attraction"),
    "backRankMate": _("Back-rank mate"), "balestraMate": _("Balestra mate"), "blindSwineMate": _("Blind swine mate"),
    "bishopEndgame": _("Bishop endgame"), "bodenMate": _("Boden's mate"), "castling": _("Castling"),
    "capturingDefender": _("Capturing the defender"), "collinearMove": _("Collinear move"),
    "cornerMate": _("Corner mate"), "crushing": _("Crushing"), "discoveredCheck": _("Discovered check"),
    "doubleBishopMate": _("Double bishop mate"), "dovetailMate": _("Dovetail mate"), "equality": _("Saving the game"),
    "kingsideAttack": _("Kingside attack"), "clearance": _("Clearance"), "defensiveMove": _("Defensive move"),
    "deflection": _("Deflection"), "discoveredAttack": _("Discovered attack"), "doubleCheck": _("Double check"),
    "endgame": _("Endgame"), "enPassant": _("En passant"), "epauletteMate": _("Epaulette mate"),
    "exposedKing": _("Exposed king"), "fork": _("Fork"), "hangingPiece": _("Hanging piece"),
    "hookMate": _("Hook mate"), "interference": _("Interference"), "intermezzo": _("In-between move"),
    "killBoxMate": _("Kill box mate"), "pillsburysMate": _("Pillsbury's mate"), "morphysMate": _("Morphy's mate"),
    "swallowstailMate": _("Swallow's tail mate"), "triangleMate": _("Triangle mate"), "vukovicMate": _("Vukovic mate"),
    "knightEndgame": _("Knight endgame"), "long": _("Long puzzle"), "master": _("Master game"),
    "masterVsMaster": _("Master vs master"), "mate": _("Checkmate"), "mateIn1": _("Mate in 1"),
    "mateIn2": _("Mate in 2"), "mateIn3": _("Mate in 3"), "mateIn4": _("Mate in 4"), "mateIn5": _("Mate in 5 or more"),
    "middlegame": _("Middlegame"), "oneMove": _("One move"), "opening": _("Opening"), "operaMate": _("Opera mate"),
    "pawnEndgame": _("Pawn endgame"), "pin": _("Pin"), "promotion": _("Promotion"), "queenEndgame": _("Queen endgame"),
    "queenRookEndgame": _("Queen and rook endgame"), "queensideAttack": _("Queenside attack"),
    "quietMove": _("Quiet move"), "rookEndgame": _("Rook endgame"), "sacrifice": _("Sacrifice"),
    "short": _("Short puzzle"), "skewer": _("Skewer"), "smotheredMate": _("Smothered mate"),
    "superGM": _("Super GM game"), "trappedPiece": _("Trapped piece"), "underPromotion": _("Underpromotion"),
    "veryLong": _("Very long puzzle"), "xRayAttack": _("X-ray attack"), "zugzwang": _("Zugzwang"),
}


def area_label(key: str) -> str:
    return str(AREA_LABELS.get(key, key))


def theme_label(key: str) -> str:
    return str(THEME_LABELS.get(key, key))
