# Puzzles and Skill Profile (Project 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A learner at any level solves rated Lichess puzzles at their level on a phone, the server re-scores every result and moves a Glicko-2 puzzle rating, and every puzzle and lesson answer becomes evidence behind a per-skill estimate, with confidence, strengths and weaknesses shown on a new Skills tab.

**Architecture:** Two new Django apps beside the milestone 1 apps. `puzzles` owns the catalogue (import from the Lichess CSV), attempts, the rating, the puzzle API and the Train pages. `skills` owns the skill vocabulary, the evidence ledger, estimates, diagnosis and the Skills pages. Rules live in pure `domain/` modules (no ORM, no I/O): `puzzles/domain/{lichess,glicko2,solution,selection}.py` and `skills/domain/{areas,estimate,diagnosis}.py`. `services.py` wraps them in transactions, views are thin. The puzzle board is a new set of ES modules in `static/js/puzzles/` reusing the lesson player's `board.js` and `san.js`.

**Tech Stack:** Python 3.12, Django 5.2, Postgres 16 (`ArrayField`, `GinIndex`), Celery 5, python-chess, `zstandard` (new, import command only), cm-chessboard + chess.js (vendored), pytest-django, Playwright for the end-to-end tests.

**Spec:** `docs/superpowers/specs/2026-11-22-puzzles-skill-profile-design.md` (approved 2026-11-22). Read it alongside this plan; section numbers below (§5.3 …) refer to it.

**Branch:** `chessmind-puzzles`, created from `chessmind-foundation` (milestone 1, not merged yet). Never commit to `main`. Stage files by name: the working tree has an unrelated line-ending change in `manage.py` that must not be committed.

## Global Constraints

- Django pages + the JS player modules; no SPA, no Django REST Framework, no JS build step. New Python runtime dependency: `zstandard` only (used only by `import_puzzles`).
- French and English for every UI string. Every new template/Python/JS string gets a French entry in `locale/fr/LC_MESSAGES/django.po`; run `docker compose run --rm test python manage.py compilemessages -l fr` and commit `.po` and `.mo` together.
- The browser checks moves instantly; the server re-scores every submission before any rating, XP or evidence is written. A garbled or hostile body answers 400 and writes nothing. A repeated finish returns the stored result with 200.
- API conventions from milestone 1: errors are `{"error": {"code": "...", "message": "..."}}`; every POST needs the CSRF token; another learner's object answers 404; attempt ids are UUIDs and act as idempotency keys; bodies over `API_MAX_BODY` (64 KB) answer 400; attempts expire after `ATTEMPT_EXPIRY_HOURS` (24) with HTTP 410.
- No learner request calls Lichess, Stockfish or Gemini.
- Ratings and skill estimates are shown as ranges rounded to 50 ("about 1250–1350"), never as one exact number; "still settling" while the rating deviation is above 110.
- Credit line, exactly: "Puzzles from the Lichess puzzle database (CC0)" — on the puzzle page footer and in the README.
- Phones first: every page works at 390 px wide; touch targets ≥ 44 px.
- Only a learner's first attempt at a puzzle is rated; only rated attempts earn XP and evidence. Only a learner's first finished attempt at a lesson gives evidence.
- One missed puzzle never shows as a weakness; "repeated mistake" is stored, never shown.
- Run tests in Docker with the code mounted: `docker compose run --rm test pytest <path> -v`; end-to-end: `docker compose --profile e2e run --rm e2e`. If Docker Desktop has stopped, restart it before concluding a test fails.
- Commit messages: plain conventional messages (`feat: …`, `test: …`), no `Co-Authored-By` trailer.

## Review Focus

1. A learner who runs out of puzzles near their level — a 2,700-rated player, or a theme with few puzzles — still gets the nearest unseen puzzle, and once every puzzle in the mode is seen gets a clear "you've seen every puzzle here" message, not an error page. Tests in Tasks 7 and 9.
2. A double-tapped or retried finish on a slow phone network: the second call returns the stored result with 200, and there is one rating change and one XP row. Test in Task 8.
3. A learner back after weeks away, in a time zone far from UTC (America/Montreal near midnight): idle days are counted in the learner's local days and the rating deviation grows before the next update. Test in Task 8.
4. A puzzle deactivated by staff while a learner has it open: the learner can still finish it, and it is never served to anyone again. Tests in Tasks 7 and 8.
5. A guest who never chose a start level starts at 1000; choosing a level later does not reset a rating that already exists. Test in Task 8.

---

## File Structure

```
chess-coach/
  requirements.txt                      # + zstandard
  config/settings.py                    # INSTALLED_APPS + "puzzles", "skills" (after "gamification"); PUZZLE_*, SKILL_*, XP_PUZZLE_SOLVED
  config/urls.py                        # + puzzles, skills pages; + puzzles API under api/v1/
  conftest.py                           # + puzzle_factory
  README.md                             # + Puzzles section (download, import, backfill, credit)
  puzzles/                              # catalogue, attempts, rating, API, Train pages
    models.py admin.py apps.py services.py api.py urls_api.py views.py urls.py
    domain/lichess.py domain/glicko2.py domain/solution.py domain/selection.py
    management/commands/import_puzzles.py
  skills/                               # vocabulary, evidence, estimates, diagnosis, Skills pages
    models.py admin.py apps.py services.py views.py urls.py labels.py
    domain/areas.py domain/estimate.py domain/diagnosis.py
    management/commands/backfill_evidence.py
  gamification/models.py, domain/xp.py, services.py   # puzzle XP reason, award_for_puzzle
  learning/services.py                  # finish_attempt writes lesson evidence and recomputes skills
  learning/views.py                     # profile "skills" tab
  curriculum/domain/schema.py           # warn on unknown skill tags
  templates/partials/nav.html           # + Train
  templates/puzzles/train.html puzzles.html replay.html
  templates/skills/area.html
  templates/learning/profile.html       # + Skills tab
  static/js/puzzles/main.js run.js ui.js replay.js
  static/css/puzzles.css
  tests/puzzle_data.py                  # MATE2, ALT_MATE, PROMOTION positions shared by tests and e2e
  tests/fixtures/puzzles/sample.csv
  tests/test_puzzle_import.py test_glicko2.py test_puzzle_solution.py test_skill_areas.py
  tests/test_skill_estimate.py test_skill_diagnosis.py test_skill_evidence.py
  tests/test_puzzle_selection.py test_puzzle_finish.py test_puzzle_api.py test_puzzle_merge.py
  tests/test_train_pages.py test_skills_pages.py
  e2e/test_puzzles.py
```

### Shared test positions (`tests/puzzle_data.py`, created in Task 1)

All three were checked with python-chess. `fen` is the position before the opponent's move, as in the Lichess file.

```python
MATE2 = {  # Lichess 00sHx, rating 1760: 1...Kd7 2.Be6+ Kd8 3.Qf8#
    "fen": "q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17",
    "moves": ["e8d7", "a2e6", "d7d8", "f7f8"],
    "start_fen": "q5nr/1ppknQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 w - - 1 18",
    "side": "white",
    "wrong_first": "f7f6",      # legal, not the solution, not mate
    "wrong_second": "a3b4",     # legal after 2.Be6+ Kd8, not mate
    "illegal_first": "a2a8",
    "themes": ["mate", "mateIn2", "middlegame", "short"],
}
ALT_MATE = {  # 1...c6 2.Ra8#; 2.Rb8# also mates
    "fen": "7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1",
    "moves": ["c7c6", "a1a8"], "side": "white", "alternative": "b1b8",
    "themes": ["backRankMate", "mate", "mateIn1", "oneMove", "endgame"],
}
PROMOTION = {  # 1...h6 2.g8=Q#; 2.g8=R# also mates
    "fen": "k7/6Pp/1K6/8/8/8/8/8 b - - 0 1",
    "moves": ["h7h6", "g7g8q"], "side": "white", "alternative": "g7g8r",
    "themes": ["promotion", "mate", "mateIn1", "oneMove", "endgame", "pawnEndgame"],
}
```

---

### Task 1: Branch, puzzles app, models, catalogue import

**Files:**
- Create: `puzzles/__init__.py`, `puzzles/apps.py`, `puzzles/models.py`, `puzzles/admin.py`, `puzzles/domain/__init__.py`, `puzzles/domain/lichess.py`, `puzzles/management/__init__.py`, `puzzles/management/commands/__init__.py`, `puzzles/management/commands/import_puzzles.py`, `puzzles/migrations/0001_initial.py`, `tests/puzzle_data.py`, `tests/fixtures/puzzles/sample.csv`, `tests/test_puzzle_import.py`
- Modify: `config/settings.py` (INSTALLED_APPS: add `"puzzles"` after `"gamification"`), `requirements.txt` (+ `zstandard>=0.23`), `conftest.py` (+ `puzzle_factory`), `README.md` (+ "Puzzles" section)

**Interfaces:**
- Produces:
  - `Puzzle(lichess_id CharField(10) unique, fen CharField(100), moves ArrayField(CharField(5)), rating int, rating_deviation int, popularity int, plays int, themes ArrayField(CharField(30)) default list, opening_tags ArrayField(CharField(80)) default list, game_url URLField blank, side CharField(5) "white"|"black", start_fen CharField(100), is_active bool default True, imported_at DateTimeField default now)`; indexes `Index(fields=["is_active", "rating"])`, `GinIndex(fields=["themes"])`.
  - `PuzzleAttempt(id UUIDField pk default uuid4, learner FK accounts.Learner CASCADE related "puzzle_attempts", puzzle FK Puzzle PROTECT related "attempts", mode CharField(5) ∈ {"rated","theme"}, theme CharField(30) blank, served_at default now, finished_at null, solved bool null, rated bool default True, learner_rating_before float null, rating_after float null, rd_after float null, played ArrayField(CharField(5)) default list, hints int default 0, solution_shown bool default False, ms int default 0, result JSON null)`; `UniqueConstraint(fields=["learner", "puzzle"], condition=Q(rated=True), name="one_rated_attempt_per_puzzle")`; `Index(fields=["learner", "finished_at"])`.
  - `PuzzleRating(learner OneToOneField accounts.Learner CASCADE primary_key related "puzzle_rating", rating float, rd float, volatility float, rated_count int default 0, solved_count int default 0, last_rated_on DateField null)`.
  - `PuzzleReport(learner FK accounts.Learner CASCADE related "puzzle_reports", puzzle FK Puzzle CASCADE related "reports", reason CharField(16) ∈ {"wrong_solution","other"}, note TextField(max_length=500) blank, created_at auto_now_add)`; unique (learner, puzzle).
  - `puzzles.domain.lichess`: `PuzzleRow` frozen dataclass (`lichess_id, fen, moves: tuple[str, ...], rating, rating_deviation, popularity, plays, themes: tuple[str, ...], opening_tags: tuple[str, ...], game_url, side, start_fen`); `parse_row(row: dict[str, str]) -> PuzzleRow | None`; `band(rating: int) -> int | None`; `derive(fen: str, moves: list[str]) -> tuple[str, str]` returning `(side, start_fen)`.
  - Command `import_puzzles <path> [--per-band 2000] [--min-popularity 80] [--min-plays 300] [--max-rd 90] [--seed 1]`.
  - Fixture `puzzle_factory(lichess_id=None, *, data=MATE2, rating=1500, rd=80, themes=None, is_active=True) -> Puzzle` (themes default to `data["themes"]`; side and start_fen from `derive`).

- [ ] **Step 1: Create the branch and commit the spec and this plan**

