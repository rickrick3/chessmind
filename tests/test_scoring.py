"""Scoring is pure: no database. The fixture lesson has 6 scored items: s3 (1), s4 (1), s5 (3 white moves), s6 (1)."""
import copy

import pytest

from learning.domain.scoring import InvalidResult, score_attempt


def perfect():
    return [
        {"id": "s3", "tries": ["b8c6"], "hints": 0, "ms": 4000},
        {"id": "s4", "tries": [0], "hints": 0, "ms": 3000},
        {"id": "s5", "tries": [["e2e4"], ["g1f3"], ["f1c4"]], "hints": [0, 0, 0], "ms": 9000},
        {"id": "s6", "tries": [0], "hints": 0, "ms": 2000},
    ]


def entry(sub, sid):
    return next(e for e in sub if e["id"] == sid)


def test_perfect_run(valid_content):
    s = score_attempt(valid_content, perfect())
    assert (s.items, s.correct_items, s.accuracy, s.completed) == (6, 6, 1.0, True)
    assert [x.step_id for x in s.steps] == ["s3", "s4", "s5", "s6"] and all(x.correct for x in s.steps)


def test_wrong_first_try_still_completes(valid_content):
    sub = perfect()
    entry(sub, "s3")["tries"] = ["d7d5", "b8c6"]
    s = score_attempt(valid_content, sub)
    assert s.completed and s.correct_items == 5 and s.accuracy == 0.8333
    assert not s.steps[0].correct and s.steps[0].cleared


def test_also_good_counts_as_correct(valid_content):
    sub = perfect()
    entry(sub, "s3")["tries"] = ["d7d6"]
    assert score_attempt(valid_content, sub).accuracy == 1.0


def test_hint_makes_item_incorrect(valid_content):
    sub = perfect()
    entry(sub, "s4")["hints"] = 1
    assert score_attempt(valid_content, sub).correct_items == 5


def test_play_line_hint_costs_only_that_move(valid_content):
    sub = perfect()
    entry(sub, "s5")["hints"] = [0, 1, 0]
    s = score_attempt(valid_content, sub)
    assert s.correct_items == 5 and s.completed and not s.steps[2].correct


def test_play_line_alternative_from_also_accept(valid_content):
    sub = perfect()
    entry(sub, "s5")["tries"] = [["e2e4"], ["g1f3"], ["f1b5"]]
    s = score_attempt(valid_content, sub)
    assert s.accuracy == 1.0 and s.completed


def test_unfinished_step_is_not_cleared(valid_content):
    sub = perfect()
    entry(sub, "s3")["tries"] = ["d7d5", "f7f6"]
    s = score_attempt(valid_content, sub)
    assert not s.completed and not s.steps[0].cleared


def test_missing_scored_step_not_completed(valid_content):
    sub = [e for e in perfect() if e["id"] != "s6"]
    s = score_attempt(valid_content, sub)
    assert not s.completed and s.items == 6 and s.correct_items == 5


def test_unscored_steps_may_be_sent(valid_content):
    sub = perfect() + [{"id": "s1", "tries": [], "hints": 0, "ms": 1500}]
    assert score_attempt(valid_content, sub).completed


def test_min_accuracy_blocks_completion(valid_content):
    valid_content["completion"] = {"min_accuracy": 0.9}
    sub = perfect()
    entry(sub, "s3")["tries"] = ["d7d5", "b8c6"]
    assert not score_attempt(valid_content, sub).completed


def test_ms_and_skills_are_kept(valid_content):
    s = score_attempt(valid_content, perfect())
    assert s.steps[0].ms == 4000 and s.steps[0].skills == ["development"]


def illegal_move(sub):
    entry(sub, "s3")["tries"] = ["e2e5"]


def illegal_line_move(sub):
    entry(sub, "s5")["tries"][1] = ["g1g5"]


def unknown_id(sub):
    sub.append({"id": "nope", "tries": [0], "hints": 0, "ms": 1})


def duplicate_id(sub):
    sub.append(copy.deepcopy(sub[0]))


def wrong_line_count(sub):
    entry(sub, "s5")["tries"] = [["e2e4"], ["g1f3"]]


def eleven_tries(sub):
    entry(sub, "s3")["tries"] = ["d7d5"] * 10 + ["b8c6"]


def tries_not_list(sub):
    entry(sub, "s4")["tries"] = "0"


def fifty_one_entries(sub):
    sub.extend({"id": f"x{i}", "tries": [], "hints": 0, "ms": 0} for i in range(47))


def choice_out_of_range(sub):
    entry(sub, "s4")["tries"] = [7]


def bool_as_index(sub):
    entry(sub, "s4")["tries"] = [True]


def negative_ms(sub):
    entry(sub, "s4")["ms"] = -5


def line_hints_not_list(sub):
    entry(sub, "s5")["hints"] = 0


def not_an_object(sub):
    sub.append("s3")


def empty_line_tries(sub):
    entry(sub, "s5")["tries"][0] = []


@pytest.mark.parametrize("mutate", [illegal_move, illegal_line_move, unknown_id, duplicate_id, wrong_line_count,
                                    eleven_tries, tries_not_list, fifty_one_entries, choice_out_of_range,
                                    bool_as_index, negative_ms, line_hints_not_list, not_an_object,
                                    empty_line_tries])
def test_hostile_payloads_raise(valid_content, mutate):
    sub = perfect()
    mutate(sub)
    with pytest.raises(InvalidResult):
        score_attempt(valid_content, sub)


def test_submission_must_be_a_list(valid_content):
    with pytest.raises(InvalidResult):
        score_attempt(valid_content, {"s3": ["b8c6"]})
