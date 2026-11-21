import pytest
from django.contrib.auth import get_user_model

from accounts.models import Learner
from accounts.signals import merge_learners

pytestmark = pytest.mark.django_db
User = get_user_model()
PW = "Chess-is-fun-42"


def test_signup_turns_guest_into_account(guest_client):
    client, guest = guest_client
    r = client.post("/signup/", {"email": "Farel@Example.com", "password": PW, "display_name": "Farel",
                                 "timezone": "Europe/Paris"})
    guest.refresh_from_db()
    assert r.status_code == 302 and r.url == "/learn/"
    assert guest.user.username == "farel@example.com" and guest.user.email == "farel@example.com"
    assert guest.display_name == "Farel" and guest.timezone == "Europe/Paris"
    assert Learner.objects.count() == 1 and int(client.session["_auth_user_id"]) == guest.user.id


def test_signup_without_guest_creates_learner(client):
    client.post("/signup/", {"email": "new@example.com", "password": PW})
    learner = Learner.objects.get()
    assert learner.user.email == "new@example.com" and not learner.is_guest


def test_signup_email_is_case_insensitive_unique(client, account):
    r = client.post("/signup/", {"email": "FAREL@example.com", "password": PW})
    assert r.status_code == 200 and "already has an account" in r.content.decode()
    assert User.objects.count() == 1


def test_signup_rejects_weak_password(client):
    r = client.post("/signup/", {"email": "a@b.co", "password": "123"})
    assert r.status_code == 200 and User.objects.count() == 0


def test_login_merges_guest_and_sends_signal(guest_client, account):
    client, guest = guest_client
    seen = []

    def receiver(sender, source, target, **kw):
        seen.append((source.id, target.id))

    merge_learners.connect(receiver, weak=False, dispatch_uid="test-merge")
    try:
        r = client.post("/login/", {"email": "Farel@example.com", "password": PW})
    finally:
        merge_learners.disconnect(dispatch_uid="test-merge")
    assert r.status_code == 302 and r.url == "/learn/"
    assert seen == [(guest.id, account.learner.id)]
    assert not Learner.objects.filter(id=guest.id).exists() and "learner_id" not in client.session


def test_login_without_guest_sends_no_signal(client, account):
    seen = []
    merge_learners.connect(lambda **kw: seen.append(kw), weak=False, dispatch_uid="test-merge-2")
    try:
        client.post("/login/", {"email": "farel@example.com", "password": PW})
    finally:
        merge_learners.disconnect(dispatch_uid="test-merge-2")
    assert seen == [] and "_auth_user_id" in client.session


def test_login_with_wrong_password(client, account):
    r = client.post("/login/", {"email": "farel@example.com", "password": "wrong"})
    assert r.status_code == 200 and "_auth_user_id" not in client.session


def test_login_throttled_after_five_failures(client, account):
    for _ in range(5):
        client.post("/login/", {"email": "farel@example.com", "password": "wrong"})
    r = client.post("/login/", {"email": "farel@example.com", "password": PW})
    assert "Too many attempts" in r.content.decode() and "_auth_user_id" not in client.session


def test_success_clears_failures(client, account):
    for _ in range(4):
        client.post("/login/", {"email": "farel@example.com", "password": "wrong"})
    client.post("/login/", {"email": "farel@example.com", "password": PW})
    client.post("/logout/")
    for _ in range(4):
        client.post("/login/", {"email": "farel@example.com", "password": "wrong"})
    client.post("/login/", {"email": "farel@example.com", "password": PW})
    assert "_auth_user_id" in client.session


def test_logout_is_post_only(client, account):
    client.force_login(account)
    assert client.get("/logout/").status_code == 405
    r = client.post("/logout/")
    assert r.status_code == 302 and r.url == "/" and "_auth_user_id" not in client.session


def test_password_reset_sends_email(client, account, mailoutbox):
    r = client.post("/password-reset/", {"email": "FAREL@example.com"})
    assert r.status_code == 302 and r.url == "/password-reset/sent/"
    assert len(mailoutbox) == 1 and "/password-reset/" in mailoutbox[0].body
    assert mailoutbox[0].to == ["farel@example.com"]


def test_next_must_be_safe(client, account):
    r = client.post("/login/?next=https://evil.example/", {"email": "farel@example.com", "password": PW})
    assert r.url == "/learn/"
    client.post("/logout/")
    r = client.post("/login/?next=/profile/", {"email": "farel@example.com", "password": PW})
    assert r.url == "/profile/"


def test_login_page_in_french(client):
    r = client.get("/login/", HTTP_ACCEPT_LANGUAGE="fr")
    assert "Se connecter" in r.content.decode()