```bash
git checkout chessmind-foundation && git checkout -b chessmind-puzzles
git add docs/superpowers/specs/2026-11-22-puzzles-skill-profile-design.md docs/superpowers/plans/2026-11-22-puzzles-skill-profile.md
git commit -m "docs: puzzles and skill profile design and plan"
```

- [ ] **Step 2: Write `tests/puzzle_data.py`** (the block under "Shared test positions") and `tests/fixtures/puzzles/sample.csv`:

```
PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags,DailyDate
pMate2,q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17,e8d7 a2e6 d7d8 f7f8,1760,80,90,5000,mate mateIn2 middlegame short,https://lichess.org/yyznGmXs/black#34,Italian_Game Italian_Game_Classical_Variation,
pAlt1,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1a8,900,75,95,4000,backRankMate mate mateIn1 oneMove endgame,https://lichess.org/abcdefgh#1,,
pPromo,k7/6Pp/1K6/8/8/8/8/8 b - - 0 1,h7h6 g7g8q,1200,75,92,3000,promotion mate mateIn1 oneMove endgame pawnEndgame,https://lichess.org/abcdefgi#1,,
pUnpop,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1a8,950,75,50,4000,mate mateIn1,https://lichess.org/x1#1,,
pFewPl,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1a8,960,75,95,100,mate mateIn1,https://lichess.org/x2#1,,
pHighRd,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1a8,970,120,95,4000,mate mateIn1,https://lichess.org/x3#1,,
pTooHi,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1a8,3000,75,95,4000,mate mateIn1,https://lichess.org/x4#1,,
pIllgl,7k/2p3pp/8/8/8/8/5PPP/RR4K1 b - - 0 1,c7c6 a1h8,980,75,95,4000,mate mateIn1,https://lichess.org/x5#1,,
```

- [ ] **Step 3: Write the failing tests** in `tests/test_puzzle_import.py`

```python
def test_parse_row_derives_side_and_start():
    row = parse_row(csv_row("pMate2"))
    assert row.side == "white" and row.start_fen == MATE2["start_fen"]
    assert row.moves == tuple(MATE2["moves"]) and row.themes == ("mate", "mateIn2", "middlegame", "short")
    assert row.opening_tags == ("Italian_Game", "Italian_Game_Classical_Variation")

@pytest.mark.parametrize("moves", ["c7c6 a1h8", "c7c6", "c7c6 a1a8 h8g8", ""])
def test_parse_row_rejects_illegal_single_and_odd(moves):
    assert parse_row({**csv_row("pAlt1"), "Moves": moves}) is None

def test_parse_row_rejects_bad_numbers_and_fen():
    assert parse_row({**csv_row("pAlt1"), "Rating": "abc"}) is None
    assert parse_row({**csv_row("pAlt1"), "FEN": "not a fen"}) is None

def test_band_limits():
    assert (band(399), band(400), band(2799), band(2800)) == (None, 400, 2700, None)

def test_import_filters(db, tmp_path):
    call_command("import_puzzles", str(SAMPLE))
    assert set(Puzzle.objects.values_list("lichess_id", flat=True)) == {"pMate2", "pAlt1", "pPromo"}
    p = Puzzle.objects.get(lichess_id="pMate2")
    assert (p.rating, p.side, p.is_active) == (1760, "white", True)

def test_import_reads_zst(db, tmp_path):
    path = tmp_path / "sample.csv.zst"
    path.write_bytes(zstandard.ZstdCompressor().compress(SAMPLE.read_bytes()))
    call_command("import_puzzles", str(path))
    assert Puzzle.objects.count() == 3

def test_import_caps_each_band_deterministically(db, tmp_path):
    path = write_csv(tmp_path, [{**csv_row("pMate2"), "PuzzleId": f"m{i}", "Rating": "1750"} for i in range(10)])
    call_command("import_puzzles", str(path), "--per-band", "4")
    first = set(Puzzle.objects.filter(is_active=True).values_list("lichess_id", flat=True))
    call_command("import_puzzles", str(path), "--per-band", "4")
    assert len(first) == 4 and set(Puzzle.objects.filter(is_active=True).values_list("lichess_id", flat=True)) == first

def test_reimport_deactivates_missing_and_keeps_attempted(db, tmp_path, guest):
    call_command("import_puzzles", str(SAMPLE))
    PuzzleAttempt.objects.create(learner=guest, puzzle=Puzzle.objects.get(lichess_id="pAlt1"), mode="rated")
    path = write_csv(tmp_path, [csv_row("pMate2"), csv_row("pPromo")])
    call_command("import_puzzles", str(path))
    alt = Puzzle.objects.get(lichess_id="pAlt1")
    assert alt.is_active is False and Puzzle.objects.filter(is_active=True).count() == 2
```

`csv_row(id)` reads `SAMPLE` with `csv.DictReader` and returns the row with that `PuzzleId`; `write_csv(tmp_path, rows)` writes rows under the same header and returns the path.

- [ ] **Step 4: Run to verify they fail**

Run: `docker compose run --rm test pytest tests/test_puzzle_import.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'puzzles'`)

