import pytest
import responses
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Learner
from accounts.services import link_chesscom
from games.models import Game
from players.models import Player

pytestmark = pytest.mark.django_db
PW = "Chess-is-fun-42"
API = "https://api.chess.com/pub/player"


@responses.activate
def test_link_unknown_username_shows_error(client):
    responses.get(f"{API}/nobody_xyz", status=404)
    r = client.post("/profile/chess-com/", {"username": "nobody_xyz"})
    assert r.status_code == 200 and "nobody_xyz" in r.content.decode()
    assert Player.objects.count() == 0


@responses.activate
def test_link_is_case_insensitive(client):
    responses.get(f"{API}/farel", json={"username": "farel"})
    client.post("/profile/chess-com/", {"username": "Farel"})
    r = client.post("/profile/chess-com/", {"username": "farel"})
    assert r.status_code == 302 and r.url == "/games/"
    assert Player.objects.get().chesscom_username == "farel"
    assert Learner.objects.get().player.chesscom_username == "farel"


@responses.activate
def test_link_when_chesscom_down(client):
    responses.get(f"{API}/farel", status=503)
    r = client.post("/profile/chess-com/", {"username": "farel"})
    assert r.status_code == 200 and "Chess.com" in r.content.decode() and Player.objects.count() == 0


@responses.activate
def test_two_learners_can_link_same_username():
    responses.get(f"{API}/farel", json={"username": "farel"})
    a, b = Learner.objects.create(), Learner.objects.create()
    assert link_chesscom(a, "farel") == link_chesscom(b, " FAREL ")
    assert Player.objects.count() == 1


def test_unlink(guest_client):
    client, guest = guest_client
    guest.player = Player.objects.create(chesscom_username="farel")
    guest.save()
    client.post("/profile/chess-com/unlink/")
    guest.refresh_from_db()
    assert guest.player is None and Player.objects.count() == 1


def test_settings_save(guest_client):
    client, guest = guest_client
    r = client.post("/profile/settings/", {"display_name": "Farel", "language": "fr", "daily_goal_xp": "30",
                                            "timezone": "Europe/Paris"})
    guest.refresh_from_db()
    assert r.status_code == 302
    assert (guest.display_name, guest.language, guest.daily_goal_xp, guest.timezone) == \
        ("Farel", "fr", 30, "Europe/Paris")
    assert client.cookies["django_language"].value == "fr"


@pytest.mark.parametrize("field,value", [("daily_goal_xp", "15"), ("timezone", "Mars/Base"), ("language", "de")])
def test_settings_reject_bad_values(guest_client, field, value):
    client, guest = guest_client
    data = {"display_name": "", "language": "en", "daily_goal_xp": "20", "timezone": "UTC", field: value}
    r = client.post("/profile/settings/", data)
    guest.refresh_from_db()
    assert r.status_code == 200
    assert (guest.language, guest.daily_goal_xp, guest.timezone) == ("en", 20, "UTC")


def test_settings_page_creates_guest_for_new_visitor(client):
    assert client.get("/profile/settings/").status_code == 200
    assert Learner.objects.count() == 1


def test_delete_account_needs_password(client, account):
    client.force_login(account)
    client.post("/profile/delete/", {"password": "wrong"})
    assert get_user_model().objects.count() == 1 and Learner.objects.count() == 1
    r = client.post("/profile/delete/", {"password": PW})
    assert r.status_code == 302 and r.url == "/"
    assert get_user_model().objects.count() == 0 and Learner.objects.count() == 0
    assert "_auth_user_id" not in client.session


def test_delete_keeps_shared_games(client, account):
    player = Player.objects.create(chesscom_username="farel")
    account.learner.player = player
    account.learner.save()
    Game.objects.create(chesscom_url="https://www.chess.com/game/live/1", pgn="1. e4 e5 1-0", white="farel",
                        black="opp", result="1-0", played_at=timezone.now())
    client.force_login(account)
    client.post("/profile/delete/", {"password": PW})
    assert Player.objects.count() == 1 and Game.objects.count() == 1


def test_guest_deletes_without_password(guest_client):
    client, guest = guest_client
    r = client.post("/profile/delete/", {})
    assert r.status_code == 302 and not Learner.objects.filter(id=guest.id).exists()


def test_password_change_needs_old_password(client, account):
    client.force_login(account)
    new = "Another-long-pass-77"
    client.post("/profile/password/", {"old_password": "wrong", "new_password1": new, "new_password2": new})
    account.refresh_from_db()
    assert account.check_password(PW)
    r = client.post("/profile/password/", {"old_password": PW, "new_password1": new, "new_password2": new})
    account.refresh_from_db()
    assert r.status_code == 302 and r.url == "/profile/settings/" and account.check_password(new)


def test_password_change_requires_account(guest_client):
    client, _guest = guest_client
    r = client.get("/profile/password/")
    assert r.status_code == 302 and r.url.startswith("/login/")


def test_game_list_without_link_redirects_to_link_page(guest_client):
    client, _guest = guest_client
    r = client.get("/games/")
    assert r.status_code == 302 and r.url == "/profile/chess-com/"
