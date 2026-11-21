import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import Learner
from curriculum.services import new_version
from gamification.models import XpEvent
from learning.models import LessonAttempt, StepResult

from .test_finish import perfect_steps

pytestmark = pytest.mark.django_db
J = "application/json"


@pytest.fixture
def path2(lesson_factory, publish, valid_content):
    lessons = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2)]
    for lesson in lessons:
        publish(lesson, valid_content)
    return lessons


def start(client, slug="lesson-1"):
    r = client.post(f"/api/v1/lessons/{slug}/attempts", {"timezone": "Europe/Paris"}, content_type=J)
    assert r.status_code == 201, r.content
    return r.json()["attempt_id"]


def finish(client, attempt_id, body):
    data = body if isinstance(body, str) else json.dumps(body)
    return client.post(f"/api/v1/attempts/{attempt_id}/finish", data, content_type=J)


def test_me_before_any_action(client):
    assert client.get("/api/v1/me").json() == {"learner": None}
    assert Learner.objects.count() == 0


def test_start_level_creates_guest_and_returns_first_lesson(client, path2):
    r = client.post("/api/v1/me/start-level", {"level": "new", "timezone": "Europe/Paris"}, content_type=J)
    assert r.status_code == 200 and r.json() == {"next_lesson": "lesson-1"}
    learner = Learner.objects.get()
    assert (learner.timezone, learner.start_level, learner.is_guest) == ("Europe/Paris", "new", True)
    me = client.get("/api/v1/me").json()["learner"]
    assert me["is_guest"] is True and me["xp_total"] == 0 and me["streak"]["current"] == 0
    assert me["daily_goal"] == {"target": 20, "today_xp": 0} and me["start_level"] == "new"


def test_start_level_rejects_unknown(client, path2):
    r = client.post("/api/v1/me/start-level", {"level": "grandmaster"}, content_type=J)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"


def test_settings_endpoint(guest_client):
    client, guest = guest_client
    r = client.post("/api/v1/me/settings", {"daily_goal_xp": 30, "timezone": "America/Montreal"}, content_type=J)
    assert r.status_code == 200 and r.json()["learner"]["daily_goal"]["target"] == 30
    assert client.post("/api/v1/me/settings", {"daily_goal_xp": 15}, content_type=J).status_code == 400
    guest.refresh_from_db()
    assert (guest.daily_goal_xp, guest.timezone) == (30, "America/Montreal")


def test_lesson_json_in_french(client, path2):
    d = client.get("/api/v1/lessons/lesson-1", HTTP_ACCEPT_LANGUAGE="fr").json()
    s3 = next(s for s in d["steps"] if s["id"] == "s3")
    assert d["lesson"]["title"] == "Les premiers coups" and s3["correct"] == "Cc6 défend e5 et sort un cavalier."
    assert s3["accept"] == ["b8c6"] and d["version_id"] == path2[0].versions.get().id
    assert d["completion"] == {"min_accuracy": 0} and d["lesson"]["orientation"] == "white"


def test_lesson_json_follows_learner_language(guest_client, path2):
    client, guest = guest_client
    guest.language = "fr"
    guest.save()
    d = client.get("/api/v1/lessons/lesson-1", HTTP_ACCEPT_LANGUAGE="en").json()
    assert d["lesson"]["title"] == "Les premiers coups"


def test_locked_and_unpublished(client, path2, lesson_factory):
    lesson_factory("draft-only", order=9)
    r = client.get("/api/v1/lessons/lesson-2")
    assert r.status_code == 403 and r.json()["error"]["code"] == "locked"
    assert client.get("/api/v1/lessons/nope").status_code == 404
    assert client.get("/api/v1/lessons/draft-only").json()["error"]["code"] == "not_found"
    assert client.post("/api/v1/lessons/lesson-2/attempts", {}, content_type=J).status_code == 403


def test_attempt_and_finish_over_http(client, path2):
    attempt_id = start(client)
    r = finish(client, attempt_id, {"steps": perfect_steps()})
    assert r.status_code == 200 and r.json()["xp"]["awarded"] == 15 and r.json()["unlocked"] == ["lesson-2"]
    assert finish(client, attempt_id, {"steps": perfect_steps()}).json() == r.json()
    assert client.get("/api/v1/lessons/lesson-2").status_code == 200


def test_hostile_finish_writes_nothing(client, path2):
    attempt_id = start(client)
    illegal = {"steps": [{"id": "s3", "tries": ["e2e5"], "hints": 0, "ms": 1}]}
    for body in (illegal, '{"steps": 5}', "not json", "[1, 2]", json.dumps({"steps": perfect_steps(), "x": "y" * 70_000})):
        r = finish(client, attempt_id, body)
        assert r.status_code == 400 and r.json()["error"]["code"] in ("invalid_result", "bad_request")
    assert not StepResult.objects.exists() and not XpEvent.objects.exists()
    assert LessonAttempt.objects.get().finished_at is None


def test_other_learners_attempt_is_404(client, path2):
    attempt_id = start(client)
    other = Client()
    other.post("/api/v1/me/start-level", {"level": "new"}, content_type=J)
    assert finish(other, attempt_id, {"steps": perfect_steps()}).status_code == 404
    assert finish(Client(), attempt_id, {"steps": perfect_steps()}).status_code == 404


def test_expired_is_410(client, path2):
    attempt_id = start(client)
    LessonAttempt.objects.filter(pk=attempt_id).update(started_at=timezone.now() - timedelta(hours=25))
    r = finish(client, attempt_id, {"steps": perfect_steps()})
    assert r.status_code == 410 and r.json()["error"]["code"] == "expired"


def test_csrf_enforced(path2):
    c = Client(enforce_csrf_checks=True)
    assert c.post("/api/v1/me/start-level", {"level": "new"}, content_type=J).status_code == 403


def test_staff_preview(client, staff, path2):
    draft = new_version(path2[1], staff, content={"schema": 1, "meta": {}, "steps": []})
    assert client.get(f"/api/v1/lessons/lesson-1?version={draft.pk}").json()["version_id"] == \
        path2[0].versions.get().id
    client.force_login(staff)
    d = client.get(f"/api/v1/lessons/lesson-2?version={draft.pk}").json()
    assert d["version_id"] == draft.pk and d["steps"] == []
