"""Engine checks run real Stockfish at the test depth (8)."""
import chess
import pytest

from analysis import engine
from curriculum.domain.workflow import DRAFT, PENDING_REVIEW, VALIDATING
from curriculum.services import new_version, request_validation
from curriculum.validation import engine_issues, grade

pytestmark = pytest.mark.django_db

AFTER_E4_D5 = "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2"  # Qg4?? loses the queen to Bxg4
BACK_RANK = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"  # Ra8#
START = chess.STARTING_FEN
T = {"fr": "x", "en": "x"}


def lesson_with(step: dict) -> dict:
    return {"schema": 1, "steps": [{"id": "s1", "prompt": T, "hint": T, "correct": T, **step}]}


def codes(issues):
    return {(i.check, i.level) for i in issues}


def test_grade_names_blunder_and_best():
    assert grade(chess.Board(AFTER_E4_D5), "d1g4") == "blunder"
    assert grade(chess.Board(BACK_RANK), "a1a8") == "best"


def test_blunder_as_answer_is_refuted():
    issues = engine_issues(lesson_with({"type": "find_move", "fen": AFTER_E4_D5, "accept": ["d1g4"]}))
    assert ("answer_refuted", "fail") in codes(issues)


def test_mate_in_one_answer_passes():
    assert engine_issues(lesson_with({"type": "find_move", "fen": BACK_RANK, "accept": ["a1a8"]})) == []


def test_wrong_move_that_is_fine_warns():
    issues = engine_issues(lesson_with({"type": "find_move", "fen": START, "accept": ["e2e4"],
                                        "wrong": [{"uci": "d2d4", "feedback": T}]}))
    assert codes(issues) == {("wrong_move_is_fine", "warn")}


def test_line_blunder_fails_but_opponent_moves_are_not_graded():
    step = {"type": "play_line", "fen": START, "side": "white", "moves": ["e2e4", "d7d5", "d1g4"]}
    assert ("line_move_refuted", "fail") in codes(engine_issues(lesson_with(step)))
    step = {"type": "play_line", "fen": START, "side": "black", "moves": ["e2e4", "d7d5", "d1g4", "c8g4"]}
    assert engine_issues(lesson_with(step)) == []


def test_valid_lesson_reaches_pending_review(lesson_factory, staff, valid_content,
                                             django_capture_on_commit_callbacks):
    v = new_version(lesson_factory(), staff, content=valid_content)
    with django_capture_on_commit_callbacks(execute=True):
        request_validation(v, staff)
    v.refresh_from_db()
    assert v.status == PENDING_REVIEW
    assert not [i for i in v.validation_report["issues"] if i["level"] == "fail"]
    assert v.validation_report["engine_depth"] == 8 and v.validation_report["checked_at"]
    assert [(e.from_status, e.to_status, e.actor) for e in v.events.all()][-1] == (VALIDATING, PENDING_REVIEW, None)


def test_failure_returns_to_draft_with_report(lesson_factory, staff, valid_content,
                                              django_capture_on_commit_callbacks):
    valid_content["steps"][2]["accept"] = ["b8c6", "d8g5"]  # s3: Qg5?? loses the queen to Nxg5
    v = new_version(lesson_factory(), staff, content=valid_content)
    with django_capture_on_commit_callbacks(execute=True):
        request_validation(v, staff)
    v.refresh_from_db()
    assert v.status == DRAFT
    assert any(i["check"] == "answer_refuted" and i["step_id"] == "s3" for i in v.validation_report["issues"])
    assert v.events.last().note == "validation failed"


def test_structure_failure_skips_engine(lesson_factory, staff, valid_content, mocker,
                                        django_capture_on_commit_callbacks):
    spy = mocker.spy(engine, "analyse")
    del valid_content["steps"][0]["text"]["en"]
    v = new_version(lesson_factory(), staff, content=valid_content)
    with django_capture_on_commit_callbacks(execute=True):
        request_validation(v, staff)
    v.refresh_from_db()
    assert v.status == DRAFT and spy.call_count == 0


def test_engine_crash_returns_to_draft(lesson_factory, staff, valid_content, mocker,
                                       django_capture_on_commit_callbacks):
    mocker.patch.object(engine, "analyse", side_effect=RuntimeError("engine died"))
    v = new_version(lesson_factory(), staff, content=valid_content)
    with django_capture_on_commit_callbacks(execute=True):
        request_validation(v, staff)
    v.refresh_from_db()
    assert v.status == DRAFT and "engine died" in v.error
