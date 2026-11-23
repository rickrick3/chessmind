"""The lesson player in a real browser: a guest finishes a lesson, gets feedback, signs up and keeps the XP."""
import json
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


def test_rejected_result_is_not_called_saved(page: Page, live_server, e2e_lesson):
    """A 4xx from the server is final: the learner must see why, not a promise to save later."""
    message = "This lesson was started too long ago. Start it again."
    page.route("**/api/v1/attempts/*/finish", lambda route: route.fulfill(
        status=410, content_type="application/json",
        body=json.dumps({"error": {"code": "expired", "message": message}})))
    start_as_guest(page, live_server)
    continue_(page)
    play(page, "e2e4")
    continue_(page)
    page.locator('[data-option="1"]').click()
    continue_(page)
    expect(page.locator(".lp-summary")).to_contain_text(message)
    expect(page.locator(".lp-summary")).not_to_contain_text("We'll save this")
    expect(page.get_by_role("link", name="Start again")).to_be_visible()


def test_play_line_with_a_wrong_move_and_an_alternative(page: Page, live_server, e2e_line):
    page.goto(live_server.url + "/lessons/e2e-line/")
    expect(page.locator(".lp-prompt")).to_have_text("Play the Italian from memory.")
    play(page, "e2e4")                  # right; the app answers ...e5
    play(page, "d2d4")                  # wrong: the line wants Nf3
    expect(page.locator(".lp-coach")).to_contain_text("Not quite")
    play(page, "g1f3")                  # right on the second try; the app answers ...Nc6
    play(page, "f1b5")                  # an accepted alternative: the board plays the lesson's Bc4
    expect(page.locator(".lp-coach")).to_contain_text("Bc4 aims at f7")
    continue_(page)                     # one wrong move: the line comes back once
    expect(page.locator(".lp-prompt")).to_have_text("Play the Italian from memory.")
    play(page, "e2e4")
    play(page, "g1f3")
    play(page, "f1c4")
    continue_(page)
    expect(page.get_by_text("+10 XP")).to_be_visible()                # completed, but 2 of 3 moves right first time
    expect(page.locator(".lp-summary")).to_contain_text("67%")


def test_header_touch_targets_are_at_least_44px(page: Page, live_server):
    page.goto(live_server.url + "/")
    for target in (page.get_by_role("button", name="FR"), page.get_by_role("button", name="EN"),
                   page.locator(".cm-topbar").get_by_role("link", name="Log in")):
        box = target.bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44, box
