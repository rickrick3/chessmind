import pytest
from django.contrib.staticfiles import finders
from django.utils import timezone

from accounts.models import Learner
from learning.models import LessonProgress

pytestmark = pytest.mark.django_db


def test_landing_for_new_visitor(client):
    r = client.get("/")
    html = r.content.decode()
    assert r.status_code == 200 and 'href="/start/"' in html and 'href="/login/"' in html
    assert Learner.objects.count() == 0


def test_landing_redirects_account(client, account):
    client.force_login(account)
    r = client.get("/")
    assert r.status_code == 302 and r.url == "/learn/"


def test_landing_redirects_guest_with_progress(guest_client, lesson_factory):
    client, guest = guest_client
    LessonProgress.objects.create(learner=guest, lesson=lesson_factory(), first_completed_at=timezone.now())
    assert client.get("/").url == "/learn/"


def test_guest_without_progress_sees_landing(guest_client):
    client, _guest = guest_client
    assert client.get("/").status_code == 200


def test_old_username_signin_is_gone(client):
    assert client.post("/", {"username": "farel"}).status_code == 405


def test_start_page_has_three_levels(client):
    html = client.get("/start/").content.decode()
    assert all(f'data-level="{level}"' in html for level in ("new", "rules", "club"))
    assert "/api/v1/me/start-level" in html and Learner.objects.count() == 0


def test_shell_nav_and_font(client):
    html = client.get("/").content.decode()
    assert all(f'href="{url}"' in html for url in ("/learn/", "/games/", "/profile/"))
    assert "css/chessmind.css" in html
    css = open(finders.find("css/chessmind.css"), encoding="utf-8").read()
    assert "@font-face" in css and "Nunito" in css and "nunito-latin-wght-normal.woff2" in css
    assert finders.find("fonts/nunito/nunito-latin-wght-normal.woff2") and finders.find("fonts/nunito/OFL.txt")


def test_landing_in_french(client):
    html = client.get("/", HTTP_ACCEPT_LANGUAGE="fr").content.decode()
    assert "Apprends les échecs, une courte leçon par jour" in html


def test_streak_in_header(guest_client):
    client, guest = guest_client
    guest.current_streak, guest.longest_streak = 3, 3
    guest.last_active_date = guest.local_date(timezone.now())
    guest.save()
    html = client.get("/start/").content.decode()
    assert 'data-streak="3"' in html


def test_no_streak_for_visitors(client):
    assert "data-streak" not in client.get("/").content.decode()


def test_existing_pages_use_the_shell(client):
    html = client.get("/login/").content.decode()
    assert "css/chessmind.css" in html and "ChessMind" in html
