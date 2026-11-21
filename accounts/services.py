"""Learner use cases: guests, accounts, settings."""
from functools import lru_cache
from zoneinfo import available_timezones

from .models import Learner


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())


def valid_timezone(name: str | None) -> bool:
    return bool(name) and name in _zones()


def request_language(request) -> str:
    return "fr" if (getattr(request, "LANGUAGE_CODE", "") or "").startswith("fr") else "en"


def ensure_learner(request, *, timezone: str | None = None) -> Learner:
    """The request's learner, or a new guest bound to this session. Called at the first learning action."""
    learner = getattr(request, "learner", None)
    if learner is not None:
        return learner
    learner = Learner.objects.create(language=request_language(request),
                                     timezone=timezone if valid_timezone(timezone) else "UTC")
    request.session["learner_id"] = learner.id
    request.learner = learner
    return learner
