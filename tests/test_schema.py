import copy
import json
from pathlib import Path

import pytest

from curriculum.domain.san import frenchify
from curriculum.domain.schema import allowed_san, check_structure, has_failures, localize, player_move_indexes

FIX = Path(__file__).parent / "fixtures" / "lessons"
START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture
def valid():
    return json.loads((FIX / "valid_lesson.json").read_text(encoding="utf-8"))


def step(content, sid):
    return next(s for s in content["steps"] if s["id"] == sid)


def checks(issues):
    return {(i.check, i.level, i.step_id) for i in issues}


def test_valid_fixture_has_no_issues(valid):
    assert check_structure(valid) == []


def test_missing_english_fails(valid):
    del step(valid, "s3")["prompt"]["en"]
    assert ("language", "fail", "s3") in checks(check_structure(valid))


def test_missing_required_field_fails(valid):
    del step(valid, "s3")["accept"]
    assert ("schema", "fail", "s3") in checks(check_structure(valid))


def test_illegal_fen(valid):
    step(valid, "s1")["fen"] = "not a fen"
    assert ("illegal_position", "fail", "s1") in checks(check_structure(valid))


def test_illegal_accepted_move(valid):
    step(valid, "s3")["accept"] = ["e2e5"]
    assert ("illegal_move", "fail", "s3") in checks(check_structure(valid))


def test_play_line_illegal_at_index_three(valid):
    step(valid, "s5")["moves"][3] = "b8b6"
    issues = [i for i in check_structure(valid) if i.check == "illegal_move"]
    assert issues and issues[0].step_id == "s5" and "3" in issues[0].detail


def test_duplicate_step_id(valid):
    step(valid, "s2")["id"] = "s1"
    assert ("duplicate_id", "fail", "s1") in checks(check_structure(valid))


def test_text_names_unknown_move(valid):
    step(valid, "s3")["correct"]["en"] = "Qh5 is the answer."
    assert ("unknown_move_in_text", "fail", "s3") in checks(check_structure(valid))


def test_text_may_name_a_square(valid):
    step(valid, "s3")["correct"]["en"] = "Nc6 guards the square d4 and the pawn on e5."
    assert check_structure(valid) == []


def test_french_letters_in_source_fail(valid):
    step(valid, "s3")["correct"]["fr"] = "Cc6 défend e5."
    assert ("unknown_move_in_text", "fail", "s3") in checks(check_structure(valid))


def test_explain_and_meta_may_name_any_move_of_the_lesson(valid):
    step(valid, "s1")["text"]["en"] = "Soon you will play Bc4."
    valid["meta"]["description"]["en"] = "From e4 to Bc4."
    assert check_structure(valid) == []


@pytest.mark.parametrize("text,bad", [("+1.3", True), ("45 cp", True), ("-0,8", True), ("3 pieces", False),
                                      ("move 12", False), ("the result 1-0", False)])
def test_engine_numbers(valid, text, bad):
    step(valid, "s4")["explanation"]["en"] = f"The queen: {text}."
    assert (("engine_numbers", "fail", "s4") in checks(check_structure(valid))) is bad


def test_long_text_and_step_count_are_warnings(valid):
    step(valid, "s1")["text"]["en"] = "x" * 300
    valid["steps"] = valid["steps"][:4]
    found = checks(check_structure(valid))
    assert ("text_too_long", "warn", "s1") in found and ("step_count", "warn", None) in found
    assert not has_failures(check_structure(valid))


@pytest.mark.parametrize("answer,options", [(3, None), (0, [{"text": {"fr": "a", "en": "a"}}])])
def test_bad_choice_is_schema_failure(valid, answer, options):
    s = step(valid, "s4")
    s["answer"] = answer
    if options is not None:
        s["options"] = options
    assert ("schema", "fail", "s4") in checks(check_structure(valid))


def test_bad_meta(valid):
    valid["meta"]["difficulty"] = 9
    valid["meta"]["orientation"] = "red"
    assert ("schema", "fail", None) in checks(check_structure(valid))


def test_not_a_lesson():
    assert has_failures(check_structure({"steps": "nope"}))
    assert has_failures(check_structure([]))


def test_player_move_indexes():
    assert player_move_indexes({"fen": START, "side": "white",
                                "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"]}) == [0, 2, 4]
    after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert player_move_indexes({"fen": after_e4, "side": "white", "moves": ["e7e5", "g1f3", "b8c6"]}) == [1]


def test_allowed_san_follows_the_line(valid):
    assert allowed_san(step(valid, "s5")) == {"e4", "e5", "Nf3", "Nc6", "Bc4", "Bb5"}
    assert allowed_san(step(valid, "s3")) == {"Nc6", "d6", "f6"}


@pytest.mark.parametrize("en,fr", [("Nf3", "Cf3"), ("Kxe2", "Rxe2"), ("e8=Q", "e8=D"), ("O-O", "O-O"),
                                   ("exd5", "exd5"), ("Rd1+", "Td1+"), ("Bxf7#", "Fxf7#"), ("Qh5", "Dh5")])
def test_frenchify(en, fr):
    assert frenchify(f"Play {en} now") == f"Play {fr} now"


def test_frenchify_leaves_words_alone():
    assert frenchify("Bravo, the Queen wins a Rook") == "Bravo, the Queen wins a Rook"


def test_localize_flattens_and_keeps_answers(valid):
    original = copy.deepcopy(valid)
    fr = localize(valid, "fr")
    assert fr["meta"]["title"] == "Les premiers coups"
    assert step(fr, "s3")["correct"] == "Cc6 défend e5 et sort un cavalier."
    assert step(fr, "s3")["accept"] == ["b8c6"] and step(fr, "s5")["notes"]["4"] == "Fc4 vise f7."
    assert step(fr, "s4")["options"][0] == {"text": "La dame"} and step(fr, "s6")["options"][0] == {"uci": "f1c4"}
    en = localize(valid, "en")
    assert step(en, "s3")["correct"] == "Nc6 defends e5 and develops a knight."
    assert valid == original