- [ ] **Step 5: Implement**
  - `pip` dependency `zstandard>=0.23` in `requirements.txt`; rebuild the test image (`docker compose build test`).
  - `parse_row`: split `Moves` and `Themes`/`OpeningTags` on spaces; ints for Rating, RatingDeviation, Popularity, NbPlays; `chess.Board(fen)` must be valid; every move legal in turn; at least 2 moves and an even number (the solution ends on the learner's move); any exception → `None`.
  - `band(r)`: `r // 100 * 100` when `400 <= r < 2800`, else `None`.
  - `import_puzzles`: open `.zst` with `zstandard.ZstdDecompressor().stream_reader` wrapped in `io.TextIOWrapper(encoding="utf-8")`, plain files directly; `csv.DictReader`; keep rows passing the filters (`Popularity ≥ min-popularity`, `NbPlays ≥ min-plays`, `RatingDeviation ≤ max-rd`, `band` not None, `parse_row` not None); per band a reservoir sample of `--per-band` with `random.Random(seed)` (deterministic for the same file). In one `transaction.atomic()`: `Puzzle.objects.update(is_active=False)`, then `bulk_create(update_conflicts=True, unique_fields=["lichess_id"], update_fields=[every other field], batch_size=1000)` with `is_active=True`. Print one line per band (`1700: 2000`), a warning for bands under `--per-band`, then `Imported N puzzles; M inactive.`
  - Admin: `PuzzleAdmin` (list: lichess_id, rating, is_active; filter is_active; search lichess_id; action "Deactivate selected puzzles"); `PuzzleReportAdmin` (list: puzzle, reason, note, created_at; action "Deactivate the reported puzzles"); `PuzzleAttempt` and `PuzzleRating` read-only.
  - README "Puzzles": download `https://database.lichess.org/lichess_db_puzzle.csv.zst`, run `docker compose run --rm -v "$PWD:/data" web python manage.py import_puzzles /data/lichess_db_puzzle.csv.zst`, the credit line.

- [ ] **Step 6: Run to verify they pass**

Run: `docker compose run --rm test pytest tests/test_puzzle_import.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add requirements.txt config/settings.py conftest.py README.md puzzles tests/puzzle_data.py tests/fixtures/puzzles tests/test_puzzle_import.py
git commit -m "feat: puzzles app, models and lichess puzzle import"
```

---

### Task 2: Glicko-2

**Files:**
- Create: `puzzles/domain/glicko2.py`, `tests/test_glicko2.py`

**Interfaces:**
- Produces:
  - `SCALE = 173.7178`
  - `Rating(rating: float, rd: float, volatility: float)` frozen dataclass; `Game(rating: float, rd: float, score: float)` frozen dataclass
  - `rate(player: Rating, games: list[Game], tau: float) -> Rating` — one Glicko-2 rating period (Glickman, "Example of the Glicko-2 system", steps 2–8, volatility by the Illinois algorithm with ε = 0.000001); with no games only the deviation grows by one period
  - `idle(player: Rating, periods: int, rd_max: float) -> Rating` — φ* = √(φ² + periods·σ²) on the Glicko-2 scale, capped at `rd_max`; `periods <= 0` returns `player`
  - `expected(rating: float, opp_rating: float, opp_rd: float) -> float` — E(μ, μj, φj)

- [ ] **Step 1: Write the failing tests**

```python
def test_glickman_example():
    r = rate(Rating(1500, 200, 0.06), [Game(1400, 30, 1), Game(1550, 100, 0), Game(1700, 300, 0)], tau=0.5)
    assert r.rating == pytest.approx(1464.06, abs=0.01)
    assert r.rd == pytest.approx(151.52, abs=0.01)
    assert r.volatility == pytest.approx(0.05999, abs=1e-5)

def test_win_raises_and_loss_lowers():
    p = Rating(1500, 100, 0.06)
    assert rate(p, [Game(1500, 80, 1)], 0.5).rating > 1500 > rate(p, [Game(1500, 80, 0)], 0.5).rating

def test_idle_grows_rd_and_caps():
    p = Rating(1500, 50, 0.06)
    assert idle(p, 0, 350) == p and idle(p, 10, 350).rd > 50 and idle(p, 100_000, 350).rd == 350

def test_expected():
    assert expected(1500, 1500, 0) == pytest.approx(0.5) and expected(1700, 1500, 80) > 0.5
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_glicko2.py -v` → FAIL (import error)
- [ ] **Step 3: Implement** `puzzles/domain/glicko2.py` following Glickman's paper exactly (convert with `SCALE` and 1500).
- [ ] **Step 4: Run to verify they pass** — same command → PASS
- [ ] **Step 5: Commit** — `git add puzzles/domain/glicko2.py tests/test_glicko2.py && git commit -m "feat: glicko-2 rating"`

---

### Task 3: Puzzle solution checking

**Files:**
- Create: `puzzles/domain/solution.py`, `tests/test_puzzle_solution.py`

**Interfaces:**
- Consumes: `learning.domain.scoring.MAX_MS`
- Produces:
  - `InvalidPuzzleResult(ValueError)`
  - `Outcome(solved: bool, played: tuple[str, ...], hints: int, solution_shown: bool, ms: int)` frozen dataclass
  - `learner_move_count(moves: list[str]) -> int` = `len(moves) // 2`
  - `score_puzzle(fen: str, moves: list[str], body: dict) -> Outcome`

The finish body is `{"played": [uci, …], "hints": int, "solution_shown": bool, "ms": int}`. It refines §5.3's "tries per learner move": rated play stops at the first wrong move, so one list of the learner's moves up to the decisive moment carries the same information.

Rules (the algorithm the tests pin):
- Shapes: `played` a list of strings, at most `learner_move_count(moves)` long; `hints` an int (not bool) from 0 to 10; `solution_shown` a bool; `ms` an int from 0 to `MAX_MS`. Otherwise `InvalidPuzzleResult`.
- Replay: from `fen` push `moves[0]`; learner move *k* is checked in the position after the solution's first `2k+1` moves. Each played move must be legal there. It is **correct** when it equals `moves[2k+1]` or gives checkmate.
- A wrong move must be the last entry; a checkmating move must be the last entry.
- Outcome: last entry wrong → missed; else `hints > 0` or `solution_shown` → missed; else complete (all learner moves played, or the last one mates) → solved; else (undecided) → `InvalidPuzzleResult`.

- [ ] **Step 1: Write the failing tests**

```python
def body(played, hints=0, shown=False, ms=1000):
    return {"played": played, "hints": hints, "solution_shown": shown, "ms": ms}

def test_solved_line():
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6", "f7f8"])).solved is True

@pytest.mark.parametrize("data", [ALT_MATE, PROMOTION])
def test_alternative_mate_solves(data):
    assert score_puzzle(data["fen"], data["moves"], body([data["alternative"]])).solved is True

def test_wrong_move_is_missed():
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body([MATE2["wrong_first"]])).solved is False
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6", MATE2["wrong_second"]])).solved is False

def test_hint_or_solution_is_missed():
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body([], hints=1)).solved is False
    assert score_puzzle(MATE2["fen"], MATE2["moves"], body(["a2e6"], shown=True)).solved is False

@pytest.mark.parametrize("b", [
    body([MATE2["illegal_first"]]), body([MATE2["wrong_first"], "a2e6"]), body(["a2e6", "f7f8", "f8f7"]),
    body(["a2e6"]), body([]), body(["a2e6"], hints=True), body([], hints=11), {"played": "a2e6"},
    body(["a2e6", "f7f8"], ms=-1), body([42]),
])
def test_rejects(b):
    with pytest.raises(InvalidPuzzleResult):
        score_puzzle(MATE2["fen"], MATE2["moves"], b)
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_puzzle_solution.py -v` → FAIL
- [ ] **Step 3: Implement** `score_puzzle` per the rules above with python-chess.
- [ ] **Step 4: Run to verify they pass** — same command → PASS
- [ ] **Step 5: Commit** — `git add puzzles/domain/solution.py tests/test_puzzle_solution.py && git commit -m "feat: server-side puzzle solution check"`

---

### Task 4: Skill vocabulary, labels and the lesson tag warning

**Files:**
- Create: `skills/__init__.py`, `skills/apps.py`, `skills/domain/__init__.py`, `skills/domain/areas.py`, `skills/labels.py`, `tests/test_skill_areas.py`
- Modify: `config/settings.py` (INSTALLED_APPS: `"skills"` right after `"puzzles"`), `curriculum/domain/schema.py` (`_check_common`), `tests/fixtures/lessons/valid_lesson.json` (tags), `tests/test_scoring.py:89`, `tests/test_schema.py`, `locale/fr/LC_MESSAGES/django.po` + `.mo`

**Interfaces:**
- Produces (`skills.domain.areas`, exact contents):
  - `AREAS = ("tactics", "calculation", "openings", "positional", "strategy", "endgames", "defense", "decisions", "time")`
  - `TACTIC_MOTIFS = frozenset({"fork", "pin", "skewer", "discoveredAttack", "discoveredCheck", "doubleCheck", "hangingPiece", "trappedPiece", "deflection", "attraction", "clearance", "interference", "xRayAttack", "capturingDefender", "sacrifice", "intermezzo", "quietMove", "zugzwang", "defensiveMove", "attackingF2F7", "exposedKing", "promotion", "underPromotion", "advancedPawn"})`
  - `NAMED_MATES = frozenset({"anastasiaMate", "arabianMate", "backRankMate", "balestraMate", "blindSwineMate", "bodenMate", "cornerMate", "doubleBishopMate", "dovetailMate", "epauletteMate", "hookMate", "killBoxMate", "morphysMate", "operaMate", "pillsburysMate", "smotheredMate", "swallowstailMate", "triangleMate", "vukovicMate"})`
  - `MATES = NAMED_MATES | {"mate", "mateIn1", "mateIn2", "mateIn3", "mateIn4", "mateIn5"}`
  - `ENDGAME_TYPES = frozenset({"bishopEndgame", "knightEndgame", "pawnEndgame", "queenEndgame", "queenRookEndgame", "rookEndgame"})`
  - `MOTIF_THEMES = TACTIC_MOTIFS | MATES | ENDGAME_TYPES` (diagnosable); `TACTICS_THEMES = TACTIC_MOTIFS | MATES`
  - `NOT_DIAGNOSED = frozenset({"opening", "middlegame", "endgame", "oneMove", "short", "long", "veryLong", "advantage", "crushing", "equality", "master", "masterVsMaster", "superGM", "castling", "enPassant", "collinearMove", "kingsideAttack", "queensideAttack"})` — the spec's phase/length/evaluation/source list, plus five themes it does not name (`castling`, `enPassant`, `collinearMove`, `kingsideAttack`, `queensideAttack`), which describe a kind of move or a side of the board rather than a skill
  - `ALL_THEMES = MOTIF_THEMES | NOT_DIAGNOSED` (73 keys, the Lichess list)
  - `PUZZLE_AREA_THEMES = {"calculation": frozenset({"long", "veryLong", "mateIn3", "mateIn4", "mateIn5", "intermezzo", "quietMove"}), "defense": frozenset({"defensiveMove", "equality"}), "endgames": frozenset({"endgame", "zugzwang"}) | ENDGAME_TYPES}`
  - `ALIASES = {"defence": "defense", "threats": "defense", "defenders": "defense", "back-rank": "backRankMate", "smothered": "smotheredMate", "cct": "tactics", "checks": "tactics", "captures": "tactics", "piece-values": None, "trades": None, "queen": None}`
  - `LESSON_KIND_AREA = {"tactic": "tactics", "opening": "openings", "endgame": "endgames"}`
  - `puzzle_areas(themes: Iterable[str]) -> set[str]` — always `"tactics"`, plus every area whose `PUZZLE_AREA_THEMES` set meets `themes`
  - `canonical_tags(tags: Iterable[str]) -> list[str]` — aliases applied, `None` aliases and unknown tags dropped, first-seen order, no duplicates
  - `unknown_tags(tags: Iterable[str]) -> list[str]` — tags neither in `AREAS`, `ALL_THEMES` nor `ALIASES`
  - `lesson_step_areas(tags: Iterable[str], lesson_kind: str) -> set[str]` — from `canonical_tags`: an area key gives itself; a theme gives `"tactics"` when in `TACTICS_THEMES` plus every `PUZZLE_AREA_THEMES` area containing it; nothing found → `{LESSON_KIND_AREA[kind]}` when the kind has one, else empty
  - `diagnosable(theme: str) -> bool` = `theme in MOTIF_THEMES`
  - `skills.labels`: `AREA_LABELS: dict[str, str]` (lazy; Tactics, Calculation, Openings, Positional play, Strategy, Endgames, Defence, Decisions, Time management) and `THEME_LABELS: dict[str, str]` (lazy, one per key of `ALL_THEMES`, our own wording, e.g. `fork` "Fork", `mateIn2` "Mate in 2", `backRankMate` "Back-rank mate"); `area_label(key) -> str`, `theme_label(key) -> str` (fall back to the key)

- [ ] **Step 1: Write the failing tests** in `tests/test_skill_areas.py`, and add to `tests/test_schema.py`

```python
def test_theme_sets_partition_the_lichess_list():
    assert len(ALL_THEMES) == 73 and not (MOTIF_THEMES & NOT_DIAGNOSED)

def test_every_puzzle_feeds_tactics():
    assert puzzle_areas(["mate", "mateIn2", "middlegame", "short"]) == {"tactics"}
    assert puzzle_areas(["long", "defensiveMove", "rookEndgame"]) == {"tactics", "calculation", "defense", "endgames"}

def test_aliases_and_unknown_tags():
    assert canonical_tags(["defence", "back-rank", "cct", "queen", "nonsense", "defence"]) == ["defense", "backRankMate", "tactics"]
    assert unknown_tags(["defence", "nonsense", "fork"]) == ["nonsense"]

@pytest.mark.parametrize("tags,kind,areas", [
    (["fork"], "concept", {"tactics"}), (["intermezzo"], "concept", {"tactics", "calculation"}),
    (["queen"], "tactic", {"tactics"}), ([], "concept", set()), (["openings"], "concept", {"openings"}),
    (["threats"], "concept", {"defense"}), ([], "endgame", {"endgames"}), (["endgame"], "concept", {"endgames"}),
])
def test_lesson_step_areas(tags, kind, areas):
    assert lesson_step_areas(tags, kind) == areas

def test_labels_cover_everything():
    assert set(THEME_LABELS) == ALL_THEMES and set(AREA_LABELS) == set(AREAS)

# tests/test_schema.py
def test_unknown_skill_tag_is_a_warning(valid_content):
    valid_content["steps"][2]["skills"] = ["defence", "nonsense"]
    issues = check_structure(valid_content)
    assert [(i.check, i.level) for i in issues] == [("unknown_skill_tag", "warn")] and "nonsense" in issues[0].detail

def test_seed_lessons_have_no_unknown_tags():
    seed = json.loads(Path("curriculum/seed/foundation.json").read_text(encoding="utf-8"))
    tags = [t for c in seed["courses"] for u in c["units"] for l in u["lessons"]
            for s in l["content"]["steps"] for t in s.get("skills", [])]
    assert tags and unknown_tags(tags) == []
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_skill_areas.py tests/test_schema.py -v` → FAIL
- [ ] **Step 3: Implement** `skills/domain/areas.py`, `skills/labels.py` (gettext_lazy), and in `curriculum/domain/schema.py::_check_common` add `Issue("unknown_skill_tag", "warn", ", ".join(unknown), sid)` when `unknown_tags(skills)` is non-empty. In `tests/fixtures/lessons/valid_lesson.json` change the tags `center` → `positional`, `development` → `openings`, `italian` → `openings` (they would now warn, and `test_schema.py` expects no issues), and in `tests/test_scoring.py:89` expect `["openings"]`. French entries for every label.
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_skill_areas.py tests/test_schema.py tests/test_scoring.py tests/test_seed.py -v` → PASS
- [ ] **Step 5: Commit**

```bash
git add config/settings.py skills curriculum/domain/schema.py tests/fixtures/lessons/valid_lesson.json tests/test_scoring.py tests/test_schema.py tests/test_skill_areas.py locale/fr/LC_MESSAGES/django.po locale/fr/LC_MESSAGES/django.mo
git commit -m "feat: skill areas, puzzle theme mapping and lesson tag warnings"
```

---

### Task 5: Skill estimates and diagnosis (pure)

**Files:**
- Create: `skills/domain/estimate.py`, `skills/domain/diagnosis.py`, `tests/test_skill_estimate.py`, `tests/test_skill_diagnosis.py`
- Modify: `config/settings.py` (the `SKILL_*` settings below)

**Interfaces:**
- Consumes: `puzzles.domain.glicko2.expected`
- Produces:
  - Settings: `SKILL_PUZZLE_WINDOW = 40`, `SKILL_LESSON_WINDOW = 30`, `SKILL_MIN_OBSERVATIONS = 10`, `SKILL_RELIABLE_OBSERVATIONS = 25`, `SKILL_RELIABLE_DAYS = 3`, `SKILL_IMPROVING_SPLIT = 15`, `SKILL_IMPROVING_POINTS = 100`, `SKILL_IMPROVING_RATE = 0.20`, `SKILL_LESSON_WEAK = 0.5`, `SKILL_LESSON_STRONG = 0.85`, `SKILL_REPEATED_MISSES = 3`, `SKILL_REPEATED_DAYS = 14`
  - `SkillRules` frozen dataclass with those fields (lower-case, without the prefix) and those defaults; `SkillRules.from_settings()`
  - `Observation(success: bool, local_date: date, difficulty: int | None = None, learner_rating: float | None = None, tags: tuple[str, ...] = ())` frozen dataclass; lists are ordered oldest first
  - `Estimate(basis: str, value: float | None, low: int | None, high: int | None, observations: int, days: int, confidence: str, comparison: str)` frozen dataclass — basis ∈ {"puzzle","lesson","none"}, confidence ∈ {"none","early","reliable"}, comparison ∈ {"","stronger","same","weaker"}
  - `performance(results: list[tuple[int, bool]]) -> float` — the R with Σ `expected(R, r_i, 0)` = number solved, by bisection on [min r − 400, max r + 400] to 0.5; all solved → max + 400; all missed → min − 400
  - `margin(n: int) -> int` = `int(round(350 / sqrt(n), -1))`
  - `round50(x: float) -> int` = `int(round(x / 50) * 50)`
  - `confidence(n: int, days: int, rules: SkillRules) -> str` — n < 10 "none"; n ≥ 25 and days ≥ 3 "reliable"; else "early"
  - `estimate(puzzle_obs: list[Observation], lesson_obs: list[Observation], overall: float | None, rules: SkillRules) -> Estimate` — §5.7: puzzle basis when ≥ 10 puzzle observations (window: newest 40; value = `performance`; low/high = `round50(value ∓ margin(n))`; comparison against `overall` only when it is not None: `weaker` if value < overall − margin, `stronger` if value > overall + margin, else `same`); else lesson basis when ≥ 10 lesson observations (newest 30; value = success rate 0–1; no low/high, no comparison); else basis "none" (value None, confidence "none", observations = the larger count). `days` = distinct local dates in the window used.
  - `skills.domain.diagnosis.status(est: Estimate, puzzle_obs, lesson_obs, rules) -> str` ∈ {"", "improving", "confirmed_weakness", "emerging_weakness", "stable_strength"}, precedence in that order. Improving: basis puzzle, ≥ 30 puzzle observations, `performance(newest 15) − performance(15 before) ≥ 100`; basis lesson, ≥ 30 lesson observations, success-rate gain ≥ 0.20. Weakness: puzzle basis with comparison `weaker`, or lesson basis with rate < 0.5 — `confirmed_weakness` when confidence is reliable, `emerging_weakness` when early. Strength: puzzle basis with comparison `stronger`, or lesson basis with rate > 0.85, and confidence reliable. Basis "none" → "".
  - `repeated_mistake(puzzle_obs: list[Observation], today: date, rules) -> bool` — at least 3 misses with `(today − local_date).days < 14` and `difficulty <= learner_rating`

- [ ] **Step 1: Write the failing tests**

```python
R = SkillRules()
def obs(n, solved=(), days=1, difficulty=1500, start=date(2026, 11, 1), learner_rating=1500):
    """n observations, success at the indexes in `solved`, spread round-robin over `days` dates."""
    return [Observation(i in solved, start + timedelta(days=i % days), difficulty, learner_rating) for i in range(n)]

# test_skill_estimate.py
def test_performance():
    assert performance([(1500, True), (1500, False)]) == pytest.approx(1500, abs=1)
    assert performance([(1200, True), (1400, True)]) == 1800 and performance([(1200, False), (1400, False)]) == 800

def test_margin_and_round50():
    assert (margin(10), margin(25), margin(40)) == (110, 70, 60) and (round50(1420), round50(1580)) == (1400, 1600)

def test_not_enough_evidence():
    e = estimate(obs(9, solved=range(5)), [], 1500, R)
    assert (e.basis, e.value, e.confidence) == ("none", None, "none")

@pytest.mark.parametrize("n,days,expected_conf", [(25, 2, "early"), (25, 3, "reliable"), (10, 5, "early")])
def test_confidence_levels(n, days, expected_conf):
    assert estimate(obs(n, solved=range(0, n, 2), days=days), [], 1500, R).confidence == expected_conf

def test_puzzle_basis_wins_at_ten():
    assert estimate(obs(10, solved={1}), obs(30, solved=range(30)), None, R).basis == "puzzle"
    e = estimate(obs(9), obs(12, solved=range(6)), None, R)
    assert (e.basis, e.value, e.observations) == ("lesson", 0.5, 12)

def test_window_uses_newest_40():
    e = estimate(obs(50, solved=range(10, 50)), [], None, R)
    assert e.value == 1900 and e.observations == 40

def test_range_and_comparison():
    e = estimate(obs(20, solved=range(10)), [], 1800, R)
    assert e.value == pytest.approx(1500, abs=1) and (e.low, e.high, e.comparison) == (1400, 1600, "weaker")
    assert estimate(obs(20, solved=range(10)), [], 1560, R).comparison == "same"

# test_skill_diagnosis.py
def test_single_miss_is_never_a_weakness():
    e = estimate(obs(1), [], 1600, R)
    assert status(e, obs(1), [], R) == ""

def test_emerging_then_confirmed_weakness():
    few = obs(12, solved={3, 9}, days=2)
    assert status(estimate(few, [], 1600, R), few, [], R) == "emerging_weakness"
    many = obs(30, solved={2, 8, 16, 22, 28}, days=3)
    assert status(estimate(many, [], 1600, R), many, [], R) == "confirmed_weakness"

def test_stable_strength():
    o = obs(30, solved=set(range(30)) - {0, 15, 29}, days=4)
    assert status(estimate(o, [], 1300, R), o, [], R) == "stable_strength"

def test_improving():
    o = obs(30, solved={0, 5, 10} | set(range(15, 27)), days=4)
    assert status(estimate(o, [], 1500, R), o, [], R) == "improving"

def test_lesson_basis_states():
    weak = obs(12, solved={0, 4, 8, 11}, days=2)
    assert status(estimate([], weak, None, R), [], weak, R) == "emerging_weakness"
    strong = obs(30, solved=set(range(30)) - {5, 17, 25}, days=3)
    assert status(estimate([], strong, None, R), [], strong, R) == "stable_strength"

def test_repeated_mistake_counts_only_expected_solves():
    today = date(2026, 11, 22)
    misses = lambda diff, ago: [Observation(False, today - timedelta(days=d), diff, 1500) for d in ago]
    assert repeated_mistake(misses(1400, (0, 3, 10)), today, R) is True
    assert repeated_mistake(misses(1700, (0, 3, 10)), today, R) is False
    assert repeated_mistake(misses(1400, (0, 10, 20)), today, R) is False
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_skill_estimate.py tests/test_skill_diagnosis.py -v` → FAIL
- [ ] **Step 3: Implement** `skills/domain/estimate.py` and `skills/domain/diagnosis.py` per the Interfaces.
- [ ] **Step 4: Run to verify they pass** — same command → PASS
- [ ] **Step 5: Commit** — `git add config/settings.py skills/domain tests/test_skill_estimate.py tests/test_skill_diagnosis.py && git commit -m "feat: skill estimates, confidence and diagnosis"`

---

### Task 6: Evidence ledger, recompute, lesson evidence, backfill

**Files:**
- Create: `skills/models.py`, `skills/admin.py`, `skills/services.py`, `skills/migrations/0001_initial.py`, `skills/management/__init__.py`, `skills/management/commands/__init__.py`, `skills/management/commands/backfill_evidence.py`, `tests/test_skill_evidence.py`
- Modify: `learning/services.py` (`finish_attempt`), `README.md` (backfill step in "Puzzles")

**Interfaces:**
- Consumes: Task 1 models, Task 4 `puzzle_areas`, `lesson_step_areas`, `canonical_tags`, `diagnosable`, `AREAS`; Task 5 `estimate`, `status`, `repeated_mistake`, `Observation`, `SkillRules`
- Produces:
  - `Evidence(learner FK accounts.Learner CASCADE related "evidence", area CharField(12) choices AREAS, source CharField(7) ∈ {"puzzle","lesson"}, puzzle_attempt FK puzzles.PuzzleAttempt null CASCADE related "evidence", step_result FK learning.StepResult null CASCADE related "evidence", success bool, difficulty int null, learner_rating float null, tags ArrayField(CharField(30)) default list, local_date DateField, created_at DateTimeField default now)`; partial unique constraints `one_area_per_puzzle_attempt` (puzzle_attempt, area) and `one_area_per_step_result` (step_result, area); `Index(fields=["learner", "area", "created_at"])`.
  - `SkillEstimate(learner FK CASCADE related "skill_estimates", kind CharField(5) ∈ {"area","theme"}, key CharField(30), basis, value float null, low int null, high int null, observations int, days int, confidence, comparison blank, status blank, repeated_mistake bool default False, updated_at auto_now)`; unique (learner, kind, key).
  - `SkillHistory(learner FK CASCADE related "skill_history", key CharField(12), local_date, basis, value float null, low int null, high int null, confidence)`; unique (learner, key, local_date).
  - `skills.services.record_puzzle_evidence(attempt: PuzzleAttempt, local_date: date) -> int` — nothing for an unrated or unfinished attempt; one row per `puzzle_areas(puzzle.themes)`: success = `attempt.solved`, difficulty = `puzzle.rating`, learner_rating = `attempt.learner_rating_before`, tags = `puzzle.themes`, created_at = `attempt.finished_at`; `bulk_create(ignore_conflicts=True)`; returns rows created.
  - `skills.services.record_lesson_evidence(attempt: LessonAttempt, step_results: list[StepResult], local_date: date) -> int` — nothing when the learner has another finished attempt at the same lesson with an earlier `finished_at`; one row per area in `lesson_step_areas(sr.skills, attempt.lesson.kind)`: success = `sr.correct`, tags = `canonical_tags(sr.skills)`, created_at = `attempt.finished_at`.
  - `skills.services.recompute(learner: Learner, now: datetime) -> None` — reads all the learner's evidence (oldest first) and `PuzzleRating.rating` as `overall` (None when absent); writes a `SkillEstimate(kind="area")` for all nine areas; for each diagnosable theme found in the tags of the learner's `tactics` puzzle rows (one per puzzle), a `SkillEstimate(kind="theme")` from those rows, with `repeated_mistake`; deletes theme rows no longer present; `SkillHistory` row for today (`learner.local_date(now)`) for each area whose basis is not "none" (update in place on the same day). Upserts with `bulk_create(update_conflicts=True, unique_fields=[...], update_fields=[...])`.
  - Command `backfill_evidence`: for every learner, for each lesson, the earliest finished attempt's step results → `record_lesson_evidence(attempt, list(attempt.steps.all()), learner.local_date(attempt.finished_at))`, then `recompute(learner, timezone.now())`; prints `Evidence rows created: N`. Idempotent.
  - `learning.services.finish_attempt`: after `attempt.save(...)`, inside the same transaction, `record_lesson_evidence(attempt, <the StepResult objects just created>, learner.local_date(now))` and `recompute(learner, now)`. The response is unchanged.

- [ ] **Step 1: Write the failing tests** in `tests/test_skill_evidence.py`

```python
def finished(learner, puzzle, solved, when, rated=True, before=1500):
    return PuzzleAttempt.objects.create(learner=learner, puzzle=puzzle, mode="rated", served_at=when,
                                        finished_at=when, solved=solved, rated=rated, learner_rating_before=before)

def test_puzzle_evidence_one_row_per_area(guest, puzzle_factory):
    p = puzzle_factory(themes=["long", "defensiveMove", "fork"], rating=1600)
    assert record_puzzle_evidence(finished(guest, p, True, NOW), NOW.date()) == 3
    rows = Evidence.objects.filter(learner=guest)
    assert set(rows.values_list("area", flat=True)) == {"tactics", "calculation", "defense"}
    assert all(r.success and r.difficulty == 1600 and r.source == "puzzle" for r in rows)

def test_unrated_attempt_gives_no_evidence(guest, puzzle_factory):
    assert record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW, rated=False), NOW.date()) == 0

