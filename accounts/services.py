"""Learner use cases: guests, accounts, settings."""
from functools import lru_cache
from zoneinfo import available_timezones

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.db import transaction

from games import chesscom
from players.models import Player

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
        if valid_timezone(timezone) and not learner.timezone_confirmed:
            learner.timezone, learner.timezone_confirmed = timezone, True
            learner.save(update_fields=["timezone", "timezone_confirmed"])
        return learner
    learner = Learner.objects.create(language=request_language(request),
                                     timezone=timezone if valid_timezone(timezone) else "UTC",
                                     timezone_confirmed=valid_timezone(timezone))
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
            learner.timezone, learner.timezone_confirmed = timezone, True
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
            if guest.timezone_confirmed and not target.timezone_confirmed:
                Learner.objects.filter(pk=target.pk).update(timezone=guest.timezone, timezone_confirmed=True)
                target.refresh_from_db()  # the receivers below compute local days in the right zone
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


# --- Settings, Chess.com link, deletion ------------------------------------

class UnknownChessComUser(Exception):
    """No Chess.com player has this username."""


def update_settings(learner: Learner, *, display_name: str | None = None, language: str | None = None,
                    daily_goal_xp: int | None = None, timezone: str | None = None) -> Learner:
    """Change a learner's settings. Raises ValueError(<field name>) for an invalid value; nothing is saved then."""
    if language is not None and language not in ("fr", "en"):
        raise ValueError("language")
    if daily_goal_xp is not None and int(daily_goal_xp) not in settings.DAILY_GOAL_CHOICES:
        raise ValueError("daily_goal_xp")
    if timezone is not None and not valid_timezone(timezone):
        raise ValueError("timezone")
    if display_name is not None:
        learner.display_name = display_name.strip()[:40]
    if language is not None:
        learner.language = language
    if daily_goal_xp is not None:
        learner.daily_goal_xp = int(daily_goal_xp)
    if timezone is not None:
        learner.timezone, learner.timezone_confirmed = timezone, True
    learner.save()
    return learner


def link_chesscom(learner: Learner, username: str) -> Player:
    """Link a Chess.com username (checked to exist, not to be owned). Several learners may share one."""
    name = (username or "").strip().lower()
    if not name or chesscom.get_player(name) is None:  # may raise chesscom.ChessComUnavailable
        raise UnknownChessComUser(name)
    player, _ = Player.objects.get_or_create(chesscom_username=name, defaults={"language": learner.language})
    learner.player = player
    learner.save(update_fields=["player"])
    return player


def unlink_chesscom(learner: Learner) -> None:
    learner.player = None
    learner.save(update_fields=["player"])


def delete_account(request) -> None:
    """Delete the learner, its learning data and its user. Shared Player, Game and analysis rows stay."""
    learner = getattr(request, "learner", None)
    with transaction.atomic():
        if learner is not None:
            user = learner.user
            learner.delete()
            if user is not None:
                user.delete()
    request.session.flush()
    request.learner = None
