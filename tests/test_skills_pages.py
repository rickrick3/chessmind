"""The Skills tab on the profile and the detail page of one skill area."""
import pytest
from django.conf import settings
from django.utils import timezone

from puzzles.services import finish_puzzle
from skills.models import SkillEstimate
from tests.puzzle_data import MISSED, SOLVED, serve

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def test_empty_state(guest_client):
    client, _ = guest_client
    assert "We're still learning how you play." in client.get("/profile/?tab=skills").content.decode()


def test_skills_tab_link_exists(guest_client):
    client, _ = guest_client
    assert 'href="?tab=skills"' in client.get("/profile/").content.decode()


def test_nine_areas_and_wording(guest_client, puzzle_factory):
    client, guest = guest_client
    for i in range(12):
        finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, MISSED if i % 6 else SOLVED, NOW)
    html = client.get("/profile/?tab=skills").content.decode()
    assert html.count("data-area=") == 9 and "12 puzzles" in html and "early estimate" in html
    assert "not enough evidence yet" in html
    est = SkillEstimate.objects.get(learner=guest, kind="area", key="tactics")
    assert f"about {est.low}–{est.high}" in html
    if round(est.value) % 50:  # the exact estimate never appears, only the rounded range
        assert str(round(est.value)) not in html


def test_area_detail(guest_client, puzzle_factory):
    client, guest = guest_client
    for _ in range(25):
        finish_puzzle(guest, serve(guest, puzzle_factory(themes=["fork", "short"])).pk, MISSED, NOW)
    r = client.get("/profile/skills/tactics/")
    assert r.status_code == 200 and len(r.context["detail"]["recent"]) == 20
    assert [t.key for t in r.context["detail"]["themes"]] == ["fork"]
    assert r.context["detail"]["sources"] == {"puzzle": 25, "lesson": 0}
    html = r.content.decode()
    assert "/train/puzzles/" in html and "From 25 puzzles and 0 lesson answers." in html


def test_unknown_area_404_and_no_repeated_mistake_text(guest_client, puzzle_factory):
    client, guest = guest_client
    assert client.get("/profile/skills/chess/").status_code == 404
    finish_puzzle(guest, serve(guest, puzzle_factory(themes=["pin"])).pk, MISSED, NOW)
    # how the flag is computed is tested in test_skill_evidence; here only that it is never shown
    SkillEstimate.objects.filter(learner=guest, kind="theme", key="pin").update(repeated_mistake=True)
    assert "repeated" not in client.get("/profile/skills/tactics/").content.decode().lower()


def test_area_detail_needs_a_learner(client):
    r = client.get("/profile/skills/tactics/")
    assert r.status_code == 302 and r["Location"] == "/start/"


def test_skills_tab_in_french(guest_client):
    client, guest = guest_client
    guest.language = "fr"
    guest.save()
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fr"  # what the FR/EN switch sets along with the learner
    assert "Nous apprenons encore" in client.get("/profile/?tab=skills").content.decode()