def test_lesson_finish_writes_evidence_on_first_attempt_only(guest, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = []
    lesson = lesson_factory("tac", kind="tactic")
    publish(lesson, valid_content)
    for _ in range(2):
        finish_attempt(guest, start_attempt(guest, lesson, NOW).id, PERFECT_STEPS, NOW)
    assert Evidence.objects.filter(learner=guest, area="tactics", source="lesson").count() == 4

def test_recompute_writes_all_areas(guest, puzzle_factory):
    for i in range(12):
        record_puzzle_evidence(finished(guest, puzzle_factory(), i % 2 == 0, NOW), NOW.date())
    recompute(guest, NOW)
    by_key = {e.key: e for e in SkillEstimate.objects.filter(learner=guest, kind="area")}
    assert set(by_key) == set(AREAS)
    assert (by_key["tactics"].basis, by_key["tactics"].confidence, by_key["tactics"].observations) == ("puzzle", "early", 12)
    assert by_key["openings"].basis == "none"

def test_theme_rows_only_for_motifs(guest, puzzle_factory):
    record_puzzle_evidence(finished(guest, puzzle_factory(themes=["fork", "short", "middlegame"]), False, NOW), NOW.date())
    recompute(guest, NOW)
    assert list(SkillEstimate.objects.filter(learner=guest, kind="theme").values_list("key", flat=True)) == ["fork"]

def test_repeated_mistake_flag_on_theme(guest, puzzle_factory):
    for d in (0, 2, 5):
        record_puzzle_evidence(finished(guest, puzzle_factory(themes=["pin"], rating=1400), False, NOW - timedelta(days=d)),
                               (NOW - timedelta(days=d)).date())
    recompute(guest, NOW)
    assert SkillEstimate.objects.get(learner=guest, kind="theme", key="pin").repeated_mistake is True

def test_history_one_row_per_area_per_day(guest, puzzle_factory):
    for i in range(10):
        record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW), NOW.date())
    recompute(guest, NOW); recompute(guest, NOW)
    assert SkillHistory.objects.filter(learner=guest, key="tactics").count() == 1
    recompute(guest, NOW + timedelta(days=1))
    assert SkillHistory.objects.filter(learner=guest, key="tactics").count() == 2

