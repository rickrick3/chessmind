from datetime import timedelta

import pytest
from django.utils import timezone

from learning.models import LessonProgress

pytestmark = pytest.mark.django_db


@pytest.fixture
def path3(lesson_factory, publish, valid_content):
    lessons = [lesson_factory(f"lesson-{n}", order=n) for n in (1, 2, 3)]
    for lesson in lessons:
        publish(lesson, valid_content)
    return lessons


@pytest.fixture
def first_done(guest_client, path3):
    client, guest = guest_client
    LessonProgress.objects.create(learner=guest, lesson=path3[0], first_completed_at=timezone.now(),
                                  best_accuracy=0.8, completions=1)
    guest.xp_total, guest.current_streak, guest.longest_streak = 15, 1, 4
    guest.last_active_date = guest.local_date(timezone.now())
    guest.save()
    return client, guest


def test_path_without_learner_redirects(client):
    r = client.get("/learn/")
    assert r.status_code == 302 and r.url == "/start/"


def test_path_node_states(first_done):
    client, _ = first_done
    html = client.get("/learn/").content.decode()
    assert 'class="node is-done"' in html and 'class="node is-current"' in html and 'class="node is-locked"' in html
    assert "1 / 3" in html and 'href="/lessons/lesson-2/"' in html and 'href="/lessons/lesson-3/"' not in html
    assert "The first moves" in html


def test_path_titles_in_french(first_done):
    client, guest = first_done
    guest.language = "fr"
    guest.save()
    assert "Les premiers coups" in client.get("/learn/").content.decode()


def test_streak_card_shows_zero_after_missed_day(first_done):
    client, guest = first_done
    guest.last_active_date = guest.local_date(timezone.now()) - timedelta(days=2)
    guest.save()
    html = client.get("/learn/").content.decode()
    assert 'data-streak-card="0"' in html


def test_daily_goal_ring(first_done):
    client, _ = first_done
    assert 'data-goal="0/20"' in client.get("/learn/").content.decode()


def test_profile_without_learner_redirects(client):
    assert client.get("/profile/").url == "/start/"


def test_profile_guest_panel(first_done):
    client, _ = first_done
    html = client.get("/profile/").content.decode()
    assert "/signup/?next=/profile/" in html and "/login/?next=/profile/" in html


def test_profile_account_has_no_guest_panel(client, account):
    client.force_login(account)
    html = client.get("/profile/").content.decode()
    assert "/signup/?next=/profile/" not in html and "Farel" in html


def test_profile_performance_numbers(first_done):
    client, _ = first_done
    html = client.get("/profile/").content.decode()
    assert "15 XP" in html and 'data-stat="lessons">1<' in html and 'data-stat="level">1<' in html
    assert 'data-stat="streak">1<' in html and 'data-stat="record">4<' in html and "80%" in html


def test_profile_mastery_unit_progress(first_done):
    client, _ = first_done
    html = client.get("/profile/?tab=mastery").content.decode()
    assert "1 / 3" in html and 'class="is-active" href="?tab=mastery"' in html


def test_profile_settings_links(client, account):
    client.force_login(account)
    html = client.get("/profile/?tab=settings").content.decode()
    assert all(u in html for u in ("/profile/settings/", "/profile/chess-com/", "/profile/password/",
                                   "/profile/delete/"))


def test_profile_rows(first_done):
    client, _ = first_done
    html = client.get("/profile/").content.decode()
    assert all(f'href="{u}"' in html for u in ("/start/", "/profile/chess-com/", "/games/"))
