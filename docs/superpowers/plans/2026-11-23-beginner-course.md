# Beginner Course Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 30 new beginner lessons in six units of the Fundamentals path, start levels that match the new first unit, and lesson checks that catch a correct answer the lesson would mark wrong.

**Architecture:** Lessons are data: one seed file, `curriculum/seed/beginner.json`, in the existing lesson schema, imported with the existing `import_lessons` command into the existing `fundamentals` course. Two new lesson checks: a pure one in `curriculum/domain/schema.py` and an engine one in `curriculum/validation.py`. The start-level rule lives in `learning/domain/unlock.py`.

**Tech Stack:** Django 5, python-chess, Stockfish (depth 8 in tests), pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-beginner-course-design.md` (approved 2026-11-23).

**Branch:** `chessmind-course`, from `chessmind-puzzles`. Stage files by name (`manage.py` has an unrelated change).

## Global Constraints

- Lesson schema 1 (`curriculum/domain/schema.py`): 6–15 steps, every text `{fr, en}` ≤ 280 characters, English SAN in both languages, no engine numbers, no move in a text that the lesson doesn't contain, legal FENs and moves.
- Skill tags only from the skills vocabulary (`skills/domain/areas.py`: area keys and Lichess theme keys).
- Lessons reach learners only after Farel publishes them in `/studio/`; nothing here publishes a lesson.
- Existing lesson slugs `piece-values`, `checks-captures-threats`, `mate-in-one` and unit `basics` (order 1) stay as they are.
- Units, in order: `pieces` (0), `basics` (1, existing), `material` (2), `safety` (3), `mates` (4), `opening-principles` (5), `first-endgames` (6).
- Difficulty 1–2 for units `pieces`, `material`, `safety`; 2–3 for `mates`, `opening-principles`, `first-endgames`.
- Run tests with `docker compose run --rm test pytest <path> -v`. Commit messages without a `Co-Authored-By` trailer.

## Review Focus

1. A learner plays a correct answer the lesson doesn't list (a second checkmate, an equally good capture) and is told it's wrong. Tests in Task 2; every lesson passes them in Tasks 3–8.
2. A learner who finished the three `basics` lessons before this course existed keeps that progress, and the unit after `basics` opens for them. Test in Task 1.
3. A "Knows the rules" or "Club player" learner is sent to the first lesson of their start unit, not to "Rook and bishop". Test in Task 1.
4. French texts stay within 280 characters and read French piece letters (the display converts English SAN). Checked by the per-lesson test in Tasks 3–8 (`text_too_long` is not allowed).
5. Farel publishes the course gradually or rejects a lesson: the path and unlocking work with whatever is published. Covered by `path_nodes()`, which numbers published lessons only; no new code.

---

### Task 1: Start levels for the new first unit

**Files:** Modify `learning/domain/unlock.py`, `tests/test_unlock.py`

**Interfaces:**
- Produces: `OPENED_UNITS = {"rules": {0, 1}, "club": {0, 1, 2}}`; `START_UNIT = {"rules": 1, "club": 2}`; `lesson_states(nodes, completed, start_level)` unchanged in signature. "current" = the first open, unfinished path lesson with `unit_index >= START_UNIT.get(start_level, 0)`; if there is none, the first open path lesson.

- [ ] **Step 1: Update and add tests** (TWO_UNITS has units 0, 1, 2):

```python
def test_rules_starts_at_the_second_unit():
    assert lesson_states(TWO_UNITS, set(), "rules") == {
        "a": "open", "b": "open", "c": "current", "d": "open", "e": "locked"}

def test_club_starts_at_the_third_unit():
    assert lesson_states(TWO_UNITS, {"a"}, "club") == {
        "a": "done", "b": "open", "c": "open", "d": "open", "e": "current"}

def test_current_falls_back_when_the_start_unit_is_done():
    assert lesson_states(TWO_UNITS, {"c", "d", "e"}, "rules")["a"] == "current"

