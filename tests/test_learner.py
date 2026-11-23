from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import Learner
from accounts.services import ensure_learner
from accounts.tasks import delete_idle_guests
from players.models import Player
from players.views import current_player

pytestmark = pytest.mark.django_db


def test_page_view_creates_no_learner(client):
    client.get("/games/")
    assert Learner.objects.count() == 0


def test_ensure_learner_one_guest_per_session(rf_with_session):
    req = rf_with_session(HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9")
    a = ensure_learner(req, timezone="Mars/Base")
    b = ensure_learner(req)
    assert a.id == b.id and a.is_guest and a.language == "fr" and a.timezone == "UTC"
    assert Learner.objects.count() == 1 and req.session["learner_id"] == a.id


def test_ensure_learner_keeps_valid_timezone(rf_with_session):
    learner = ensure_learner(rf_with_session(), timezone="America/Montreal")
    assert learner.timezone == "America/Montreal" and learner.language == "en"


def test_local_date_uses_learner_timezone():
    learner = Learner(timezone="Europe/Paris")
    assert learner.local_date(datetime(2026, 11, 21, 23, 30, tzinfo=UTC)) == date(2026, 11, 22)
    assert Learner(timezone="UTC").local_date(datetime(2026, 11, 21, 23, 30, tzinfo=UTC)) == date(2026, 11, 21)


def test_legacy_player_session_becomes_guest(client):
    p = Player.objects.create(chesscom_username="farel", language="fr")
    s = client.session
    s["player_id"] = p.id
    s.save()
    client.get("/games/")
    learner = Learner.objects.get()
    assert learner.player == p and learner.is_guest and learner.language == "fr"
    assert client.session["learner_id"] == learner.id and "player_id" not in client.session


def test_legacy_player_id_links_existing_guest(client, guest):
    p = Player.objects.create(chesscom_username="farel")
    s = client.session
    s["learner_id"] = guest.id
    s["player_id"] = p.id
    s.save()
    client.get("/games/")
    guest.refresh_from_db()
    assert guest.player == p and Learner.objects.count() == 1


def test_logged_in_user_gets_a_learner(client, django_user_model):
    u = django_user_model.objects.create_user("a@b.c", "a@b.c", "pw-Long-enough-1")
    client.force_login(u)
    client.get("/games/")
    assert Learner.objects.get().user == u


def test_current_player_comes_from_learner(rf_with_session, guest):
    p = Player.objects.create(chesscom_username="farel")
    guest.player = p
    guest.save()
    req = rf_with_session()
    assert current_player(req) is None
    req.learner = guest
    assert current_player(req) == p


def test_last_seen_written_once_per_day(client):
    g = Learner.objects.create(last_seen_at=timezone.now() - timedelta(days=2))
    s = client.session
    s["learner_id"] = g.id
    s.save()
    client.get("/games/")
    g.refresh_from_db()
    assert g.last_seen_at.date() == timezone.now().date()
    with CaptureQueriesContext(connection) as ctx:
        client.get("/games/")
    assert not [q for q in ctx.captured_queries if q["sql"].startswith("UPDATE") and "accounts_learner" in q["sql"]]


def test_unknown_learner_id_in_session_is_ignored(client):
    s = client.session
    s["learner_id"] = 999999
    s.save()
    assert client.get("/games/").status_code == 302
    assert Learner.objects.count() == 0


def test_delete_idle_guests(django_user_model):
    old = timezone.now() - timedelta(days=181)
    Learner.objects.create(last_seen_at=old)
    Learner.objects.create(last_seen_at=timezone.now() - timedelta(days=179))
    Learner.objects.create(user=django_user_model.objects.create_user("x", "x@x.x", "p"), last_seen_at=old)
    assert delete_idle_guests() == 1 and Learner.objects.count() == 2


def test_daily_visit_renews_the_session_cookie(client, settings):
    """Without renewal the one-year cookie expires a year after the guest arrived, even if they play every day."""
    g = Learner.objects.create(last_seen_at=timezone.now() - timedelta(days=2))
    s = client.session
    s["learner_id"] = g.id
    s.save()
    first = client.get("/start/")
    assert settings.SESSION_COOKIE_NAME in first.cookies
    assert first.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == settings.SESSION_COOKIE_AGE
    second = client.get("/start/")  # same day: nothing to renew
    assert settings.SESSION_COOKIE_NAME not in second.cookies
