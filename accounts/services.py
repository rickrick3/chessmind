"""Learner use cases: guests, accounts, settings."""
from functools import lru_cache
from zoneinfo import available_timezones

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.db import transaction

from .models import Learner
from .signals import merge_learners


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


# --- Accounts ---------------------------------------------------------------

def signup_user(request, *, email: str, password: str, display_name: str = "", timezone: str | None = None):
    """Create an account. A guest in this session becomes the account (nothing moves); otherwise a new learner."""
    email = email.strip().lower()
    with transaction.atomic():
        user = get_user_model().objects.create_user(username=email, email=email, password=password)
        learner = getattr(request, "learner", None)
        if learner is not None and learner.is_guest:
            learner.user = user
        else:
            learner = Learner(user=user, language=request_language(request))
        if display_name:
            learner.display_name = display_name
        if valid_timezone(timezone):
            learner.timezone = timezone
        learner.save()
    login(request, user)
    request.session.pop("learner_id", None)
    request.learner = learner
    return user


def login_user(request, user) -> Learner:
    """Log in; a guest with progress in this session is merged into the account's learner."""
    guest = getattr(request, "learner", None)
    login(request, user)
    target, _ = Learner.objects.get_or_create(user=user, defaults={"language": request_language(request)})
    if guest is not None and guest.is_guest and guest.pk != target.pk:
        with transaction.atomic():
            merge_learners.send(sender=Learner, source=guest, target=target)
            guest.delete()
        target.refresh_from_db()
    request.session.pop("learner_id", None)
    request.learner = target
    return target


def _failure_key(email: str, ip: str) -> str:
    return f"login-fail:{email}:{ip}"


def login_blocked(email: str, ip: str) -> bool:
    return cache.get(_failure_key(email, ip), 0) >= settings.LOGIN_FAILURE_LIMIT


def record_login_failure(email: str, ip: str) -> None:
    key = _failure_key(email, ip)
    if not cache.add(key, 1, settings.LOGIN_FAILURE_WINDOW):
        try:
            cache.incr(key)
        except ValueError:  # expired between add and incr
            cache.set(key, 1, settings.LOGIN_FAILURE_WINDOW)


def clear_login_failures(email: str, ip: str) -> None:
    cache.delete(_failure_key(email, ip))