def test_earlier_basics_progress_opens_the_unit_after_it():   # Review Focus 2
    states = lesson_states(TWO_UNITS, {"c", "d"}, "new")       # unit 1 done before unit 0 existed
    assert (states["a"], states["b"], states["c"], states["e"]) == ("current", "locked", "done", "open")
```
(`test_rules_opens_unit_one` and `test_club_opens_two_units` are replaced by the first two.)

- [ ] **Step 2: Run** `docker compose run --rm test pytest tests/test_unlock.py -v` → the new tests FAIL.
- [ ] **Step 3: Implement** the two constants and the "current" rule in `learning/domain/unlock.py`.
- [ ] **Step 4: Run** `docker compose run --rm test pytest tests/test_unlock.py tests/test_path_profile.py tests/test_attempts.py -v` → PASS.
- [ ] **Step 5: Commit** `git add learning/domain/unlock.py tests/test_unlock.py docs/superpowers/specs/2026-11-23-beginner-course-design.md docs/superpowers/plans/2026-11-23-beginner-course.md && git commit -m "feat: start levels for the beginner course"`

### Task 2: Checks for correct answers a lesson would reject

**Files:** Modify `curriculum/domain/schema.py`, `curriculum/validation.py`, `tests/test_schema.py`, `tests/test_validation.py`

**Interfaces:**
- Produces:
  - In `check_structure`: for a `find_move` step whose `accept` contains a checkmating move, every legal checkmating move of the position must be in `accept` or `also_good`, else `Issue("missing_mate", "fail", "<SAN list>", step_id)`.
  - In `engine_issues`: for a `find_move` step, any move from the engine's multi-PV lines (`engine.analyse(board).lines`, MULTIPV 3) that is not in `accept`/`also_good` and grades `best` or `good` gives `Issue("unaccepted_good_answer", "warn", "<SAN> grades <grade>", step_id)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schema.py
def test_every_mate_must_be_accepted(valid):
    valid["steps"].append({"id": "two-mates", "type": "find_move", "fen": "7k/2p3pp/2p5/8/8/8/5PPP/RR4K1 w - - 0 1",
        "prompt": T, "correct": T, "hint": T, "accept": ["a1a8"]})
    issues = [i for i in check_structure(valid) if i.check == "missing_mate"]
    assert len(issues) == 1 and "Rb8#" in issues[0].detail

# tests/test_validation.py (real Stockfish, depth 8)
def test_an_unaccepted_equal_capture_is_flagged():
    # two pieces can take the undefended black queen: Rxd5 and Nxd5
    step = {"type": "find_move", "fen": "4k3/8/8/3q4/8/4N3/8/3RK3 w - - 0 1", "accept": ["d1d5"]}
    issues = engine_issues(lesson_with(step))
    assert [i.check for i in issues] == ["unaccepted_good_answer"]