def test_backfill_maps_old_tags_and_is_idempotent(guest, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = ["defence"]
    lesson = lesson_factory("old", kind="concept")
    publish(lesson, valid_content)
    finish_attempt(guest, start_attempt(guest, lesson, NOW).id, PERFECT_STEPS, NOW)
    Evidence.objects.all().delete()           # as if recorded before this project
    call_command("backfill_evidence"); call_command("backfill_evidence")
    assert Evidence.objects.filter(learner=guest, area="defense").count() == 4

def test_deleting_the_learner_removes_evidence(guest, puzzle_factory):
    record_puzzle_evidence(finished(guest, puzzle_factory(), True, NOW), NOW.date())
    recompute(guest, NOW)
    guest.delete()
    assert not Evidence.objects.exists() and not SkillEstimate.objects.exists()
```

`PERFECT_STEPS = perfect_steps()` with `from tests.test_finish import perfect_steps` (the fixture lesson's four scored steps); `NOW = timezone.now()`; `puzzle_factory()` with no id gives a new puzzle each call.

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_skill_evidence.py -v` → FAIL
- [ ] **Step 3: Implement** the models + migration, services, command, the `finish_attempt` hook (keep `bulk_create`'s returned list; Postgres fills the pks), admin (read-only lists), README line `docker compose run --rm web python manage.py backfill_evidence` (run once after deploying).
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_skill_evidence.py tests/test_finish.py tests/test_attempts.py -v` → PASS
- [ ] **Step 5: Commit**

```bash
git add skills learning/services.py README.md tests/test_skill_evidence.py
git commit -m "feat: evidence ledger, skill recompute and lesson evidence"
```

---

### Task 7: Choosing the next puzzle

**Files:**
- Create: `puzzles/domain/selection.py`, `puzzles/services.py`, `tests/test_puzzle_selection.py`
- Modify: `config/settings.py` (the `PUZZLE_*` settings below)

**Interfaces:**
- Consumes: Task 1 models, Task 2 `Rating`, Task 4 `ALL_THEMES`
- Produces:
  - Settings: `PUZZLE_START_RATINGS = {"new": 700, "rules": 1000, "club": 1500}`, `PUZZLE_DEFAULT_START = 1000`, `PUZZLE_START_RD = 350`, `PUZZLE_START_VOLATILITY = 0.06`, `PUZZLE_TAU = 0.5`, `PUZZLE_RD_FLOOR = 45`, `PUZZLE_RD_MAX = 350`, `PUZZLE_SETTLING_RD = 110`, `PUZZLE_DIFFICULTY_OFFSETS = {"easier": -300, "normal": -100, "harder": 200}`, `PUZZLE_WINDOWS = (100, 200, 400, 600)`
  - `puzzles.domain.selection.target(rating: float, difficulty: str, offsets: dict[str, int]) -> int` — `round(rating) + offsets[difficulty]`; unknown difficulty → `ValueError`
  - `puzzles.services.MODES = ("rated", "theme")`, `DIFFICULTIES = ("easier", "normal", "harder")`, `class NoPuzzleLeft(Exception)`
  - `puzzles.services.start_rating(learner) -> Rating` — `PUZZLE_START_RATINGS.get(learner.start_level, PUZZLE_DEFAULT_START)`, RD 350, volatility 0.06
  - `puzzles.services.current_rating(learner) -> Rating` — the cached `PuzzleRating`, else `start_rating`
  - `puzzles.services.next_puzzle(learner, *, mode: str, theme: str = "", difficulty: str = "normal", now: datetime) -> PuzzleAttempt` — `ValueError` when mode ∉ MODES, difficulty ∉ DIFFICULTIES, mode "theme" without a theme in `ALL_THEMES`, or mode "rated" with a theme. Returns the learner's open attempt in the same mode and theme (unfinished, `served_at` within `ATTEMPT_EXPIRY_HOURS`, puzzle active) when there is one. Otherwise, for each window in `PUZZLE_WINDOWS`, a random active puzzle with `|rating − target| ≤ window`, the theme when given (`themes__contains=[theme]`), and no attempt of this learner on it (any attempt, rated or not, finished or not); then the active unseen puzzle nearest the target; none → `NoPuzzleLeft`. Creates `PuzzleAttempt(learner, puzzle, mode, theme, served_at=now, rated=True)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_target_offsets():
    offsets = {"easier": -300, "normal": -100, "harder": 200}
    assert [target(1300, d, offsets) for d in ("easier", "normal", "harder")] == [1000, 1200, 1500]

def test_first_puzzle_uses_start_level(guest, puzzle_factory):
    guest.start_level = "new"; guest.save()
    low, _ = puzzle_factory(rating=600), puzzle_factory(rating=1500)
    assert next_puzzle(guest, mode="rated", now=NOW).puzzle == low

def test_never_serves_an_attempted_puzzle(guest, puzzle_factory):
    a, b = puzzle_factory(rating=900), puzzle_factory(rating=900)
    first = next_puzzle(guest, mode="rated", now=NOW)
    PuzzleAttempt.objects.filter(pk=first.pk).update(finished_at=NOW, solved=True)
    second = next_puzzle(guest, mode="rated", now=NOW)
    assert {first.puzzle, second.puzzle} == {a, b}
    PuzzleAttempt.objects.filter(pk=second.pk).update(finished_at=NOW, solved=True)
    with pytest.raises(NoPuzzleLeft):
        next_puzzle(guest, mode="rated", now=NOW)

def test_open_attempt_is_served_again(guest, puzzle_factory):
    puzzle_factory(); puzzle_factory()
    assert next_puzzle(guest, mode="rated", now=NOW).pk == next_puzzle(guest, mode="rated", now=NOW).pk

def test_open_attempt_expires_after_24h(guest, puzzle_factory):
    puzzle_factory(); puzzle_factory()
    old = next_puzzle(guest, mode="rated", now=NOW - timedelta(hours=25))
    new = next_puzzle(guest, mode="rated", now=NOW)
    assert new.pk != old.pk and new.puzzle != old.puzzle

def test_far_puzzle_is_still_served(guest, puzzle_factory):          # Review Focus 1
    far = puzzle_factory(rating=2700)
    assert next_puzzle(guest, mode="rated", now=NOW).puzzle == far

def test_theme_mode(guest, puzzle_factory):
    fork = puzzle_factory(themes=["fork", "short"]); pin = puzzle_factory(themes=["pin"])
    themed = next_puzzle(guest, mode="theme", theme="fork", now=NOW)
    rated = next_puzzle(guest, mode="rated", now=NOW)   # the open theme attempt is not reused in rated mode
    assert themed.puzzle == fork and rated.puzzle == pin and rated.pk != themed.pk

def test_inactive_puzzle_never_served(guest, puzzle_factory):        # Review Focus 4
    puzzle_factory(); puzzle_factory()
    first = next_puzzle(guest, mode="rated", now=NOW)
    Puzzle.objects.filter(pk=first.puzzle_id).update(is_active=False)
    assert next_puzzle(guest, mode="rated", now=NOW).puzzle_id != first.puzzle_id

@pytest.mark.parametrize("kw", [{"mode": "x"}, {"mode": "theme", "theme": "nonsense"}, {"mode": "theme"},
                                {"mode": "rated", "theme": "fork"}, {"mode": "rated", "difficulty": "hard"}])
def test_bad_arguments(guest, kw):
    with pytest.raises(ValueError):
        next_puzzle(guest, now=NOW, **kw)
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_puzzle_selection.py -v` → FAIL
- [ ] **Step 3: Implement** `selection.target`, the settings and `next_puzzle` (`order_by("?")` inside a window is fine at ~2,000 rows; nearest fallback with `annotate(gap=Abs(F("rating") - t)).order_by("gap")`; "unseen" as `~Exists(PuzzleAttempt.objects.filter(learner=learner, puzzle=OuterRef("pk")))`; on an `IntegrityError` from a concurrent request picking the same puzzle, retry the selection once).
- [ ] **Step 4: Run to verify they pass** — same command → PASS
- [ ] **Step 5: Commit** — `git add config/settings.py puzzles/domain/selection.py puzzles/services.py tests/test_puzzle_selection.py && git commit -m "feat: next puzzle at the learner's level"`

---

### Task 8: Finishing a puzzle: rating, XP, evidence

**Files:**
- Modify: `puzzles/services.py`, `gamification/models.py` (+ migration), `gamification/domain/xp.py`, `gamification/services.py`, `config/settings.py` (`XP_PUZZLE_SOLVED = 3`), `tests/test_xp_rules.py`
- Create: `tests/test_puzzle_finish.py`

**Interfaces:**
- Consumes: Task 2 `rate`, `idle`, `Game`, `Rating`; Task 3 `score_puzzle`, `InvalidPuzzleResult`; Task 5 `round50`; Task 6 `record_puzzle_evidence`, `recompute`; Task 7 `current_rating`, `start_rating`; `learning.services.progress_stats`
- Produces:
  - `XpEvent.REASONS` + `("puzzle", "Puzzle")`; `XpEvent.puzzle_attempt` FK `puzzles.PuzzleAttempt` null CASCADE related "xp_events"; `UniqueConstraint(fields=["puzzle_attempt", "reason"], condition=Q(puzzle_attempt__isnull=False), name="one_reason_per_puzzle_attempt")`
  - `XpRules.puzzle_solved: int = 3` (from `settings.XP_PUZZLE_SOLVED`)
  - `gamification.services.award_for_puzzle(learner, attempt, *, solved: bool, stats: ProgressStats, now: datetime) -> dict` — same return shape as `award_for_attempt` (`xp`, `streak`, `daily_goal`, `achievements`); awards `[("puzzle", rules.puzzle_solved)]` when solved, else nothing; streak and achievements as for lessons. Move the shared "write events, advance streak, grant achievements" body into one private helper used by both.
  - `puzzles.services.Expired(Exception)`
  - `puzzles.services.rating_view(rating: Rating) -> dict` = `{"value": round(r), "low": round50(r − rd), "high": round50(r + rd), "settling": rd > PUZZLE_SETTLING_RD}`
  - `puzzles.services.finish_puzzle(learner, attempt_id, body: dict, now: datetime) -> dict` — one transaction: lock the attempt (`select_for_update(of=("self",))`, filtered by learner; else `PuzzleAttempt.DoesNotExist`); finished → return `attempt.result`; `now − served_at` over `ATTEMPT_EXPIRY_HOURS` → `Expired`; `score_puzzle(puzzle.fen, puzzle.moves, body)` (nothing written on `InvalidPuzzleResult`). For a rated attempt: lock or create `PuzzleRating` (from `start_rating`), `idle(periods = max(0, (today − last_rated_on).days − 1))` with today = `learner.local_date(now)`, `rate(... [Game(puzzle.rating, puzzle.rating_deviation, 1.0 if solved else 0.0)], PUZZLE_TAU)`, `rd = max(rd, PUZZLE_RD_FLOOR)`; update the counts and `last_rated_on`; store `learner_rating_before`, `rating_after`, `rd_after`; `award_for_puzzle`; `record_puzzle_evidence`; `recompute`. An unrated attempt changes no rating, XP or evidence. Always store `played`, `hints`, `solution_shown`, `ms`, `solved`, `finished_at`, `result`.
  - The result: `{"solved": bool, "rating": {"before": int, "after": int, "change": int, "low": int, "high": int, "settling": bool}, "xp": …, "streak": …, "daily_goal": …, "achievements": […], "puzzle": {"id": lichess_id, "rating": int, "themes": [{"key": k, "label": theme_label(k)}], "game_url": str}}` — labels in the learner's language (`translation.override(learner.language)`).

- [ ] **Step 1: Add the shared helpers to `tests/puzzle_data.py`** (Tasks 9–12 import them too; the model import stays inside the function so e2e's conftest can import the module early):

```python
SOLVED = {"played": ["a2e6", "f7f8"], "hints": 0, "solution_shown": False, "ms": 9000}        # for MATE2
MISSED = {"played": [MATE2["wrong_first"]], "hints": 0, "solution_shown": False, "ms": 4000}  # for MATE2

def serve(learner, puzzle, when=None):
    from django.utils import timezone
    from puzzles.models import PuzzleAttempt
    return PuzzleAttempt.objects.create(learner=learner, puzzle=puzzle, mode="rated", served_at=when or timezone.now())
```

- [ ] **Step 2: Write the failing tests** in `tests/test_puzzle_finish.py` (+ one line in `tests/test_xp_rules.py`); `puzzle_factory()` defaults to MATE2, so `SOLVED`/`MISSED` fit

```python
def test_solved_puzzle_raises_rating_and_awards_xp(guest, puzzle_factory):
    r = finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, SOLVED, NOW)
    assert r["solved"] and r["rating"]["before"] == 1000 and r["rating"]["after"] > 1000 and r["rating"]["settling"]
    assert r["xp"]["awarded"] == 3 and r["streak"]["current"] == 1
    assert XpEvent.objects.get(learner=guest).reason == "puzzle"
    pr = PuzzleRating.objects.get(learner=guest)
    assert (pr.rated_count, pr.solved_count) == (1, 1)
    assert set(r) == {"solved", "rating", "xp", "streak", "daily_goal", "achievements", "puzzle"}
    assert {t["key"] for t in r["puzzle"]["themes"]} == set(MATE2["themes"])

def test_missed_puzzle_lowers_rating_without_xp(guest, puzzle_factory):
    r = finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, MISSED, NOW)
    assert not r["solved"] and r["rating"]["after"] < 1000 and r["xp"]["awarded"] == 0

