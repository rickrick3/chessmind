"""The Train hub, the puzzle page and the unrated replay page."""
import pytest
from django.utils import timezone

from puzzles.services import finish_puzzle
from tests.puzzle_data import MISSED, SOLVED, serve

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def test_train_hub_renders_for_anyone(client):
    r = client.get("/train/")
    assert r.status_code == 200 and "/train/puzzles/" in r.content.decode()


def test_train_hub_shows_the_rating_range(guest_client, puzzle_factory):
    client, guest = guest_client
    assert "Not rated yet" in client.get("/train/").content.decode()
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    html = client.get("/train/").content.decode()
    assert "Your rating about" in html and "still settling" in html


def test_nav_has_train(guest_client):
    client, _ = guest_client
    html = client.get("/learn/").content.decode()
    assert html.count('href="/train/"') == 2  # sidebar and bottom bar


def test_puzzle_page_config_and_credit(client):
    page = client.get("/train/puzzles/?theme=fork")
    config = page.context["config"]
    assert (config["mode"], config["theme"]) == ("theme", "fork")
    assert config["finishUrl"] == "/api/v1/puzzle-attempts/{id}/finish" and config["nextUrl"] == "/api/v1/puzzles/next"
    assert client.get("/train/puzzles/?theme=nope").context["config"]["mode"] == "rated"
    assert "Puzzles from the Lichess puzzle database (CC0)" in page.content.decode()
    assert '?theme=fork' in page.content.decode()


def test_recent_results(guest_client, puzzle_factory):
    client, guest = guest_client
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, MISSED, NOW)
    html = client.get("/train/puzzles/").content.decode()
    assert html.count('data-result="solved"') == 1 and html.count('data-result="missed"') == 1


def test_replay_needs_own_attempt(guest_client, puzzle_factory):
    client, guest = guest_client
    p = puzzle_factory()
    assert client.get(f"/train/puzzles/{p.lichess_id}/").status_code == 404
    serve(guest, p)
    r = client.get(f"/train/puzzles/{p.lichess_id}/")
    assert r.status_code == 200 and "finishUrl" not in r.context["config"]
    assert r.context["config"]["puzzle"] == {"fen": p.fen, "moves": p.moves, "side": "white"}


def test_french(client):
    assert "Problèmes" in client.get("/train/puzzles/", HTTP_ACCEPT_LANGUAGE="fr").content.decode()
