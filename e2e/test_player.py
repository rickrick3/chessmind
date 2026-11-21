"""The lesson player in a real browser: a guest finishes a lesson, gets feedback, signs up and keeps the XP."""
import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.django_db(transaction=True)


def square(page: Page, name: str):
    return page.locator(f'#board [data-square="{name}"]').first


def play(page: Page, uci: str):
    expect(page.locator("#board")).to_have_attribute("data-input", "on")  # wait until the board takes a move
    square(page, uci[:2]).click()
    square(page, uci[2:4]).click()


def continue_(page: Page):
    page.get_by_role("button", name="Continue").click()


def start_as_guest(page: Page, live_server):
    page.goto(live_server.url + "/")
    page.get_by_role("link", name="Start").click()
    page.locator('[data-level="new"]').click()
    expect(page).to_have_url(re.compile(r"/lessons/e2e-basics/$"))


def test_guest_finishes_lesson_and_keeps_xp_after_signup(page: Page, live_server, e2e_lesson):
    start_as_guest(page, live_server)
    expect(page.locator(".lp-coach")).to_contain_text("Soon you will play Nf3")
    continue_(page)
    play(page, "e2e4")
    expect(page.locator(".lp-feedback")).to_contain_text("e4 takes the centre")
    continue_(page)
    page.locator('[data-option="1"]').click()
    continue_(page)
    expect(page.get_by_text("+15 XP")).to_be_visible()
    expect(page.locator(".lp-summary")).to_contain_text("100%")
    page.get_by_role("link", name="Create an account").click()
    page.fill('[name="email"]', "new@example.com")
    page.fill('[name="password"]', "Chess-is-fun-42")
    page.get_by_role("button", name="Create account").click()
    expect(page).to_have_url(re.compile(r"/profile/$"))
    expect(page.locator(".cm-profile__level")).to_contain_text("15 XP")
    expect(page.locator('[data-stat="streak"]')).to_have_text("1")


def test_wrong_move_feedback_and_step_returns(page: Page, live_server, e2e_lesson):
    start_as_guest(page, live_server)
    continue_(page)
    play(page, "e2e3")
    expect(page.locator(".lp-feedback")).to_contain_text("Too timid")
    continue_(page)
    play(page, "e2e4")
    continue_(page)
    page.locator('[data-option="1"]').click()
    continue_(page)
    expect(page.locator(".lp-prompt")).to_have_text("Push the king's pawn two squares.")  # the step comes back
    play(page, "e2e4")
    continue_(page)
    expect(page.get_by_text("+10 XP")).to_be_visible()
    expect(page.locator(".lp-summary")).to_contain_text("50%")


def test_also_good_move_counts_and_lesson_line_continues(page: Page, live_server, e2e_lesson):
    start_as_guest(page, live_server)
    continue_(page)
    play(page, "g1f3")
    expect(page.locator(".lp-feedback")).to_contain_text("Nf3 is good too")
    continue_(page)
    page.locator('[data-option="1"]').click()
    continue_(page)
    expect(page.get_by_text("+15 XP")).to_be_visible()


def test_french_player_sees_french_notation(page_fr: Page, live_server, e2e_lesson):
    page_fr.goto(live_server.url + "/lessons/e2e-basics/")
    expect(page_fr.locator(".lp-coach")).to_contain_text("Bientôt tu joueras Cf3")
    expect(page_fr.get_by_role("button", name="Continuer")).to_be_visible()
