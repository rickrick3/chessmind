import json

import pytest
from django.core.management import call_command

from curriculum.domain.workflow import APPROVED, DRAFT, PENDING_REVIEW, PUBLISHED, VALIDATING
from curriculum.models import Course, Lesson, LessonVersion
from curriculum.services import new_version

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client(client, staff):
    client.force_login(staff)
    return client


@pytest.fixture
def draft_version(lesson_factory, staff):
    return new_version(lesson_factory("italian"), staff, content={"schema": 1, "steps": []})


def at(version, status):
    LessonVersion.objects.filter(pk=version.pk).update(status=status)
    version.refresh_from_db()
    return version


def test_studio_access(client, account, staff):
    r = client.get("/studio/")
    assert r.status_code == 302 and r.url == "/login/?next=/studio/"
    client.force_login(account)
    assert client.get("/studio/").status_code == 403
    client.force_login(staff)
    assert client.get("/studio/").status_code == 200


def test_lesson_list_shows_versions(staff_client, draft_version):
    html = staff_client.get("/studio/").content.decode()
    assert "italian" in html and f"/studio/versions/{draft_version.pk}/" in html and "draft" in html


def test_version_page(staff_client, draft_version):
    html = staff_client.get(f"/studio/versions/{draft_version.pk}/").content.decode()
    assert "<textarea" in html and f"/lessons/italian/?version={draft_version.pk}" in html
    assert 'value="validating"' in html


def test_invalid_json_not_saved(staff_client, draft_version):
    r = staff_client.post(f"/studio/versions/{draft_version.pk}/content", {"content": "{bad"}, follow=True)
    draft_version.refresh_from_db()
    assert "Not valid JSON" in r.content.decode()
    assert draft_version.content == {"schema": 1, "steps": []} and not draft_version.events.filter(kind="edit")


def test_save_content(staff_client, draft_version):
    staff_client.post(f"/studio/versions/{draft_version.pk}/content", {"content": '{"schema": 1, "steps": [1]}'})
    draft_version.refresh_from_db()
    assert draft_version.content == {"schema": 1, "steps": [1]}


def test_reject_without_note_is_refused(staff_client, draft_version):
    v = at(draft_version, PENDING_REVIEW)
    r = staff_client.post(f"/studio/versions/{v.pk}/transition", {"to": "rejected", "note": ""}, follow=True)
    v.refresh_from_db()
    assert v.status == PENDING_REVIEW and "note" in r.content.decode().lower()


def test_validate_button_runs_checks(staff_client, draft_version, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        staff_client.post(f"/studio/versions/{draft_version.pk}/transition", {"to": VALIDATING})
    draft_version.refresh_from_db()
    assert draft_version.status == DRAFT and draft_version.validation_report["issues"]


def test_approve_then_publish(staff_client, draft_version, staff):
    v = at(draft_version, PENDING_REVIEW)
    staff_client.post(f"/studio/versions/{v.pk}/transition", {"to": APPROVED})
    staff_client.post(f"/studio/versions/{v.pk}/transition", {"to": PUBLISHED})
    v.refresh_from_db()
    assert v.status == PUBLISHED and v.lesson.published_version == v and v.reviewed_by == staff


def test_illegal_transition_shows_message(staff_client, draft_version):
    r = staff_client.post(f"/studio/versions/{draft_version.pk}/transition", {"to": PUBLISHED}, follow=True)
    draft_version.refresh_from_db()
    assert draft_version.status == DRAFT and r.status_code == 200


def test_new_version_copies_latest(staff_client, draft_version):
    r = staff_client.post("/studio/lessons/italian/versions/new")
    v2 = LessonVersion.objects.get(lesson__slug="italian", number=2)
    assert r.status_code == 302 and r.url == f"/studio/versions/{v2.pk}/" and v2.content == draft_version.content


def _write(tmp_path, content):
    data = {"courses": [{"slug": "c", "track": "path", "order": 1, "title": {"fr": "C", "en": "C"},
                         "units": [{"slug": "u", "order": 1, "title": {"fr": "U", "en": "U"},
                                    "lessons": [{"slug": "l1", "order": 1, "kind": "concept", "difficulty": 1,
                                                 "content": content}]}]}]}
    path = tmp_path / "lessons.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_import_is_idempotent(tmp_path, capsys):
    path = _write(tmp_path, {"schema": 1, "steps": [1]})
    call_command("import_lessons", path)
    call_command("import_lessons", path)
    out = capsys.readouterr().out
    assert "lessons: 1 created, 0 updated; drafts: 1" in out and "lessons: 0 created, 1 updated; drafts: 0" in out
    assert Course.objects.count() == 1 and Lesson.objects.count() == 1 and LessonVersion.objects.count() == 1


def test_import_new_content_makes_new_draft(tmp_path):
    call_command("import_lessons", _write(tmp_path, {"schema": 1, "steps": [1]}))
    call_command("import_lessons", _write(tmp_path, {"schema": 1, "steps": [2]}))
    assert list(LessonVersion.objects.order_by("number").values_list("number", "content")) == [
        (1, {"schema": 1, "steps": [1]}), (2, {"schema": 1, "steps": [2]})]