def test_finish_is_idempotent(guest, puzzle_factory):                 # Review Focus 2
    a = serve(guest, puzzle_factory())
    assert finish_puzzle(guest, a.pk, SOLVED, NOW) == finish_puzzle(guest, a.pk, SOLVED, NOW + timedelta(seconds=2))
    assert XpEvent.objects.filter(learner=guest).count() == 1 and PuzzleRating.objects.get(learner=guest).rated_count == 1

def test_invalid_body_writes_nothing(guest, puzzle_factory):
    a = serve(guest, puzzle_factory())
    with pytest.raises(InvalidPuzzleResult):
        finish_puzzle(guest, a.pk, {**SOLVED, "played": [MATE2["illegal_first"]]}, NOW)
    a.refresh_from_db()
    assert a.finished_at is None and not PuzzleRating.objects.exists() and not XpEvent.objects.exists() and not Evidence.objects.exists()

def test_expired_attempt(guest, puzzle_factory):
    with pytest.raises(Expired):
        finish_puzzle(guest, serve(guest, puzzle_factory(), NOW - timedelta(hours=25)).pk, SOLVED, NOW)

def test_other_learner(guest, account, puzzle_factory):
    with pytest.raises(PuzzleAttempt.DoesNotExist):
        finish_puzzle(account.learner, serve(guest, puzzle_factory()).pk, SOLVED, NOW)

def test_idle_days_use_local_dates_and_grow_rd(puzzle_factory):      # Review Focus 3
    tz = "America/Montreal"
    a, b = Learner.objects.create(timezone=tz), Learner.objects.create(timezone=tz)
    late = datetime(2026, 11, 20, 4, 30, tzinfo=UTC)                  # 23:30 on 19 Nov in Montreal
    for learner in (a, b):
        finish_puzzle(learner, serve(learner, puzzle_factory(), late).pk, SOLVED, late)
    assert PuzzleRating.objects.get(learner=a).last_rated_on == date(2026, 11, 19)
    for learner, second in ((a, late + timedelta(minutes=40)), (b, late + timedelta(days=10))):
        finish_puzzle(learner, serve(learner, puzzle_factory(), second).pk, SOLVED, second)
    assert PuzzleRating.objects.get(learner=a).last_rated_on == date(2026, 11, 20)
    assert PuzzleRating.objects.get(learner=b).rd > PuzzleRating.objects.get(learner=a).rd

def test_deactivated_puzzle_can_still_be_finished(guest, puzzle_factory):   # Review Focus 4
    a = serve(guest, puzzle_factory())
    Puzzle.objects.filter(pk=a.puzzle_id).update(is_active=False)
    assert finish_puzzle(guest, a.pk, SOLVED, NOW)["solved"] is True

def test_start_level_only_matters_before_the_first_puzzle(guest, puzzle_factory):   # Review Focus 5
    first = finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert first["rating"]["before"] == 1000
    guest.start_level = "club"; guest.save()
    second = finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert second["rating"]["before"] == first["rating"]["after"]

def test_unrated_attempt_changes_nothing(guest, puzzle_factory):
    a = serve(guest, puzzle_factory()); PuzzleAttempt.objects.filter(pk=a.pk).update(rated=False)
    r = finish_puzzle(guest, a.pk, SOLVED, NOW)
    assert r["rating"]["change"] == 0 and r["xp"]["awarded"] == 0 and not Evidence.objects.exists()

def test_evidence_and_estimates_written(guest, puzzle_factory):
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    assert Evidence.objects.filter(learner=guest, area="tactics").count() == 1
    assert SkillEstimate.objects.get(learner=guest, kind="area", key="tactics").observations == 1

# tests/test_xp_rules.py
def test_puzzle_xp_rule():
    assert XpRules().puzzle_solved == 3 == XpRules.from_settings().puzzle_solved
```

- [ ] **Step 3: Run to verify they fail** — `docker compose run --rm test pytest tests/test_puzzle_finish.py tests/test_xp_rules.py -v` → FAIL
- [ ] **Step 4: Implement** the gamification changes (migration depends on `puzzles` 0001), `rating_view`, `Expired`, `finish_puzzle`.
- [ ] **Step 5: Run to verify they pass** — `docker compose run --rm test pytest tests/test_puzzle_finish.py tests/test_xp_rules.py tests/test_award.py tests/test_finish.py -v` → PASS
- [ ] **Step 6: Commit** — `git add config/settings.py gamification puzzles/services.py tests/puzzle_data.py tests/test_puzzle_finish.py tests/test_xp_rules.py && git commit -m "feat: puzzle finish with glicko-2 rating, xp and evidence"`

---

### Task 9: Puzzle API

**Files:**
- Create: `puzzles/api.py`, `puzzles/urls_api.py`, `tests/test_puzzle_api.py`
- Modify: `config/urls.py` (`path("api/v1/", include("puzzles.urls_api"))` next to the learning API), `locale/fr/LC_MESSAGES/django.po` + `.mo`

**Interfaces:**
- Consumes: `learning.api.BadRequest`, `json_error`, `_body`; `accounts.services.ensure_learner`; Tasks 7–8 services
- Produces:
  - `POST /api/v1/puzzles/next` (name `api_puzzle_next`), body `{"mode": "rated"|"theme", "theme"?: str, "difficulty"?: str, "timezone"?: str}` → 200 `{"attempt_id": str, "mode": str, "theme": str, "puzzle": {"fen": str, "moves": [str], "side": str}}`; creates the guest learner when needed (`ensure_learner(request, timezone=...)`). Errors: 400 `bad_request` ("Unknown mode, theme or difficulty."), 404 `no_puzzle` ("You've seen every puzzle here. Try another theme or difficulty."). This is a POST rather than §5.3's GET because it creates the attempt (and maybe a guest), so it must carry the CSRF token.
  - `POST /api/v1/puzzle-attempts/<uuid:attempt_id>/finish` (name `api_puzzle_finish`), body as Task 3 → 200 result; 404 `not_found` (no learner, unknown or another learner's attempt); 410 `expired` ("This puzzle was opened too long ago."); 400 `invalid_result` ("These moves don't match the puzzle.") or `bad_request` (body).
  - `POST /api/v1/puzzles/<str:lichess_id>/report` (name `api_puzzle_report`), body `{"reason": "wrong_solution"|"other", "note"?: str ≤ 500}` → 201 `{"reported": true}` the first time, 200 `{"reported": true}` after; 404 when the puzzle is unknown or the learner never attempted it; 400 for a bad reason or note.

- [ ] **Step 1: Write the failing tests**

```python
def test_next_creates_guest_and_returns_puzzle(client, puzzle_factory):
    p = puzzle_factory()
    r = client.post("/api/v1/puzzles/next", {"mode": "rated"}, content_type="application/json")
    assert r.status_code == 200 and client.session.get("learner_id")
    assert r.json()["puzzle"] == {"fen": p.fen, "moves": p.moves, "side": "white"}

def test_next_requires_csrf(puzzle_factory):
    puzzle_factory()
    r = Client(enforce_csrf_checks=True).post("/api/v1/puzzles/next", {"mode": "rated"}, content_type="application/json")
    assert r.status_code == 403

