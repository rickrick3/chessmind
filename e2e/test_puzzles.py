"""The puzzle board in a real browser on a phone-sized screen: solve, miss, promote, alternative mate."""
import pytest
from playwright.sync_api import Page, expect

from tests.puzzle_data import ALT_MATE, MATE2

pytestmark = pytest.mark.django_db(transaction=True)


def square(page: Page, name: str):
    return page.locator(f'#board [data-square="{name}"]').first


def play(page: Page, uci: str):
    expect(page.locator("#board")).to_have_attribute("data-input", "on")  # wait until the board takes a move
    square(page, uci[:2]).click()
    square(page, uci[2:4]).click()


def start(page: Page, live_server):
    page.goto(live_server.url + "/train/puzzles/")
    page.get_by_role("button", name="Start puzzles").click()


def test_guest_solves_a_puzzle(page: Page, live_server, mate2_puzzle):
    start(page, live_server)
    expect(page.locator(".pz-prompt")).to_have_text("White to play — find the best move.")
    play(page, "a2e6")
    play(page, "f7f8")
    expect(page.get_by_text("Solved!")).to_be_visible()
    expect(page.get_by_text("+3 XP")).to_be_visible()
    expect(page.locator(".pz-result__change")).to_contain_text("+")


def test_skills_tab_after_a_puzzle(page: Page, live_server, mate2_puzzle):
    start(page, live_server)
    play(page, "a2e6")
    play(page, "f7f8")
    expect(page.get_by_text("Solved!")).to_be_visible()
    page.goto(live_server.url + "/profile/?tab=skills")
    expect(page.get_by_text("not enough evidence yet").first).to_be_visible(timeout=2000)


def test_wrong_move_counts_as_missed(page: Page, live_server, mate2_puzzle):
    start(page, live_server)
    play(page, MATE2["wrong_first"])
    expect(page.get_by_text("this puzzle counts as missed")).to_be_visible()
    page.get_by_role("button", name="Show solution").click()
    expect(page.get_by_text("Missed", exact=True)).to_be_visible()
    expect(page.locator(".pz-result__change")).to_contain_text("-")


def test_promotion_puzzle(page: Page, live_server, promotion_puzzle):
    start(page, live_server)
    play(page, "g7g8")
    page.locator('#board [data-piece="wq"]').first.click()
    expect(page.get_by_text("Solved!")).to_be_visible()


def test_alternative_mate(page: Page, live_server, alt_mate_puzzle):
    start(page, live_server)
    play(page, ALT_MATE["alternative"])
    expect(page.get_by_text("Solved!")).to_be_visible()


def test_no_puzzle_left_returns_to_the_start_panel(page: Page, live_server, mate2_puzzle):  # Review Focus 1
    start(page, live_server)
    play(page, "a2e6")
    play(page, "f7f8")
    expect(page.get_by_text("Solved!")).to_be_visible()
    page.get_by_role("button", name="Next puzzle").click()
    expect(page.get_by_text("You've seen every puzzle here")).to_be_visible()
    expect(page.get_by_role("button", name="Start puzzles")).to_be_visible()
    expect(page.get_by_role("link", name="Fork")).to_be_visible()


def test_outcome_is_kept_when_the_connection_drops(page: Page, live_server, mate2_puzzle):
    from puzzles.models import PuzzleAttempt

    page.route("**/finish", lambda route: route.abort())
    start(page, live_server)
    play(page, MATE2["wrong_first"])
    expect(page.get_by_text("this puzzle counts as missed")).to_be_visible()
    page.reload()  # the tab is closed while the miss is being sent: every send so far was cut
    page.unroute("**/finish")
    with page.expect_response(lambda r: "/finish" in r.url and r.status == 200):
        page.reload()  # back online: the kept outcome goes out on the next visit
    attempt = PuzzleAttempt.objects.get()
    assert attempt.finished_at is not None and attempt.solved is False


def test_no_new_puzzle_while_an_outcome_is_unsent(page: Page, live_server, mate2_puzzle):
    page.route("**/finish", lambda route: route.abort())
    asked = []
    page.on("request", lambda req: asked.append(req.url) if req.url.endswith("/api/v1/puzzles/next") else None)
    start(page, live_server)
    play(page, MATE2["wrong_first"])
    page.get_by_role("button", name="Show solution").click()
    expect(page.get_by_text("We'll save this when you're back online.")).to_be_visible(timeout=30000)
    page.get_by_role("button", name="Next puzzle").click()
    expect(page.get_by_text("isn't saved yet")).to_be_visible()
    assert len(asked) == 1
