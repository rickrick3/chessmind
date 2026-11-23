"""Puzzle positions shared by the tests and the end-to-end tests, all checked with python-chess.

`fen` is the position before the opponent's move, as in the Lichess puzzle file.
"""

MATE2 = {  # Lichess 00sHx, rating 1760: 1...Kd7 2.Be6+ Kd8 3.Qf8#
    "fen": "q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17",
    "moves": ["e8d7", "a2e6", "d7d8", "f7f8"],
    "start_fen": "q5nr/1ppknQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 w - - 1 18",
    "side": "white",
    "wrong_first": "f7f6",      # legal, not the solution, not mate
    "wrong_second": "a3b4",     # legal after 2.Be6+ Kd8, not mate
    "illegal_first": "a2a8",
    "themes": ["mate", "mateIn2", "middlegame", "short"],
}

ALT_MATE = {  # 1...c6 2.Ra8#; 2.Rb8# also mates
    "fen": "7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1",
    "moves": ["c7c6", "a1a8"],
    "side": "white",
    "alternative": "b1b8",
    "themes": ["backRankMate", "mate", "mateIn1", "oneMove", "endgame"],
}

PROMOTION = {  # 1...h6 2.g8=Q#; 2.g8=R# also mates
    "fen": "k7/6Pp/1K6/8/8/8/8/8 b - - 0 1",
    "moves": ["h7h6", "g7g8q"],
    "side": "white",
    "alternative": "g7g8r",
    "themes": ["promotion", "mate", "mateIn1", "oneMove", "endgame", "pawnEndgame"],
}

SOLVED = {"played": ["a2e6", "f7f8"], "hints": 0, "solution_shown": False, "ms": 9000}  # for MATE2
MISSED = {"played": [MATE2["wrong_first"]], "hints": 0, "solution_shown": False, "ms": 4000}  # for MATE2


def serve(learner, puzzle, when=None):
    """A rated attempt served to the learner, as next_puzzle would create it."""
    from django.utils import timezone

    from puzzles.models import PuzzleAttempt

    return PuzzleAttempt.objects.create(learner=learner, puzzle=puzzle, mode="rated",
                                        served_at=when or timezone.now())
