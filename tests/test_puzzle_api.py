"""The puzzle API: /api/v1/puzzles/next, /api/v1/puzzle-attempts/<id>/finish, /api/v1/puzzles/<id>/report."""
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from gamification.models import XpEvent
from puzzles.models import PuzzleReport
from tests.puzzle_data import SOLVED, serve

pytestmark = pytest.mark.django_db
NOW = timezone.now()


def post(client, url, data):
    return client.post(url, data, content_type="application/json")


def test_next_creates_guest_and_returns_puzzle(client, puzzle_factory):
    p = puzzle_factory()
    r = post(client, "/api/v1/puzzles/next", {"mode": "rated", "timezone": "Europe/Paris"})
    assert r.status_code == 200 and client.session.get("learner_id")
    body = r.json()
    assert body["puzzle"] == {"fen": p.fen, "moves": p.moves, "side": "white"}
    assert (body["mode"], body["theme"]) == ("rated", "") and body["attempt_id"]


def test_next_requires_csrf(puzzle_factory):
    puzzle_factory()
    r = Client(enforce_csrf_checks=True).post("/api/v1/puzzles/next", {"mode": "rated"},
                                              content_type="application/json")
    assert r.status_code == 403


def test_next_errors(guest_client, puzzle_factory):
    client, _ = guest_client
    r = post(client, "/api/v1/puzzles/next", {"mode": "x"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"
    r = post(client, "/api/v1/puzzles/next", {"mode": "rated"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_puzzle"
    assert client.get("/api/v1/puzzles/next").status_code == 405


def test_finish_round_trip(guest_client, puzzle_factory):
    client, _ = guest_client
    puzzle_factory()
    attempt = post(client, "/api/v1/puzzles/next", {"mode": "rated"}).json()["attempt_id"]
    r = post(client, f"/api/v1/puzzle-attempts/{attempt}/finish", SOLVED)
    assert r.status_code == 200 and r.json()["solved"] is True
    again = post(client, f"/api/v1/puzzle-attempts/{attempt}/finish", SOLVED)
    assert again.status_code == 200 and again.json() == r.json()


def test_finish_errors(guest_client, account, puzzle_factory):
    client, guest = guest_client
    a = serve(guest, puzzle_factory())
    r = post(client, f"/api/v1/puzzle-attempts/{a.pk}/finish", {**SOLVED, "played": ["a2a8"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_result" and not XpEvent.objects.exists()
    other = serve(account.learner, puzzle_factory())
    assert post(client, f"/api/v1/puzzle-attempts/{other.pk}/finish", SOLVED).status_code == 404
    old = serve(guest, puzzle_factory(), NOW - timedelta(hours=25))
    assert post(client, f"/api/v1/puzzle-attempts/{old.pk}/finish", SOLVED).status_code == 410
    r = client.post(f"/api/v1/puzzle-attempts/{a.pk}/finish", "x" * (64 * 1024 + 1), content_type="application/json")
    assert r.status_code == 400
    assert post(Client(), f"/api/v1/puzzle-attempts/{a.pk}/finish", SOLVED).status_code == 404


def test_report_once(guest_client, puzzle_factory):
    client, guest = guest_client
    p = puzzle_factory()
    serve(guest, p)
    url = f"/api/v1/puzzles/{p.lichess_id}/report"
    assert post(client, url, {"reason": "wrong_solution"}).status_code == 201
    assert post(client, url, {"reason": "other", "note": "?"}).status_code == 200
    assert PuzzleReport.objects.count() == 1 and PuzzleReport.objects.get().reason == "wrong_solution"
    assert post(client, url, {"reason": "nope"}).status_code == 400
    assert post(client, url, {"reason": "other", "note": "x" * 501}).status_code == 400
    assert post(client, f"/api/v1/puzzles/{puzzle_factory().lichess_id}/report", {"reason": "other"}).status_code == 404
    assert post(client, "/api/v1/puzzles/nothere/report", {"reason": "other"}).status_code == 404
