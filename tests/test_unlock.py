from learning.domain.unlock import LessonNode, lesson_states, next_up


def node(slug, position, unit_index=0, track="path", prerequisites=()):
    return LessonNode(slug, track, unit_index, position, frozenset(prerequisites))


NODES3 = [node("a", 0), node("b", 1), node("c", 2)]
TWO_UNITS = [node("a", 0, 0), node("b", 1, 0), node("c", 2, 1), node("d", 3, 1), node("e", 4, 2)]


def test_new_learner_path():
    assert lesson_states(NODES3, set(), "new") == {"a": "current", "b": "locked", "c": "locked"}


def test_completing_unlocks_next():
    assert lesson_states(NODES3, {"a"}, "new") == {"a": "done", "b": "current", "c": "locked"}


def test_blank_start_level_is_like_new():
    assert lesson_states(NODES3, set(), "") == {"a": "current", "b": "locked", "c": "locked"}


def test_rules_starts_at_the_second_unit():
    assert lesson_states(TWO_UNITS, set(), "rules") == {
        "a": "open", "b": "open", "c": "current", "d": "open", "e": "locked"}


def test_club_starts_at_the_third_unit():
    assert lesson_states(TWO_UNITS, {"a"}, "club") == {
        "a": "done", "b": "open", "c": "open", "d": "open", "e": "current"}


def test_current_falls_back_when_the_start_unit_is_done():
    assert lesson_states(TWO_UNITS, {"c", "d", "e"}, "rules")["a"] == "current"


def test_earlier_basics_progress_opens_the_unit_after_it():  # Review Focus 2
    states = lesson_states(TWO_UNITS, {"c", "d"}, "new")  # unit 1 done before unit 0 existed
    assert (states["a"], states["b"], states["c"], states["e"]) == ("current", "locked", "done", "open")


def test_next_unit_opens_after_last_lesson_of_previous():
    assert lesson_states(TWO_UNITS, {"a", "b"}, "new")["c"] == "current"


def test_prerequisite_locks_catalog_lesson():
    nodes = NODES3 + [node("scotch", 0, track="openings", prerequisites={"b"}), node("italian", 1, track="openings")]
    states = lesson_states(nodes, {"a"}, "new")
    assert states["scotch"] == "locked" and states["italian"] == "open"
    assert lesson_states(nodes, {"a", "b"}, "new")["scotch"] == "open"


def test_prerequisite_also_applies_on_the_path():
    nodes = [node("a", 0), node("b", 1, prerequisites={"x"}), node("x", 0, track="endgames")]
    assert lesson_states(nodes, {"a"}, "new")["b"] == "locked"


def test_next_up_is_the_current_lesson():
    states = lesson_states(NODES3, {"a"}, "new")
    assert next_up(states, NODES3, {"a": 0.2}) == "b"


def test_next_up_revisits_weakest_when_path_is_done():
    states = lesson_states(NODES3, {"a", "b", "c"}, "new")
    assert next_up(states, NODES3, {"a": 0.9, "b": 0.5, "c": 0.65}) == "b"
    assert next_up(states, NODES3, {"a": 0.9, "b": 0.8, "c": 0.7}) is None