def test_next_errors(guest_client, puzzle_factory):
    client, _ = guest_client
    assert post(client, "/api/v1/puzzles/next", {"mode": "x"}).json()["error"]["code"] == "bad_request"
    r = post(client, "/api/v1/puzzles/next", {"mode": "rated"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_puzzle"

def test_finish_round_trip(guest_client, puzzle_factory):
    client, _ = guest_client
    puzzle_factory()
    attempt = post(client, "/api/v1/puzzles/next", {"mode": "rated"}).json()["attempt_id"]
    r = post(client, f"/api/v1/puzzle-attempts/{attempt}/finish", SOLVED)
    assert r.status_code == 200 and r.json()["solved"] is True

def test_finish_errors(guest_client, account, puzzle_factory):
    client, guest = guest_client
    a = serve(guest, puzzle_factory())
    assert post(client, f"/api/v1/puzzle-attempts/{a.pk}/finish", {**SOLVED, "played": ["a2a8"]}).status_code == 400
    assert not XpEvent.objects.exists()
    other = serve(account.learner, puzzle_factory())
    assert post(client, f"/api/v1/puzzle-attempts/{other.pk}/finish", SOLVED).status_code == 404
    old = serve(guest, puzzle_factory(), NOW - timedelta(hours=25))
    assert post(client, f"/api/v1/puzzle-attempts/{old.pk}/finish", SOLVED).status_code == 410
    r = client.post(f"/api/v1/puzzle-attempts/{a.pk}/finish", "x" * (64 * 1024 + 1), content_type="application/json")
    assert r.status_code == 400

def test_report_once(guest_client, puzzle_factory):
    client, guest = guest_client
    p = puzzle_factory(); serve(guest, p)
    url = f"/api/v1/puzzles/{p.lichess_id}/report"
    assert post(client, url, {"reason": "wrong_solution"}).status_code == 201
    assert post(client, url, {"reason": "other", "note": "?"}).status_code == 200 and PuzzleReport.objects.count() == 1
    assert post(client, url, {"reason": "nope"}).status_code == 400
    assert post(client, f"/api/v1/puzzles/{puzzle_factory().lichess_id}/report", {"reason": "other"}).status_code == 404
```

`post(client, url, data)` = `client.post(url, data, content_type="application/json")`; `SOLVED` and `serve` come from `tests/puzzle_data.py`.

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_puzzle_api.py -v` → FAIL
- [ ] **Step 3: Implement** the three views (`require_POST`, the learning API helpers), routes, French messages.
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_puzzle_api.py tests/test_api.py -v` → PASS
- [ ] **Step 5: Commit** — `git add config/urls.py puzzles/api.py puzzles/urls_api.py tests/test_puzzle_api.py locale/fr/LC_MESSAGES && git commit -m "feat: puzzle api"`

---

### Task 10: Guest merge, cleanup and deletion

**Files:**
- Modify: `puzzles/services.py` (`rebuild_rating`, `on_merge`), `puzzles/apps.py` (`ready`), `skills/services.py` (`on_merge`), `skills/apps.py` (`ready`)
- Create: `tests/test_puzzle_merge.py`

**Interfaces:**
- Consumes: `accounts.signals.merge_learners`; Task 2; Task 6 `recompute`; Task 7 `start_rating`
- Produces:
  - `puzzles.services.rebuild_rating(learner) -> PuzzleRating | None` — replays the learner's rated, finished attempts in `finished_at` order from `start_rating(learner)`, with the same idle-day rule and RD floor as `finish_puzzle`; writes the cache (counts, `last_rated_on`) or deletes it when there are none.
  - `puzzles.services.on_merge(sender, source, target, **kw)` — for each puzzle both learners have a rated attempt on, the later one (unfinished counts as later) gets `rated=False` first; then all source attempts move to the target; source reports move unless the target already reported that puzzle (then deleted); `rebuild_rating(target)`; source `PuzzleRating` deleted. XP events are left to gamification's receiver, unchanged.
  - `skills.services.on_merge(sender, source, target, **kw)` — moves evidence to the target; deletes puzzle evidence whose attempt is now unrated; for each lesson, keeps only the lesson evidence of the target's earliest finished attempt at it; deletes the source's estimates and history; `recompute(target, timezone.now())`.
  - Connected with `dispatch_uid="puzzles-merge"` and `"skills-merge"`. Receivers run in INSTALLED_APPS order (learning, gamification, puzzles, skills); skills must run after puzzles.

- [ ] **Step 1: Write the failing tests**

```python
def test_merge_moves_attempts_and_rebuilds_rating(guest, account, puzzle_factory):
    target = account.learner
    finish_puzzle(target, serve(target, puzzle_factory(rating=1000), T0).pk, MISSED, T0)
    for t in (T1, T2):
        finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000), t).pk, SOLVED, t)
    merge_learners.send(sender=Learner, source=guest, target=target)
    expected = rate(rate(rate(Rating(1000, 350, 0.06), [Game(1000, 80, 0)], 0.5), [Game(1000, 80, 1)], 0.5),
                    [Game(1000, 80, 1)], 0.5)
    pr = PuzzleRating.objects.get(learner=target)
    assert pr.rated_count == 3 and pr.rating == pytest.approx(expected.rating, abs=0.01)
    assert not PuzzleRating.objects.filter(learner=guest).exists()

def test_same_puzzle_is_rated_once(guest, account, puzzle_factory):
    target, p = account.learner, puzzle_factory()
    finish_puzzle(target, serve(target, p, T0).pk, SOLVED, T0)
    finish_puzzle(guest, serve(guest, p, T1).pk, MISSED, T1)
    merge_learners.send(sender=Learner, source=guest, target=target)
    assert list(PuzzleAttempt.objects.filter(learner=target, puzzle=p).order_by("served_at").values_list("rated", flat=True)) == [True, False]
    assert PuzzleRating.objects.get(learner=target).rated_count == 1
    assert Evidence.objects.filter(learner=target, source="puzzle").count() == 1

def test_lesson_evidence_kept_once(guest, account, lesson_factory, publish, valid_content):
    for step in valid_content["steps"]:
        step["skills"] = []
    lesson = lesson_factory("tac", kind="tactic")
    publish(lesson, valid_content)
    target = account.learner
    finish_attempt(target, start_attempt(target, lesson, T0).id, perfect_steps(), T0)
    finish_attempt(guest, start_attempt(guest, lesson, T1).id, perfect_steps(), T1)
    merge_learners.send(sender=Learner, source=guest, target=target)
    rows = Evidence.objects.filter(learner=target, source="lesson")
    assert rows.count() == 4
    assert set(rows.values_list("step_result__attempt__finished_at", flat=True)) == {T0}

def test_login_merges_puzzles(client, account, puzzle_factory):
    puzzle_factory()
    attempt = client.post("/api/v1/puzzles/next", {"mode": "rated"}, content_type="application/json").json()["attempt_id"]
    client.post(f"/api/v1/puzzle-attempts/{attempt}/finish", SOLVED, content_type="application/json")
    client.post("/login/", {"email": "farel@example.com", "password": "Chess-is-fun-42"})
    assert PuzzleAttempt.objects.get(pk=attempt).learner == account.learner
    assert account.learner.xp_events.filter(reason="puzzle").count() == 1

def test_idle_guest_cleanup_removes_puzzle_data(guest, puzzle_factory, settings):
    finish_puzzle(guest, serve(guest, puzzle_factory()).pk, SOLVED, NOW)
    Learner.objects.filter(pk=guest.pk).update(last_seen_at=NOW - timedelta(days=181))
    delete_idle_guests()
    assert not PuzzleAttempt.objects.exists() and not PuzzleRating.objects.exists() and not Evidence.objects.exists()
```

`T0, T1, T2 = (datetime(2026, 11, d, 12, tzinfo=UTC) for d in (18, 19, 20))`; `perfect_steps` from `tests.test_finish`; `delete_idle_guests` from `accounts.tasks`. The login form posts `email` and `password` (as in `tests/test_auth.py`).

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_puzzle_merge.py -v` → FAIL
- [ ] **Step 3: Implement** `rebuild_rating`, both receivers, the `ready()` hooks.
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_puzzle_merge.py tests/test_auth.py tests/test_learner.py -v` → PASS
- [ ] **Step 5: Commit** — `git add puzzles skills tests/test_puzzle_merge.py && git commit -m "feat: guest merge keeps puzzle rating and evidence"`

---

### Task 11: Train hub, puzzle page, replay, end-to-end tests

**Files:**
- Create: `puzzles/views.py`, `puzzles/urls.py`, `templates/puzzles/train.html`, `templates/puzzles/puzzles.html`, `templates/puzzles/replay.html`, `static/js/puzzles/main.js`, `static/js/puzzles/run.js`, `static/js/puzzles/ui.js`, `static/js/puzzles/replay.js`, `static/css/puzzles.css`, `tests/test_train_pages.py`, `e2e/test_puzzles.py`
- Modify: `config/urls.py` (`path("", include("puzzles.urls"))` before `learning.urls`), `templates/partials/nav.html` (Train), `e2e/conftest.py` (puzzle fixtures), `locale/fr/LC_MESSAGES/django.po` + `.mo`

**Interfaces:**
- Consumes: `static/js/player/board.js` (`createBoard`, `after`, `turnOf`), `static/js/player/san.js` (`localSan`), the Task 9 API, Task 8 `rating_view`, `skills.labels`
- Produces:
  - `/train/` (`train`): page title "Train"; a Puzzles card with the learner's rating range ("Your rating about 1250–1350", "still settling · 12 puzzles") or "Not rated yet", linking to `/train/puzzles/`.
  - `/train/puzzles/` (`puzzles`): the §5.2 layout: rating line; **Start puzzles** button; difficulty switch (Easier · Normal · Harder, `data-difficulty`, remembered in `localStorage` inside try/catch); theme picker (links `?theme=<key>`, grouped: Tactics `fork pin skewer discoveredAttack hangingPiece sacrifice`, Mates `mateIn1 mateIn2 mateIn3 backRankMate`, Calculation `long quietMove intermezzo`, Defence `defensiveMove`, Endgames `pawnEndgame rookEndgame`); the last 10 results (✓/✗ with `data-result="solved|missed"`); the board; coach line; Hint and Show solution buttons; result card; footer credit. Config (`json_script`): `nextUrl`, `finishUrl` ("/api/v1/puzzle-attempts/{id}/finish"), `reportUrl` ("/api/v1/puzzles/{id}/report"), `csrfToken`, `assets`, `lang`, `mode` ("theme" when `?theme=` is a key of `ALL_THEMES`, else "rated"), `theme`, `isGuest`, `signupUrl`, `i18n`.
  - `/train/puzzles/<str:lichess_id>/` (`puzzle_replay`): 404 unless the learner has an attempt on that puzzle; config carries `puzzle: {fen, moves, side}` and no API URLs; the board plays it with no rating.
  - `run.js`: `export async function runPuzzle(puzzle, ctx)` with `ctx = {board, ui, t, lang, onDecided(body)}`; returns `{solved: boolean}`. Behaviour: show `fen`, wait 500 ms, play `moves[0]` animated; then for each learner move: a move equal to the solution or giving checkmate (chess.js `isCheckmate()`) is correct; the opponent's reply follows after 400 ms; mate or the end of the solution ends the line. `onDecided` is called **exactly once**, at the first of: the line completed correctly; the first wrong move (body includes it); the first hint (before any marker is shown); Show solution. After a wrong move the coach says the missed sentence, the board shakes and resets, the learner can retry (after 2 wrong tries the right move is shown as an arrow and forced, as in lessons). Hint 1 marks the piece's square, hint 2 adds the arrow. Show solution plays the rest of the line.
  - `main.js`: loop — POST `nextUrl` (`{mode, theme, difficulty, timezone}`); 404 `no_puzzle` → show its message; `runPuzzle` with `onDecided = body => finishPromise = finish(attemptId, body)` (retries 1 s / 3 s / 9 s, then keeps the body in `localStorage` under `chessmind:pending-puzzle:<id>` and resends on the next visit, like the lesson player); after the line, await the result and show the card: Solved! / Missed, rating change (`+12`), new range, puzzle rating and theme labels, `+3 XP` when awarded, **Next puzzle** (primary, focused), **Report a problem** (two choices, then "Thanks, we'll check this puzzle."), "See the game on Lichess" link.
  - Copy (exact English; French in the `.po`): "White to play — find the best move." / "Black to play — find the best move."; "Not this time — this puzzle counts as missed. Keep going to learn the idea."; Hint button sub-text "counts the puzzle as missed"; "Show solution"; "Solved!"; "Missed"; "Next puzzle"; "Report a problem"; "The solution is wrong"; "Something else"; "Thanks, we'll check this puzzle."; "See the game on Lichess"; "Puzzle rating"; "still settling"; "Start puzzles"; "Train a theme"; "Easier", "Normal", "Harder"; page titles "Train" / "Puzzles" (French "S'entraîner" / "Problèmes").
  - Nav: a Train item between Learn and Analysis (`href="/train/"`, active for paths starting `/train/`), in the sidebar and the bottom bar.

- [ ] **Step 1: Write the failing page tests** in `tests/test_train_pages.py`

```python
def test_train_hub_renders_for_anyone(client):
    r = client.get("/train/")
    assert r.status_code == 200 and "/train/puzzles/" in r.content.decode()

