"""The beginner course (curriculum/seed/beginner.json): every lesson passes the structure and Stockfish checks."""
import json
from pathlib import Path

import pytest

from curriculum.domain.schema import check_structure, has_failures
from curriculum.validation import engine_issues
from skills.domain.areas import ALL_THEMES, AREAS

SEED = Path(__file__).parent.parent / "curriculum" / "seed" / "beginner.json"
EXPECTED_UNITS = ["pieces", "material", "safety", "mates", "opening-principles", "first-endgames"]
UNIT_ORDER = {"pieces": 0, "material": 2, "safety": 3, "mates": 4, "opening-principles": 5, "first-endgames": 6}
ALLOWED_WARNINGS = {"inaccurate_line_move"}  # an opening line may hold a slightly inaccurate main-line move


def course() -> dict:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    assert [c["slug"] for c in data["courses"]] == ["fundamentals"]
    return data["courses"][0]


def all_lessons() -> list[dict]:
    return [les for u in course()["units"] for les in u["lessons"]]


def lesson_slugs() -> list[str]:
    try:
        return [les["slug"] for les in all_lessons()]
    except FileNotFoundError:
        return ["missing-seed-file"]


def lesson(slug: str) -> dict:
    return next(les for les in all_lessons() if les["slug"] == slug)


@pytest.mark.django_db
@pytest.mark.parametrize("slug", lesson_slugs())
def test_lesson_passes_every_check(slug):
    content = lesson(slug)["content"]
    issues = check_structure(content)
    if not has_failures(issues):
        issues += engine_issues(content)
    assert [i for i in issues if i.level == "fail" or i.check not in ALLOWED_WARNINGS] == []


def test_course_shape():
    c = course()
    assert (c["track"], c["order"], c["title"]) == ("path", 1, {"fr": "Fondamentaux", "en": "Fundamentals"})
    units = c["units"]
    assert [u["slug"] for u in units] == EXPECTED_UNITS[:len(units)] and units
    assert all(u["order"] == UNIT_ORDER[u["slug"]] for u in units)
    assert all(len(u["lessons"]) == 5 for u in units)
    lessons = all_lessons()
    assert len({les["slug"] for les in lessons}) == len(lessons)
    assert not {les["slug"] for les in lessons} & {"piece-values", "checks-captures-threats", "mate-in-one"}
    for les in lessons:
        steps = les["content"]["steps"]
        scored = [s for s in steps if s["type"] in ("find_move", "choice", "play_line")]
        assert len(scored) >= 2, les["slug"]
        assert all(s.get("skills") for s in scored), les["slug"]
        assert all(t in ALL_THEMES or t in AREAS for s in steps for t in s.get("skills", [])), les["slug"]
    for u in units:
        assert {s["type"] for les in u["lessons"] for s in les["content"]["steps"]} == {
            "explain", "show_moves", "find_move", "choice", "play_line"}, u["slug"]
