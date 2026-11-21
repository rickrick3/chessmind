"""End-to-end tests: a real browser (Playwright, Chromium) against Django's live server, on a phone-sized screen."""
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "e2e_lesson.json"


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 390, "height": 844}, "locale": "en-US"}


@pytest.fixture
def e2e_lesson(transactional_db, lesson_factory, publish):
    """The only path lesson, published: explain, then find_move (e2e4), then choice (answer 1)."""
    lesson = lesson_factory("e2e-basics", order=1)
    publish(lesson, json.loads(FIXTURE.read_text(encoding="utf-8")))
    return lesson


@pytest.fixture
def page_fr(browser, live_server):
    context = browser.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR",
                                  extra_http_headers={"Accept-Language": "fr"})
    page = context.new_page()
    yield page
    context.close()
