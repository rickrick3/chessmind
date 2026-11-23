# ChessMind · Project 1 — Puzzles and the skill profile: Design

**Date:** 2026-11-22 · **Status:** approved by Farel on 2026-11-22
**Inputs:** ChessMind PRD v1.0 and UX and Interaction Specification v1.0 (both given by Farel on 2026-11-22),
the milestone 1 code on branch `chessmind-foundation`, and the earlier design (https://claude.ai/artifact/DboSaF5t4A3pQ3Hrachk2j).

---

## 1. Why

Farel wants ChessMind to feel like a full chess school, not three lessons. The PRD makes an **adaptive coach** the centre
of the product: it keeps an evidence-backed profile of the player's skills and recommends what to practise next.

A coach can only adapt to evidence. Today the only evidence is the step results of three lessons. Puzzles fix that cheaply:
Lichess publishes millions of rated, themed puzzles under CC0, so learners from beginner to advanced get something to solve
from day one, and every puzzle they solve or miss becomes evidence about a specific skill.

This project builds the puzzles and the **skill profile** (the player model's evidence, estimates, confidence, strengths and
weaknesses). The next project builds the coach that reads it (recommendations, onboarding, dashboard).

### Where this sits (the five projects Farel agreed on 2026-11-22)

Scope is "the PRD and UX spec, plus puzzles"; the adaptive bot and Lichess import stay deferred.

1. **Puzzles and the skill profile** — this document.
2. Coach: onboarding, dashboard, recommendations (accept / postpone / reject), Coach tab. The visual direction (UX spec §7:
   minimal, dark-first) is settled with mockups before this project, because it adds most of the new screens.
3. Game review: 10 games per page with filters, PGN upload, verified Chess.com link; game evidence feeds the profile.
4. Opening laboratory.
5. Endgame laboratory.

Alongside: email verification, lesson rollback, more lessons through the content pipeline.

## 2. Goals, non-goals, anti-goals

**Goals**
- A learner at any level opens **Train → Puzzles** and gets puzzles at their level, on a phone, as a guest or with an account.
- A puzzle rating that adapts after every puzzle, checked by the server.
- Theme training: pick a theme (forks, pins, mates in 2…) and get puzzles of that theme at your level.
- An append-only **evidence ledger**: every puzzle result and every scored lesson step, tagged with the skill areas it shows.
- A **skill estimate per skill area** with its confidence and the evidence behind it, recomputed from the ledger.
- **Strengths and weaknesses** that follow the PRD's diagnosis states, never from a single error.
- A **Skills** tab on the profile that shows all of this in plain words, including "not enough evidence yet".

**Non-goals (this project)**
- Recommendations, onboarding, dashboard, Coach tab (project 2).
- Evidence from games (project 3); opening and endgame laboratories (projects 4–5).
- Puzzle racing, timed modes, leaderboards, puzzle streak modes, daily puzzle.
- Updating puzzle ratings from our learners' results (puzzle ratings stay as Lichess published them).
- A new visual design; this project uses the current ChessMind design system.

**Anti-goals (a failure even if it works)**
- One missed puzzle shown as a weakness.
- A skill shown as a precise number ("Calculation: 1437") or a claim of mastery without evidence.
- A learner who can't tell why the profile says what it says.
- Any learner request that calls Lichess, Stockfish or Gemini.
- Learners stuck on puzzles far too hard (or trivially easy) for their level after the first dozen puzzles.

## 3. Constraints

- Stack and rules from milestone 1 stay: Django pages plus the one JS player (cm-chessboard + chess.js), no SPA, no DRF,
  Postgres, Celery for background work, French and English everywhere, phones first (390 px, 44 px targets).
- The browser checks moves instantly; the **server re-scores** every submission before any rating, XP or evidence is written.
  A garbled or hostile body answers 400 and writes nothing. A repeated finish returns the stored result.
- Hosting is Oracle Cloud Always Free (2 OCPU / 12 GB in total). The puzzle catalogue must stay small and the next-puzzle
  query cheap.
- No learner request calls Lichess, Stockfish or Gemini (unchanged rule).
- Licensing: the Lichess puzzle database is released under **CC0** ("Database exports are released under the Creative
  Commons CC0 license", database.lichess.org). No attribution is required; we credit it anyway.

## 4. Approaches

Every approach keeps the evidence ledger (the PRD requires evidence behind each estimate, and diagnosis needs to count
observations over time). They differ in how evidence becomes an estimate.

1. **One puzzle rating; per-area estimates computed from the evidence — chosen.** One Glicko-2 rating picks puzzles at the
   learner's level. Each skill area's estimate is recomputed from that area's own recent evidence, so every number can be
   explained ("from your last 34 calculation puzzles") and rebuilt from the ledger at any time.
2. *A Glicko-2 rating per skill area, updated live.* Confidence comes built in, but the numbers drift and are hard to trace
   back to evidence; a puzzle tagged with three areas moves three ratings; changing the theme mapping means replaying
   everything.
3. *Knowledge tracing (probability of knowing each concept).* The textbook model for lessons, but it needs tuned parameters
   per concept that we don't have and ignores puzzle difficulty.

Farel said "proceed" on the plan; approach 1 is Claude's pick and stands unless he objects.

## 5. Design

### 5.1 The puzzle catalogue

**Source.** `https://database.lichess.org/lichess_db_puzzle.csv.zst` — 6,193,530 puzzles (file of 2026-11-11). Columns:
`PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags, DailyDate`.
`FEN` is the position *before the opponent's move*; the first move in `Moves` (UCI) is the opponent's, the second starts the
solution. Popularity runs from −100 to 100. All player moves are "only moves", except that **any checkmating move wins**.

**Import.** A staff management command, `import_puzzles <file> [--per-band N]`, run once on the server (and again to refresh):
- reads the `.zst` file directly (new dependency `zstandard`, used only by this command) or a plain `.csv`;
- keeps puzzles with a stable rating and good reception (starting point: `Popularity ≥ 80`, `NbPlays ≥ 300`,
  `RatingDeviation ≤ 90`; thresholds are options so low-rated bands can be loosened if they come out thin);
- replays every move with python-chess and skips any row whose moves are not legal;
- takes up to **2,000 puzzles per 100-point band from 400 to 2,800** (about 48,000 in all), with a deterministic sample
  (fixed seed), so a rerun on the same file gives the same set;
- upserts by Lichess id. Puzzles are never deleted while attempts point at them; a puzzle that leaves the set is deactivated.

**Stored per puzzle:** Lichess id, FEN, moves, rating, rating deviation, popularity, plays, themes, opening tags, game URL,
active flag, import date. Derived at import for convenience: the learner's side and the starting position after the
opponent's first move.

**Review.** Puzzles are not AI-generated and are not lessons, so they do not go through the studio. The staff import is the
review step (staff chooses the file and filters); legality is checked by our code; Lichess's solutions are engine-checked and
the play-count filter keeps only puzzles many players have solved. Learners can **report a puzzle** ("wrong solution",
"other"); reports appear in the Django admin, where staff deactivate a puzzle. *(Decided by Farel on 2026-11-22: the
staff import counts as the review for PRD acceptance criterion 11; puzzles are not reviewed one by one.)*

**Credit.** The puzzle page footer and the README say "Puzzles from the Lichess puzzle database (CC0)".

### 5.2 Playing a puzzle

**Train hub (`/train/`).** A new **Train** item in the sidebar and the bottom bar (Learn · Train · Analysis · Profile). The
page has a Puzzles card; Openings and Endgames cards arrive with projects 4–5.

**Puzzles page (`/train/puzzles/`).**

```
┌──────────────────────────────┐
│ Puzzles                      │
│ Your rating  about 1250–1350 │
│ still settling · 12 puzzles  │
│ [ Start puzzles ]   (primary)│
│ Difficulty: Easier·Normal·Harder
│ Train a theme                │
│  Tactics:  Fork  Pin  Skewer │
│            Discovered attack │
│  Mates:    Mate in 1  in 2   │
│  Calculation: Long  Quiet move│
│  Defence:  Defensive move    │
│  Endgames: Pawn  Rook        │
│ Recent   ✓ ✓ ✗ ✓ ✗ ✓ …       │
└──────────────────────────────┘
```

**Choosing the next puzzle (server).** An active puzzle this learner has never been served, within a rating window around
the target, widening (±100, ±200, ±400, ±600) until one is found; in theme mode the theme must match. Target = learner rating
+ offset: Easier −300, **Normal −100** (default; roughly two puzzles in three solved), Harder +200. If the learner already
has an open attempt (served, not finished, under 24 h old) in the same mode, that one is served again, so refreshing does not
skip a puzzle.

**On the board.** The board shows the position before the opponent's move, plays the opponent's move with animation, then
the learner moves (board turned to the learner's side). Each correct move is answered by the opponent's reply from the
solution until the solution ends. **Any checkmating move solves the puzzle at once.** Promotions use the player's promotion
picker.

**Missing.** A wrong move, a hint, or "Show solution" makes the puzzle **missed** for rating purposes, and the screen says so
plainly ("Not this time — this puzzle counts as missed. Keep going to learn the idea."). The learner can still retry the move
or watch the solution; nothing after that point is rated. The Hint button says before use that it counts the puzzle as missed.
Hint 1 highlights the piece to move, hint 2 the target square.

**When the outcome is decided** (solved, or the first wrong move / hint / show solution), the browser sends the finish call
immediately; the server re-scores and returns the result. Closing the tab after a wrong move therefore does not avoid the loss.

**Result card:** Solved / Missed, the rating change (e.g. +12), the puzzle's rating and its themes (shown only now — they would
give the answer away), XP earned, **Next puzzle** (primary), **Report a problem**, and a link to the source game on Lichess.

**Opened and left alone:** served again for 24 h; after that the attempt expires with no rating change and the puzzle is not
served again.

**Reuse.** The puzzle board reuses the lesson player's modules — a puzzle is a `play_line` with opponent replies — in a
puzzle mode with its own chrome (no step progress bar, puzzle result card, checkmate ends the line).

### 5.3 Server checks and API

Same conventions as milestone 1 (JSON errors `{"error": {"code", "message"}}`, CSRF on every POST, another learner's object
answers 404, attempts are UUIDs used as idempotency keys).

- `GET /api/v1/puzzles/next?mode=rated|theme&theme=<key>&difficulty=easier|normal|harder` →
  `{attempt_id, puzzle: {fen, moves, side}}`. Theme mode is rated too. Sending the solution to
  the browser is what gives instant feedback; a learner who reads it only fools their own rating (same trade-off as lessons).
- `POST /api/v1/puzzle-attempts/<id>/finish` with `{tries: [[uci, …] per learner move reached], hints: n, solution_shown: bool,
  ms}`. The server replays from the puzzle's position: **solved** requires every learner move to be the solution move or a
  checkmate, with no hint and no solution shown; **missed** requires a correct prefix ending in one legal wrong move, or a hint /
  solution flag. Anything else (illegal move, moves past the end, shape errors, sizes over the lesson limits) → 400, nothing
  written. Expired attempt → 410. A repeat call returns the stored result with 200.
- The response: `{solved, rating: {before, after, change, range, settling}, xp, streak, daily_goal, achievements,
  puzzle: {rating, themes, game_url}}`.
- Only the **first attempt of a puzzle by a learner is rated** (served puzzles are never served again in normal use, so this
  only matters after a guest merge, §5.9).
- `POST /api/v1/puzzles/<id>/report` with `{reason, note}` — one report per learner per puzzle.

### 5.4 The puzzle rating

- **Glicko-2**, one rated "game" per attempt between the learner and the puzzle, using the puzzle's Lichess rating and rating
  deviation; the puzzle's numbers never change.
- **Start** from the learner's start level: `new` 700, `rules` 1000, `club` 1500, none chosen 1000; deviation 350,
  volatility 0.06. Deviation floor 45. Deviation grows back with inactivity, as Glicko-2 does between rating periods (one period
  per day without puzzles).
- Stored as a cache (rating, deviation, volatility, counts, last date) next to the learner; the **ordered attempts are the
  truth**, and one function rebuilds the cache from them (used by guest merge and tests).
- **Shown as a range, not a number:** rating ± deviation, rounded to 50 ("about 1250–1350"), with "still settling" while the
  deviation is above 110.

### 5.5 The evidence ledger

One row per (observation, skill area): learner, area, source (`puzzle` or `lesson`; `game` arrives in project 3), link to
the puzzle attempt or the lesson step result, success (true/false), difficulty (the puzzle's rating; null for lessons),
tags (the puzzle's themes or the step's skill tags), the learner's local date, created at. Append-only, unique per
(source object, area), deleted with the learner.

- **Puzzle evidence:** written by the finish call, in the same transaction as the rating and XP.
- **Lesson evidence:** written by the lesson finish call for each scored step; success = correct on the first try with no
  hint. **Only the learner's first finished attempt at a lesson gives evidence**; replays don't, because their answers are
  remembered rather than found. A one-off backfill creates evidence for step results recorded before this project, with the
  same first-attempt rule.

### 5.6 Skill areas and what feeds them

The PRD's nine domains, with these keys: `tactics`, `calculation`, `openings`, `positional`, `strategy`, `endgames`,
`defense`, `decisions`, `time`.

| Area | Puzzle evidence (Lichess themes) | Lesson evidence |
|---|---|---|
| tactics | every puzzle | steps tagged with a tactics theme; untagged steps of `tactic` lessons |
| calculation | `long`, `veryLong`, `mateIn3`, `mateIn4`, `mateIn5`, `intermezzo`, `quietMove` | steps tagged `calculation` or one of those themes |
| defense | `defensiveMove`, `equality` | tagged `defense` |
| endgames | `endgame` and every `…Endgame` theme, `zugzwang` | tagged `endgames`; untagged steps of `endgame` lessons |
| openings | — | tagged `openings`; untagged steps of `opening` lessons |
| positional, strategy, decisions, time | — | tagged with the area key |

Lesson step `skills` tags come from one fixed vocabulary: the nine area keys plus the Lichess theme keys. "A tactics theme"
means any Lichess theme in the tactics row's motif list (§5.8), mates included (`mate`, `mateIn1`…`mateIn5` and the named
mate patterns).

**Existing tags.** The milestone 1 seed lessons use their own tags, and each old step result keeps a copy of them. An
**alias table** in code maps them, and is applied wherever tags are read (scoring, backfill, validation):
`defence`, `threats`, `defenders` → `defense`; `back-rank` → `backRankMate`; `smothered` → `smotheredMate`;
`cct`, `checks`, `captures` → `tactics`; `piece-values`, `trades`, `queen` → no area. The seed lessons are not retagged in
this project (that would mean new versions through review); new lessons use the vocabulary directly.

Lesson validation **warns** on a tag that is neither in the vocabulary nor an alias. A step whose tags all map to no area
counts as untagged and falls back to its lesson's kind. Untagged steps of `concept` lessons give no evidence. Areas with no evidence source yet show
"not enough evidence yet" — that is the honest answer until projects 3–5 add games and laboratories.

Endgame puzzles show tactics in endgame positions, not endgame technique; the area's detail says where its evidence came from
("from 18 endgame puzzles") so the learner isn't misled.

### 5.7 Skill estimates and confidence

Recomputed for the learner's areas (and their puzzle themes) after every finish, stored as the current estimate, plus one
history row per area per local day for later charts (PRD FR-020).

- **Puzzle-based estimate** (areas and themes with puzzle evidence): the performance rating over the **last 40** puzzle
  observations in that area — the rating at which the expected score against those puzzles equals the learner's actual
  score (maximum likelihood, bounded when everything was solved or everything missed) — with a margin that shrinks with the
  number of observations. Shown as a range and compared with the overall puzzle rating: *stronger than your usual level*,
  *about your level*, *weaker than your usual level* (only when the gap exceeds the margin).
- **Lesson-based estimate:** first-try success rate over the last 30 lesson observations.
- **Which estimate an area shows.** Puzzle and lesson evidence are never mixed into one number, because lesson steps have no
  rating. An area with **10 or more puzzle observations** shows the puzzle-based estimate, and its confidence counts puzzles
  only. Otherwise, an area with 10 or more lesson observations shows the lesson-based estimate, counting lesson answers
  only. Otherwise it shows *not enough evidence yet*. The other kind of evidence still appears in the area's detail as
  supporting evidence. The wording names what was counted: "14 puzzles" or "12 lesson answers".
- **Confidence** (of the estimate shown, counting its own kind of evidence):
  - under 10 observations → *not enough evidence yet* (no estimate shown);
  - 10 to 24, or all on fewer than 3 different days → *early estimate*;
  - 25 or more over at least 3 days → *reliable*.

### 5.8 Strengths and weaknesses (PRD §5.2)

Computed with the estimates, at area level and theme level (so the coach can later say "pins", not just "tactics").

**Themes that can be diagnosed** are the motif themes only: the named tactics (`fork`, `pin`, `skewer`, `discoveredAttack`,
`discoveredCheck`, `doubleCheck`, `hangingPiece`, `trappedPiece`, `deflection`, `attraction`, `clearance`, `interference`,
`xRayAttack`, `capturingDefender`, `sacrifice`, `intermezzo`, `quietMove`, `zugzwang`, `defensiveMove`, `attackingF2F7`,
`exposedKing`, `promotion`, `underPromotion`, `advancedPawn`), the mates (`mate`, `mateIn1`…`mateIn5`, every named mate
pattern) and the endgame types (`pawnEndgame`, `rookEndgame`, …). Phase, length, evaluation and source themes (`opening`,
`middlegame`, `endgame`, `oneMove`, `short`, `long`, `veryLong`, `advantage`, `crushing`, `equality`, `master`,
`masterVsMaster`, `superGM`) only feed areas through §5.6 and are never diagnosed on their own.

| State | Rule (starting values; all thresholds are settings) |
|---|---|
| Isolated error | any single miss — never shown as a weakness |
| Repeated mistake | the same motif theme missed 3 or more times within 14 days **on puzzles rated at or below the learner's rating at the time** (ones they were expected to solve). Stored for the coach (project 2); **not shown on the Skills tab** |
| Emerging weakness | estimate below the overall rating by more than the margin, *early estimate* confidence |
| Confirmed weakness | the same with *reliable* confidence |
| Improving | the latest 15 observations perform at least 100 points above the 15 before (30+ observations) |
| Stable strength | estimate above the overall rating by more than the margin, *reliable* confidence |

For lesson-only areas the same states use success rate (weakness under 50 %, strength over 85 %, same confidence rules).

### 5.9 Guests and merging

When a guest logs into an account (milestone 1's merge signal): puzzle attempts, evidence and XP events move to the account;
if both did the same puzzle, the earlier attempt stays rated and the later becomes unrated; the puzzle rating is **rebuilt by
replaying all attempts in time order** from the account's start level; estimates are recomputed.

### 5.10 XP, streak, achievements

- Solved puzzle: **3 XP**; missed: 0. Only rated (first) attempts earn XP. Amounts are settings.
- Puzzle XP counts for the streak and the daily goal like any XP (new XP reason `puzzle`, one per attempt).
- No new achievements in this project.

### 5.11 Skills tab on the profile

Profile tabs become Performance · Mastery · **Skills** · Settings.

```
┌──────────────────────────────┐
│ Skills                       │
│ Puzzle rating about 1250–1350│
│ ─────────────────────────────│
│ Tactics        about your level
│   reliable · 64 puzzles      │ >
│ Calculation    weaker than usual
│   early estimate · 14 puzzles│ >
│ Defence        not enough evidence yet
│ Endgames       stronger than usual
│   early estimate · 18 puzzles│ >
│ Openings       not enough evidence yet
│ …                            │
└──────────────────────────────┘
```

Tapping an area opens its detail: the estimate range and confidence, its strengths and weaknesses by theme, where the
evidence came from (puzzles, lessons), and the last 20 observations (each puzzle links to an unrated replay, each lesson
step to its lesson). With no evidence at all the tab shows the UX spec's empty state: "We're still learning how you play.
Solve a few puzzles or finish a lesson to see your skills."

### 5.12 Languages, privacy, performance

- Every new UI string in French and English (`.po` and `.mo` together). Theme names get our own French and English labels
  for the themes we show (we don't copy translation files from the Lichess project). Moves use French piece letters in `fr`.
- Account deletion and the 180-day guest cleanup remove attempts, evidence, estimates and reports with the learner.
- The next-puzzle query uses an index on (active, rating), an index on themes, and a unique (learner, puzzle) attempt index
  for the "never served" check; with about 48,000 puzzles it stays in milliseconds.

## 6. Testing focus

1. Glicko-2 matches the worked example in Glickman's Glicko-2 paper (1500/200/0.06 against three opponents →
   about 1464.06 / 151.52 / 0.05999).
2. Finish re-scoring: a solved line; an alternative checkmate accepted at any learner move; a wrong move → missed; a hint or
   solution flag → missed; an illegal move, moves past the end or a bad shape → 400 with nothing written; a repeat call →
   the same result and no second XP row; an expired attempt → 410.
3. Next puzzle never repeats a served puzzle; an open attempt is served again after a refresh; theme mode only gives that
   theme; the window widens when the band is empty.
4. One missed puzzle never produces a weakness; *reliable* needs 25 observations over 3 days; the diagnosis table's rules,
   each at its boundary.
5. Guest merge: rating rebuilt from both histories in time order; a puzzle done by both is rated once.
6. Import: deterministic sample; illegal rows skipped; rerun is idempotent; deactivation instead of deletion.
7. End to end on a phone-sized browser: a guest solves a puzzle (including a promotion puzzle), sees the rating move, and
   finds the Skills tab.

## 7. Decisions

**Decided by Farel**
- Scope: PRD + UX spec + puzzles; adaptive bot and Lichess import deferred (2026-11-22).
- The five-project order above, starting with this one ("proceed", 2026-11-22).
- **Puzzle review (2026-11-22):** the staff import counts as the review; no per-puzzle human review. Legality checks,
  learner reports and deactivation in the admin cover bad puzzles.
- Still standing from milestone 1: Django pages + one JS player, no SPA/DRF, guests and accounts, French and English,
  server-side scoring, published lessons only after human review.

**Claude's calls (please check)**
1. Approach 1: one puzzle rating, estimates computed from evidence.
2. About 48,000 puzzles, 2,000 per 100-point band from 400 to 2,800, with quality filters.
3. Start ratings by level (700 / 1000 / 1500), difficulty offsets (−300 / −100 / +200), Normal as default.
4. A wrong move, hint or shown solution = missed; the outcome is sent the moment it is decided.
5. 3 XP per solved puzzle, 0 for a miss.
6. The skill-area keys, the theme mapping and the confidence thresholds (10 / 25 observations, 3 days).
7. A Train tab now (UX spec puts puzzles' siblings, the laboratories, under Train).
8. Current look kept for this project; the visual direction is settled before project 2.
9. One new dependency, `zstandard`, for the import command only.
10. Puzzles reuse the lesson player's `play_line` machinery (puzzles have opponent replies, so `find_move` doesn't fit).
11. Old seed-lesson tags are mapped by an alias table instead of retagging the lessons.
12. Only a learner's first finished attempt at a lesson gives evidence.
13. Puzzle and lesson evidence are never mixed into one estimate; 10 puzzle observations switch an area to the puzzle-based
    estimate.
14. Only motif themes are diagnosed; "repeated mistake" counts only misses on puzzles at or below the learner's rating and
    is kept for the coach, not shown to the learner.

## 8. Left to the builder

- Model and field names, indexes, and whether tags are an array field or a join table.
- The exact import thresholds per band, as long as every band from 400 to 2,800 ends up with puzzles.
- Glicko-2 τ (system constant) and the inactivity formula, within standard Glicko-2.
- The performance-rating solver and the margin formula, within §5.7's intent.
- Layout details inside the current design system; the theme list shown on the Puzzles page (about 15–20 themes).
- How the backfill of old lesson step results runs (data migration or command).
- The uniqueness constraints around attempts (merged duplicates and unrated replays need a partial unique index or
  similar), and the order of the merge receivers relative to the XP cache rebuild.
- An unrated replay of a puzzle (from the Skills detail) writes nothing.

## 9. Changes after the final review (2026-11-23)

- **§5.7 comparison.** An area or theme is compared with the learner's own puzzle rating *at the time* of the
  observations in its window (the average of the ratings recorded with them), not with today's rating; otherwise
  every improving learner's older evidence reads as a weakness. Falls back to the overall rating when none was recorded.
- **§5.7–5.8 thresholds.** "Stronger" / "weaker" need a gap of two margins (about two standard errors); the shown
  range stays ± one margin. "Improving" needs 250 points between the two 15-puzzle halves (lesson basis: +35 points
  of success rate). The old values let ordinary noise produce labels.
- **§5.1 review.** A puzzle staff turn off (admin action, or from a report) is flagged `disabled_by_staff`; a re-import
  never turns it back on. Staff can turn it back on in the admin.
- **§5.9 merge.** The puzzle rating cache records the rating it started from; a merge rebuilds from the account's
  start (or the guest's, when only the guest had a rating), never from a start level the account adopts in the merge.
- **§5.2 play.** An outcome is kept on the device before it is first sent and must be delivered before another
  puzzle is requested; when a mode has no puzzle left, the page returns to the start panel with the message.
