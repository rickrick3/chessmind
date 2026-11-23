"""Strengths and weaknesses from an estimate and its evidence (design 5.8, PRD 5.2). Pure: no database.

A single miss is only ever an isolated error. Weaknesses and strengths need an estimate with enough evidence;
"repeated mistake" is kept for the coach and never shown to the learner.
"""
from datetime import date

from .estimate import Estimate, Observation, SkillRules, performance

STATUSES = ("", "improving", "confirmed_weakness", "emerging_weakness", "stable_strength")


def _rate(observations: list[Observation]) -> float:
    return sum(1 for o in observations if o.success) / len(observations)


def _improving(est: Estimate, puzzle_obs: list[Observation], lesson_obs: list[Observation], rules: SkillRules) -> bool:
    k = rules.improving_split
    if est.basis == "puzzle" and len(puzzle_obs) >= 2 * k:
        newest, before = puzzle_obs[-k:], puzzle_obs[-2 * k:-k]
        return (performance([(o.difficulty, o.success) for o in newest])
                - performance([(o.difficulty, o.success) for o in before])) >= rules.improving_points
    if est.basis == "lesson" and len(lesson_obs) >= 2 * k:
        return _rate(lesson_obs[-k:]) - _rate(lesson_obs[-2 * k:-k]) >= rules.improving_rate
    return False


def status(est: Estimate, puzzle_obs: list[Observation], lesson_obs: list[Observation], rules: SkillRules) -> str:
    """One of STATUSES. Precedence: improving, confirmed weakness, emerging weakness, stable strength."""
    if est.basis == "none":
        return ""
    if _improving(est, puzzle_obs, lesson_obs, rules):
        return "improving"
    if est.basis == "puzzle":
        weak, strong = est.comparison == "weaker", est.comparison == "stronger"
    else:
        weak, strong = est.value < rules.lesson_weak, est.value > rules.lesson_strong
    if weak:
        return "confirmed_weakness" if est.confidence == "reliable" else "emerging_weakness"
    if strong and est.confidence == "reliable":
        return "stable_strength"
    return ""


def repeated_mistake(puzzle_obs: list[Observation], today: date, rules: SkillRules) -> bool:
    """The same theme missed again and again recently, on puzzles the learner was expected to solve."""
    misses = [o for o in puzzle_obs
              if not o.success and (today - o.local_date).days < rules.repeated_days
              and o.difficulty is not None and o.learner_rating is not None and o.difficulty <= o.learner_rating]
    return len(misses) >= rules.repeated_misses
