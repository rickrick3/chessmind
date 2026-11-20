"""Win chances and move grades, as Lichess computes them."""
import math

BAD_GRADES = {"inaccuracy", "mistake", "blunder"}


def win_percent(cp: int | None, mate: int | None) -> float:
    """Winning chances (0-100) for the side whose score this is."""
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    cp = max(-1000, min(1000, cp or 0))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def wp_of(analysis) -> float:
    """Winning chances for the side to move in this position."""
    return win_percent(analysis.cp, analysis.mate)


def mover_wp_after(analysis_after) -> float:
    """After a move the opponent is to move, so flip their winning chances to the mover's."""
    return 100.0 - wp_of(analysis_after)


def grade_move(wp_before: float, wp_after: float, is_engine_best: bool) -> str:
    drop = wp_before - wp_after
    if drop >= 30:
        return "blunder"
    if drop >= 20:
        return "mistake"
    if drop >= 10:
        return "inaccuracy"
    return "best" if is_engine_best else "good"


def is_key_moment(grade: str) -> bool:
    return grade in BAD_GRADES