def test_nav_has_train(guest_client):
    client, _ = guest_client
    assert 'href="/train/"' in client.get("/learn/").content.decode()

def test_puzzle_page_config_and_credit(client):
    page = client.get("/train/puzzles/?theme=fork")
    assert page.context["config"]["mode"] == "theme" and page.context["config"]["theme"] == "fork"
    assert client.get("/train/puzzles/?theme=nope").context["config"]["mode"] == "rated"
    assert "Puzzles from the Lichess puzzle database (CC0)" in page.content.decode()

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

def test_french(client):
    assert "Problèmes" in client.get("/train/puzzles/", HTTP_ACCEPT_LANGUAGE="fr").content.decode()
```

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_train_pages.py -v` → FAIL
- [ ] **Step 3: Implement** views, templates, nav, CSS (board full width on phones, controls ≥ 44 px), JS modules, French entries; `compilemessages`.
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_train_pages.py tests/test_pages.py -v` → PASS
- [ ] **Step 5: Write the end-to-end tests** in `e2e/test_puzzles.py` (phone viewport from `e2e/conftest.py`). Add fixtures `mate2_puzzle`, `alt_mate_puzzle`, `promotion_puzzle` to `e2e/conftest.py`: each takes `transactional_db` and `puzzle_factory` and creates exactly one active puzzle (`puzzle_factory(data=MATE2 / ALT_MATE / PROMOTION, rating=1000)`).

```python
def test_guest_solves_a_puzzle(page, live_server, mate2_puzzle):
    page.goto(live_server.url + "/train/puzzles/")
    page.get_by_role("button", name="Start puzzles").click()
    play(page, "a2e6"); play(page, "f7f8")
    expect(page.get_by_text("Solved!")).to_be_visible()
    expect(page.get_by_text("+3 XP")).to_be_visible()
    page.goto(live_server.url + "/profile/?tab=skills")
    expect(page.get_by_text("not enough evidence yet").first).to_be_visible()

def test_wrong_move_counts_as_missed(page, live_server, mate2_puzzle):
    page.goto(live_server.url + "/train/puzzles/")
    page.get_by_role("button", name="Start puzzles").click()
    play(page, MATE2["wrong_first"])
    expect(page.get_by_text("this puzzle counts as missed")).to_be_visible()
    page.get_by_role("button", name="Show solution").click()
    expect(page.get_by_text("Missed", exact=True)).to_be_visible()

def test_promotion_puzzle(page, live_server, promotion_puzzle):
    page.goto(live_server.url + "/train/puzzles/")
    page.get_by_role("button", name="Start puzzles").click()
    play(page, "g7g8")
    page.locator('#board [data-piece="wq"]').first.click()
    expect(page.get_by_text("Solved!")).to_be_visible()

def test_alternative_mate(page, live_server, alt_mate_puzzle):
    page.goto(live_server.url + "/train/puzzles/")
    page.get_by_role("button", name="Start puzzles").click()
    play(page, ALT_MATE["alternative"])
    expect(page.get_by_text("Solved!")).to_be_visible()
```

`play` waits for `#board[data-input="on"]` and clicks the two squares, as in `e2e/test_player.py` (import it from there or copy it). The Skills tab assertion in the first test passes only after Task 12; until then mark it `xfail(strict=True)` and remove the mark in Task 12.

- [ ] **Step 6: Run the end-to-end tests** — `docker compose --profile e2e run --rm e2e` → all pass (the skills assertion xfails as planned)
- [ ] **Step 7: Commit** — `git add config/urls.py puzzles templates/puzzles templates/partials/nav.html static/js/puzzles static/css/puzzles.css e2e tests/test_train_pages.py locale/fr/LC_MESSAGES && git commit -m "feat: train hub and puzzle player"`

---

### Task 12: Skills tab and area detail

**Files:**
- Create: `skills/views.py`, `skills/urls.py`, `templates/skills/area.html`, `tests/test_skills_pages.py`
- Modify: `skills/services.py` (`overview`, `area_detail`), `learning/views.py` (`PROFILE_TABS = ("performance", "mastery", "skills", "settings")`, context), `templates/learning/profile.html` (Skills tab), `config/urls.py` (`path("", include("skills.urls"))` before `learning.urls`), `e2e/test_puzzles.py` (drop the xfail), `locale/fr/LC_MESSAGES/django.po` + `.mo`

**Interfaces:**
- Consumes: Task 6 models, Task 8 `rating_view`, `current_rating`, Task 4 sets and labels
- Produces:
  - `skills.services.AreaRow` frozen dataclass: `key, label, basis, low, high, percent (lesson basis: round(value × 100), else None), observations, confidence, comparison, status`
  - `skills.services.overview(learner) -> dict` = `{"rating": rating_view(...) | None, "rated_count": int, "areas": list[AreaRow]}` — nine rows in `AREAS` order; an area without a `SkillEstimate` row is basis "none"
  - `skills.services.area_detail(learner, area: str) -> dict` = `{"area": AreaRow, "themes": list[AreaRow], "sources": {"puzzle": int, "lesson": int}, "recent": list[dict]}` — themes: the learner's theme estimates for this area's themes (tactics → `TACTICS_THEMES`, calculation → `PUZZLE_AREA_THEMES["calculation"] & MOTIF_THEMES`, defense → `{"defensiveMove"}`, endgames → `ENDGAME_TYPES | {"zugzwang"}`, other areas → none); recent: the area's last 20 evidence rows as `{"date", "success", "source", "label", "url"}` (puzzle → `/train/puzzles/<id>/`, label "Puzzle · " followed by the puzzle's rating, plus theme labels; lesson → `/lessons/<slug>/`, label the lesson title); unknown area → `KeyError`
  - `/profile/skills/<str:area>/` (`skill_area`): redirect to `/start/` without a learner; 404 for an unknown area
  - Copy (exact English): status — confirmed_weakness "Weakness", emerging_weakness "Weakness forming", improving "Improving", stable_strength "Strength"; comparison — "stronger than your usual level", "about your level", "weaker than your usual level"; confidence — "not enough evidence yet", "early estimate", "reliable"; counts — ngettext "%(n)s puzzle"/"%(n)s puzzles", "%(n)s lesson answer"/"%(n)s lesson answers"; range — "about %(low)s–%(high)s"; detail sources — "From %(p)s puzzles and %(l)s lesson answers."; empty state — "We're still learning how you play. Solve a few puzzles or finish a lesson to see your skills."; puzzle rating line — "Puzzle rating about %(low)s–%(high)s". `repeated_mistake` is never rendered.

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_state(guest_client):
    client, _ = guest_client
    assert "We're still learning how you play." in client.get("/profile/?tab=skills").content.decode()

def test_nine_areas_and_wording(guest_client, puzzle_factory):
    client, guest = guest_client
    for i in range(12):
        finish_puzzle(guest, serve(guest, puzzle_factory(rating=1000)).pk, MISSED if i % 6 else SOLVED, NOW)
    html = client.get("/profile/?tab=skills").content.decode()
    assert html.count("data-area=") == 9 and "12 puzzles" in html and "early estimate" in html
    est = SkillEstimate.objects.get(learner=guest, kind="area", key="tactics")
    assert f"about {est.low}–{est.high}" in html
    if round(est.value) % 50:                  # the exact estimate never appears, only the rounded range
        assert str(round(est.value)) not in html

def test_area_detail(guest_client, puzzle_factory):
    client, guest = guest_client
    for _ in range(25):
        finish_puzzle(guest, serve(guest, puzzle_factory(themes=["fork", "short"])).pk, MISSED, NOW)
    r = client.get("/profile/skills/tactics/")
    assert r.status_code == 200 and len(r.context["detail"]["recent"]) == 20
    assert [t.key for t in r.context["detail"]["themes"]] == ["fork"]
    assert "/train/puzzles/" in r.content.decode()

def test_unknown_area_404_and_no_repeated_mistake_text(guest_client):
    client, _ = guest_client
    assert client.get("/profile/skills/chess/").status_code == 404
    assert "repeated" not in client.get("/profile/skills/tactics/").content.decode().lower()

def test_skills_tab_in_french(guest_client):
    client, guest = guest_client
    guest.language = "fr"; guest.save()
    assert "Nous apprenons encore" in client.get("/profile/?tab=skills").content.decode()
```

(The French empty state starts "Nous apprenons encore comment vous jouez." — put exactly that in the `.po`.)

- [ ] **Step 2: Run to verify they fail** — `docker compose run --rm test pytest tests/test_skills_pages.py -v` → FAIL
- [ ] **Step 3: Implement** the services, view, templates (each area row a `cm-row` with `data-area`, linking to its detail when the area has any evidence), French entries, `compilemessages`; remove the xfail in `e2e/test_puzzles.py`.
- [ ] **Step 4: Run to verify they pass** — `docker compose run --rm test pytest tests/test_skills_pages.py tests/test_path_profile.py -v` → PASS, then `docker compose --profile e2e run --rm e2e` → PASS
- [ ] **Step 5: Commit** — `git add skills learning/views.py templates/learning/profile.html templates/skills config/urls.py e2e/test_puzzles.py tests/test_skills_pages.py locale/fr/LC_MESSAGES && git commit -m "feat: skills tab and skill area detail"`

---

### Task 13: Milestone check

**Files:**
- Modify: `README.md` only if a step below shows a gap.

- [ ] **Step 1: Full test suite** — `docker compose run --rm test pytest` → all pass; `docker compose --profile e2e run --rm e2e` → all pass.
- [ ] **Step 2: Real import.** Download `https://database.lichess.org/lichess_db_puzzle.csv.zst` into the project folder (do not commit it; add it to `.gitignore` if it isn't covered), run `docker compose run --rm -v "$PWD:/data" web python manage.py import_puzzles /data/lichess_db_puzzle.csv.zst`. Expected: 24 band lines from 400 to 2700, each at or near 2,000, total about 48,000. If a band is short, rerun with looser `--min-plays` / `--min-popularity` and note the values used in the README.
- [ ] **Step 3: Backfill** — `docker compose run --rm web python manage.py backfill_evidence` → prints the rows created; the three seed lessons' earlier attempts now give tactics/defense evidence.
- [ ] **Step 4: On a phone-sized browser window (390 px):** as a new guest open Train → Puzzles, solve and miss a few, use a hint once (the button warns first), check the rating range moves and reads "still settling"; try a theme; open Profile → Skills and an area's detail; switch to French and check the pages. Sign up and confirm the puzzle rating and Skills tab survive.
- [ ] **Step 5: Commit** any README fix — `git add README.md && git commit -m "docs: puzzle import notes"`
