"""Observation lists for the skill estimate and diagnosis tests."""
from datetime import date, timedelta

from skills.domain.estimate import Observation


def obs(n, solved=(), days=1, difficulty=1500, start=date(2026, 11, 1), learner_rating=1500):
    """n observations, success at the indexes in `solved`, spread round-robin over `days` dates."""
    solved = set(solved)
    return [Observation(i in solved, start + timedelta(days=i % days), difficulty, learner_rating) for i in range(n)]
