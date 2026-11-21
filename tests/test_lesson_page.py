import json
import re

import pytest

from curriculum.domain.workflow import PENDING_REVIEW
from curriculum.models import LessonVersion
from curriculum.services import new_version

pytestmark = pytest.mark.django_db


def config_of(response) -> dict:
    match = re.search(r'<script id="player-config" type="application/json">(.*?)</script>',
                      response.content.decode(), re.S)
    assert match, "no player config"
    return json.loads(match.group(1))


@pytest.fixture
def path2(lesson_factory, publish, valid_content):
    lessons = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2)]
    for lesson in lessons:
        publish(lesson, valid_content)
    return lessons


def test_lesson_page_config(client, path2):
    r = client.get("/lessons/lesson-1/")
    cfg = config_of(r)
    assert r.status_code == 200 and cfg["preview"] is False and cfg["versionId"] is None
    assert cfg["lessonUrl"] == "/api/v1/lessons/lesson-1" and cfg["attemptsUrl"] == "/api/v1/lessons/lesson-1/attempts"
    assert cfg["finishUrl"] == "/api/v1/attempts/{id}/finish" and cfg["pathUrl"] == "/learn/"
    assert cfg["signupUrl"] == "/signup/?next=/profile/" and cfg["isGuest"] is True and cfg["csrfToken"]
    assert cfg["assets"].endswith("vendor/cm-chessboard/assets/") and cfg["i18n"]["continue"] == "Continue"
    assert "js/player/main.js" in r.content.decode()


def test_lesson_page_in_french(client, path2):
    cfg = config_of(client.get("/lessons/lesson-1/", HTTP_ACCEPT_LANGUAGE="fr"))
    assert cfg["lang"] == "fr" and cfg["i18n"]["continue"] == "Continuer"


def test_locked_lesson_redirects(client, path2):
    r = client.get("/lessons/lesson-2/")
    assert r.status_code == 302 and r.url == "/learn/"


def test_unknown_or_unpublished_is_404(client, path2, lesson_factory):
    lesson_factory("draft-only")
    assert client.get("/lessons/nope/").status_code == 404
    assert client.get("/lessons/draft-only/").status_code == 404


def test_staff_preview(client, staff, path2):
    draft = new_version(path2[1], staff, content={"schema": 1, "meta": {}, "steps": []})
    LessonVersion.objects.filter(pk=draft.pk).update(status=PENDING_REVIEW)
    client.force_login(staff)
    cfg = config_of(client.get(f"/lessons/lesson-2/?version={draft.pk}"))
    assert cfg["preview"] is True and cfg["versionId"] == draft.pk
    assert cfg["lessonUrl"] == f"/api/v1/lessons/lesson-2?version={draft.pk}"


def test_preview_param_ignored_for_learners(client, path2, staff):
    draft = new_version(path2[0], staff, content={"schema": 1, "meta": {}, "steps": []})
    cfg = config_of(client.get(f"/lessons/lesson-1/?version={draft.pk}"))
    assert cfg["preview"] is False and cfg["lessonUrl"] == "/api/v1/lessons/lesson-1"
