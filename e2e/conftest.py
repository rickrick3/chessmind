"""End-to-end tests: a real browser (Playwright, Chromium) against Django's live server, on a phone-sized screen."""
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "e2e_lesson.json"
LINE = Path(__file__).parent / "fixtures" / "e2e_line.json"


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


@pytest.fixture
def e2e_line(transactional_db, lesson_factory, publish):
    """A play_line lesson in an openings course, so it is open without unlocking: the Italian, White to play."""
    lesson = lesson_factory("e2e-line", course="openings", unit="italian", track="openings", kind="opening")
    publish(lesson, json.loads(LINE.read_text(encoding="utf-8")))
    return lesson


@pytest.fixture
def mate2_puzzle(transactional_db, puzzle_factory):
    """The only active puzzle: MATE2 (1...Kd7 2.Be6+ Kd8 3.Qf8#), White to play."""
    from tests.puzzle_data import MATE2

    return puzzle_factory(data=MATE2, rating=1000)


@pytest.fixture
def alt_mate_puzzle(transactional_db, puzzle_factory):
    from tests.puzzle_data import ALT_MATE

    return puzzle_factory(data=ALT_MATE, rating=1000)


@pytest.fixture
def promotion_puzzle(transactional_db, puzzle_factory):
    from tests.puzzle_data import PROMOTION

    return puzzle_factory(data=PROMOTION, rating=1000)