```
(`T` is any valid `{fr, en}` text; `lesson_with` exists in `tests/test_validation.py`. Confirm both FENs with python-chess before relying on them; adjust the position, not the assertion, if one is wrong.)

- [ ] **Step 2: Run** `docker compose run --rm test pytest tests/test_schema.py tests/test_validation.py -v` → FAIL.
- [ ] **Step 3: Implement** both checks.
- [ ] **Step 4: Run** `docker compose run --rm test pytest tests/test_schema.py tests/test_validation.py tests/test_seed.py -v` → PASS (the seed lessons must still pass with no failure).
- [ ] **Step 5: Commit** `git commit -m "feat: lesson checks for correct answers a lesson would reject"`

### Tasks 3–8: One unit each

Task 3 `pieces` · Task 4 `material` · Task 5 `safety` · Task 6 `mates` · Task 7 `opening-principles` · Task 8 `first-endgames`, with the lessons the spec lists, in that order.

**Files:** Modify `curriculum/seed/beginner.json` (created in Task 3: `{"courses": [{"slug": "fundamentals", "track": "path", "order": 1, "title": {"fr": "Fondamentaux", "en": "Fundamentals"}, "description": {"fr": "Les bases pour bien commencer.", "en": "The basics to start well."}, "units": [...]}]}` — the course fields copied from `foundation.json` so importing either file leaves them unchanged); Create in Task 3, extend after: `tests/test_beginner_course.py`.

**Lesson slugs** (stable from now on): `pieces`: `rook-bishop`, `queen-king`, `knight`, `pawn`, `check-castling-mate`; `material`: `free-pieces`, `forks`, `pins`, `skewers`, `discovered-attacks`; `safety`: `opponent-threats`, `saving-a-piece`, `out-of-check`, `back-rank-safety`, `trading-ahead`; `mates`: `ladder-mate`, `supported-queen-mate`, `queen-king-mate`, `rook-king-mate`, `mate-in-two`; `opening-principles`: `take-the-centre`, `develop`, `castle-early`, `queen-out-early`, `italian-game`; `first-endgames`: `square-rule`, `active-king`, `opposition`, `king-pawn-king`, `cut-off-the-king`.

Each lesson: `kind` (`concept` for units `pieces` and `opening-principles` except `italian-game` = `opening`; `tactic` for `material`, `safety`, `mates`; `endgame` for `first-endgames`), `difficulty` per Global Constraints, `content` with 6–10 steps, at least two scored steps (`find_move`, `choice` or `play_line`), and skill tags on scored steps. Each unit uses all five step types somewhere.

- [ ] **Step 1: Write the per-lesson test once (Task 3), parametrized over every lesson in the file**

```python
ALLOWED_WARNINGS = {"inaccurate_line_move"}   # an opening line may contain a slightly inaccurate main-line move

@pytest.mark.parametrize("slug", lesson_slugs())
def test_lesson_passes_every_check(slug):
    content = lesson(slug)["content"]
    issues = check_structure(content)
    if not has_failures(issues):
        issues += engine_issues(content)
    assert [i for i in issues if i.level == "fail" or i.check not in ALLOWED_WARNINGS] == []

def test_course_shape():
    units = course()["units"]
    assert [u["slug"] for u in units] == EXPECTED_UNITS[:len(units)]        # grows task by task
    assert all(len(u["lessons"]) == 5 for u in units)
    assert all(t in ALL_THEMES or t in AREAS for les in all_lessons() for s in les["content"]["steps"]
               for t in s.get("skills", []))
```
(`lesson_slugs()`, `lesson()`, `course()`, `all_lessons()` read `curriculum/seed/beginner.json`; `EXPECTED_UNITS` = the six new unit slugs in order.)

- [ ] **Step 2: Write the unit's five lessons** in `beginner.json`, checking each position with python-chess while writing.
- [ ] **Step 3: Run** `docker compose run --rm test pytest tests/test_beginner_course.py -v` → PASS for every lesson so far.
- [ ] **Step 4: Commit** `git add curriculum/seed/beginner.json tests/test_beginner_course.py && git commit -m "feat: beginner course unit <slug>"`

### Task 9: Import as drafts and queue validation

- [ ] **Step 1: Full suite** — `docker compose run --rm test pytest` → all pass.
- [ ] **Step 2: Import into the dev database** (drafts only): `docker compose run --rm web python manage.py import_lessons curriculum/seed/beginner.json` — needs the `web` image rebuilt with this branch, or run it from the `test` service (`docker compose run --rm test python manage.py import_lessons …`, same database). Expected: `lessons: 30 created, 0 updated; drafts: 30`.
- [ ] **Step 3: Queue the Stockfish validation** of each new draft as the system actor (`curriculum.services.request_validation(version, None)`); the running worker (`content` queue) moves each to "pending review". Check in `/studio/` that all 30 show "pending review".
- [ ] **Step 4: README** — one line under "Lessons": import `beginner.json` after `foundation.json`. Commit.
