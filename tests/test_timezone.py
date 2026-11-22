"""A learner's streak days follow the time zone their browser reports, even when the learner was created without one."""
import pytest

from accounts.models import Learner
from players.models import Player

pytestmark = pytest.mark.django_db
J = "application/json"
PW = "Chess-is-fun-42"


@pytest.fixture
def first_lesson(lesson_factory, publish, valid_content):
    lesson = lesson_factory("lesson-1", order=1)
    publish(lesson, valid_content)
    return lesson


def start(client, tz):
    r = client.post("/api/v1/lessons/lesson-1/attempts", {"timezone": tz}, content_type=J)
    assert r.status_code == 201
    return r


def test_legacy_session_learner_adopts_browser_timezone(client, first_lesson):
    player = Player.objects.create(chesscom_username="farel")
    s = client.session
    s["player_id"] = player.id
    s.save()
    start(client, "America/Montreal")
    learner = Learner.objects.get()
    assert (learner.timezone, learner.timezone_confirmed) == ("America/Montreal", True)


def test_learner_created_on_a_settings_page_adopts_browser_timezone(client, first_lesson):
    client.get("/profile/chess-com/")  # creates a guest before any lesson
    assert Learner.objects.get().timezone == "UTC"
    start(client, "Europe/Paris")
    assert Learner.objects.get().timezone == "Europe/Paris"


def test_chosen_timezone_is_not_overwritten_by_the_browser(guest_client, first_lesson):
    client, guest = guest_client
    client.post("/profile/settings/", {"display_name": "", "language": "en", "daily_goal_xp": "20",
                                       "timezone": "Asia/Tokyo"})
    start(client, "Europe/Paris")
    guest.refresh_from_db()
    assert (guest.timezone, guest.timezone_confirmed) == ("Asia/Tokyo", True)


def test_invalid_browser_timezone_is_ignored(client, first_lesson):
    start(client, "Mars/Base")
    assert (Learner.objects.get().timezone, Learner.objects.get().timezone_confirmed) == ("UTC", False)


def test_account_takes_the_guest_timezone_on_login(guest_client, account):
    client, guest = guest_client
    guest.timezone, guest.timezone_confirmed = "Europe/Paris", True
    guest.save()
    client.post("/login/", {"email": "farel@example.com", "password": PW})
    account.learner.refresh_from_db()
    assert (account.learner.timezone, account.learner.timezone_confirmed) == ("Europe/Paris", True)


def test_account_keeps_its_own_confirmed_timezone_on_login(guest_client, account):
    client, guest = guest_client
    guest.timezone, guest.timezone_confirmed = "Europe/Paris", True
    guest.save()
    Learner.objects.filter(user=account).update(timezone="Asia/Tokyo", timezone_confirmed=True)
    client.post("/login/", {"email": "farel@example.com", "password": PW})
    account.learner.refresh_from_db()
    assert account.learner.timezone == "Asia/Tokyo"
