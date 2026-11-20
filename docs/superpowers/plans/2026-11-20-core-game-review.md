# Chess Coach: Core Game Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A player types a Chess.com username, picks a recent game, and gets every move graded and explained in French or English on a board, at $0 running cost.

**Architecture:** One Django project with three apps (`players`, `games`, `analysis`). A Celery worker runs server Stockfish over UCI, builds a fact packet per move in code, writes template text for ordinary moves and asks Gemini's free tier for key moments, and stores everything in two shared cache tables keyed by position. The review page is a Django template plus jQuery and cm-chessboard, polling a JSON status endpoint.

**Tech Stack:** Python 3.12, Django 5.x, Postgres 16, Redis 7, Celery 5, python-chess, Stockfish (Debian package, arm64), google-genai SDK, requests, pytest-django, responses (HTTP mocking), cm-chessboard (MIT), chess.js (BSD), Bootstrap 5, jQuery 3, Docker Compose.

**Spec:** Chess Coach App: Design — https://claude.ai/artifact/CxdoNZcFvBPCmpGE58shQv

**Later plans (not in this one):** 2. Exploration board (browser Stockfish + "Explain this position", 20/week). 3. Opening lessons. 4. Endgame lessons. 5. My patterns (`MistakeTag`).

## Global Constraints

- No GPL code in our own bundle: board = cm-chessboard (MIT), rules = chess.js (BSD). Never chessground.
- Stockfish runs only as a separate process over UCI (`chess.engine.SimpleEngine.popen_uci`); never linked or vendored into our code.
- Only server analysis writes to `PositionAnalysis` and `MoveExplanation`.
- Normalised FEN = the first 4 FEN fields (board, side to move, castling, en passant); move counters dropped.
- Win% = `50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)`, from the mover's point of view. Mate for the mover = 100, mate against = 0.
- Grades by win% drop for the mover: `< 10` → good (or best if it is the engine's top move), `>= 10` inaccuracy, `>= 20` mistake, `>= 30` blunder.
- Engine: MultiPV 3, depth from `settings.ENGINE_DEPTH` (default 18; tests use 8).
- Key moment = grade in {inaccuracy, mistake, blunder}, for either side's move (so the opponent's errors are key moments too). Every big swing is already one of these grades.
- Languages: `fr` and `en` only, for UI and explanations. Explanations are cached per language.
- Limits from settings: `LIMIT_REVIEWS_PER_WEEK = 5`, `LIMIT_EXPLAINS_PER_WEEK = 20`. Week = ISO week in UTC. Reviewing a game that already has a finished analysis is free.
- Chess.com: requests one at a time, a `User-Agent` naming the app and a contact email (`settings.CHESSCOM_USER_AGENT`), ETag caching, only the current and previous month's archives.
- AI provider is chosen by `settings.AI_PROVIDER` (`"gemini"` or `"none"`); model by `settings.GEMINI_MODEL`; key from env `GEMINI_API_KEY`.
- Deploy target: one Oracle Cloud Always Free ARM server (2 OCPU, 12 GB). All images must build for arm64.
- Keep it minimal: function-based or simple class-based views, no DRF, no frontend framework, no build step for JS.

## Review Focus

1. A username that doesn't exist, or typed in a different letter case → friendly error on the sign-in page; usernames stored lowercase so "Farel" and "farel" are one player. (Task 2)
2. Archives that contain non-standard games (chess960, bughouse, three-check) or games with no moves → skipped at import, never crash a review. (Task 3)
3. Games that end in checkmate or stalemate, and engine scores given as mate → the terminal position is graded without calling the engine and mate scores convert to 100/0. (Tasks 4, 5)
4. Gemini quota exhausted, timeout, or a reply that names an illegal move → the review still finishes with template text and the move is queued for AI text later. (Tasks 8, 9)
5. The same game reviewed twice, or by both players, or two workers hitting the same position at once → one `Game` row, one cache row per position, no second charge against the weekly limit. (Tasks 4, 9, 10)

---

## File Structure

```
chess-coach/
  docker-compose.yml          # web, worker, db, redis
  Dockerfile                  # python:3.12-slim + apt stockfish (arm64 + amd64)
  requirements.txt
  .env.example
  pytest.ini
  conftest.py                 # shared fixtures: player, game_pgn, fake_provider
  config/settings.py          # all settings named in Global Constraints
  config/urls.py
  config/celery.py
  players/models.py           # Player, UsageCounter
  players/limits.py           # try_consume()
  players/views.py            # signin, signout, set_language
  games/chesscom.py           # Chess.com client
  games/models.py             # Game
  games/importer.py           # import_recent_games()
  games/views.py              # game_list
  analysis/models.py          # PositionAnalysis, MoveExplanation, GameReview
  analysis/engine.py          # normalize_fen(), analyse()
  analysis/grading.py         # win_percent(), grade_move(), is_key_moment()
  analysis/facts.py           # FactPacket, build_fact_packet()
  analysis/phrases.py         # template_text() FR/EN
  analysis/ai.py              # Provider protocol, GeminiProvider, NoneProvider, validate_text()
  analysis/explain.py         # get_explanation()
  analysis/tasks.py           # run_review, upgrade_pending_explanations
  analysis/views.py           # start_review, review_page, review_status
  templates/                  # base.html, signin.html, game_list.html, review.html
  static/js/review.js
  static/vendor/              # cm-chessboard, chess.js (with their LICENSE files)
  locale/fr/LC_MESSAGES/django.po
  tests/                      # one test module per source module
```

---

### Task 1: Project skeleton, containers, settings

**Files:**
- Create: `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `.env.example`, `pytest.ini`, `conftest.py`, `config/settings.py`, `config/urls.py`, `config/celery.py`, `README.md`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: settings `ENGINE_DEPTH`, `ENGINE_PATH` (default `/usr/games/stockfish`), `LIMIT_REVIEWS_PER_WEEK`, `LIMIT_EXPLAINS_PER_WEEK`, `AI_PROVIDER`, `GEMINI_MODEL`, `CHESSCOM_USER_AGENT`, `LANGUAGES = [("fr", "Français"), ("en", "English")]`; `CELERY_TASK_ALWAYS_EAGER` true under tests; URL namespace root `/`.

- [ ] **Step 1: Write the failing tests**

```python
def test_settings_values(settings):
    assert settings.LIMIT_REVIEWS_PER_WEEK == 5
    assert settings.LIMIT_EXPLAINS_PER_WEEK == 20
    assert [c for c, _ in settings.LANGUAGES] == ["fr", "en"]
    assert settings.AI_PROVIDER in ("gemini", "none")

def test_stockfish_binary_runs(settings):
    import chess.engine
    eng = chess.engine.SimpleEngine.popen_uci(settings.ENGINE_PATH)
    assert "Stockfish" in eng.id["name"]
    eng.quit()
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose run --rm web pytest tests/test_setup.py -v`
Expected: FAIL (no project yet).

- [ ] **Step 3: Create the project.** `Dockerfile` installs `stockfish` from Debian apt (works on arm64 and amd64). `docker-compose.yml` runs `web` (gunicorn), `worker` (`celery -A config worker -c 2`), `db` (postgres:16), `redis` (redis:7). Tests use `ENGINE_DEPTH=8` and `AI_PROVIDER=none` via `pytest.ini` env. `README.md` lists: run locally, run tests, deploy to Oracle Always Free ARM (keep total A1 at or under 2 OCPU / 12 GB), and the license notice for Stockfish (GPL-3.0, source link).

- [ ] **Step 4: Run to verify pass**

Run: `docker compose run --rm web pytest tests/test_setup.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: django project skeleton with celery, postgres, redis, stockfish"
```

---

### Task 2: Player sign-in by Chess.com username

**Files:**
- Create: `players/models.py`, `players/views.py`, `games/chesscom.py`, `templates/base.html`, `templates/signin.html`
- Test: `tests/test_signin.py`, `tests/test_chesscom.py`

**Interfaces:**
- Produces:
  - `Player(chesscom_username: CharField unique, lowercase; language: "fr"|"en"; rating: IntegerField null; created_at)`
  - `games.chesscom.get_player(username: str) -> dict | None` (None on 404; raises `ChessComUnavailable` on 429/5xx/timeout)
  - `players.views.current_player(request) -> Player | None` (from `request.session["player_id"]`)
  - URLs: `signin` (`/`), `signout`, `set_language` (POST `lang`)

- [ ] **Step 1: Write the failing tests**

```python
@responses.activate
def test_get_player_404_returns_none():
    responses.get("https://api.chess.com/pub/player/nobody_xyz", status=404)
    assert chesscom.get_player("nobody_xyz") is None

@responses.activate
def test_get_player_sends_user_agent(settings):
    responses.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
    chesscom.get_player("Farel")
    assert responses.calls[0].request.headers["User-Agent"] == settings.CHESSCOM_USER_AGENT
    assert responses.calls[0].request.url.endswith("/player/farel")

@responses.activate
def test_signin_unknown_username_shows_error(client):
    responses.get("https://api.chess.com/pub/player/nobody_xyz", status=404)
    r = client.post("/", {"username": "nobody_xyz"})
    assert r.status_code == 200 and "nobody_xyz" in r.content.decode()
    assert Player.objects.count() == 0

@responses.activate
def test_signin_case_insensitive_one_player(client):
    responses.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
    client.post("/", {"username": "Farel"}); client.post("/", {"username": "farel"})
    assert Player.objects.get().chesscom_username == "farel"

def test_language_guessed_from_browser(client, mocked_farel):
    client.post("/", {"username": "farel"}, HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9")
    assert Player.objects.get().language == "fr"
```

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_signin.py tests/test_chesscom.py -v` → FAIL.

- [ ] **Step 3: Implement** `get_player`, `Player`, `signin` view (POST: strip + lowercase, `get_player`, `get_or_create`, set session, redirect to `game_list`; on `ChessComUnavailable` show "Chess.com is not answering, try again in a minute"). `language` defaults from `request.LANGUAGE_CODE` if it is `fr`, else `en`.

- [ ] **Step 4: Run to verify pass** — all tests above pass.

- [ ] **Step 5: Commit** — `git commit -m "feat: sign in with chess.com username"`

---

### Task 3: Import recent games

**Files:**
- Create: `games/models.py`, `games/importer.py`, `games/views.py`, `templates/game_list.html`
- Modify: `games/chesscom.py` (add archive fetch)
- Test: `tests/test_importer.py`, `tests/fixtures/archive_2026_11.json` (real-shaped archive with 1 standard rapid, 1 chess960, 1 game with empty PGN moves, 1 standard blitz)

**Interfaces:**
- Consumes: `get_player`, `Player`, `current_player`
- Produces:
  - `chesscom.get_month_games(username: str, year: int, month: int) -> list[dict]` (uses stored ETag; on 304 returns `[]`)
  - `Game(chesscom_url unique, pgn, white, black, white_rating, black_rating, result, time_control, eco, opening_name, played_at)`
  - `importer.import_recent_games(player: Player, today: date) -> list[Game]` — current + previous month, newest first
  - URL `game_list` (`/games/`)

- [ ] **Step 1: Write the failing tests**

```python
def test_import_skips_variants_and_empty_games(player, mock_archive):
    games = import_recent_games(player, date(2026, 11, 20))
    assert len(games) == 2
    assert all("[Variant" not in g.pgn for g in games)

def test_import_fetches_two_months_serially(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    urls = [c.request.url for c in responses.calls]
    assert urls[-2:] == [".../games/2026/11", ".../games/2026/10"]  # exact URLs in the test

def test_import_twice_no_duplicates(player, mock_archive):
    import_recent_games(player, date(2026, 11, 20))
    import_recent_games(player, date(2026, 11, 20))
    assert Game.objects.count() == 2

def test_january_reaches_back_to_december(player, mock_archive_jan):
    import_recent_games(player, date(2027, 1, 3))
    assert any(c.request.url.endswith("/2026/12") for c in responses.calls)

def test_game_list_newest_first(client, signed_in, imported):
    r = client.get("/games/")
    assert r.context["games"][0].played_at > r.context["games"][1].played_at
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Keep a game only when `rules == "chess"` and the PGN parses with python-chess to at least one move. `eco`/`opening_name` come from the PGN `ECO` and `ECOUrl` headers (name = last path segment of `ECOUrl`, dashes to spaces).
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: import recent chess.com games"`

---

### Task 4: Engine wrapper and position cache

**Files:**
- Create: `analysis/models.py` (`PositionAnalysis` only in this task), `analysis/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Produces:
  - `normalize_fen(board: chess.Board) -> str`
  - `PositionAnalysis(fen unique, depth, lines: JSON list of {"uci": [str], "cp": int|None, "mate": int|None}, engine_version, created_at)` — scores from the side to move's point of view
  - `analyse(board: chess.Board) -> PositionAnalysis` — cache-first; terminal positions (`board.is_game_over()`) stored without calling the engine, with `lines=[]` and score `mate=0` for checkmate (side to move is mated) or `cp=0` for draws
  - One engine process per worker, opened lazily: `get_engine() -> chess.engine.SimpleEngine`

- [ ] **Step 1: Write the failing tests**

```python
def test_normalize_drops_counters():
    b = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert normalize_fen(b) == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -"

def test_analyse_returns_three_lines(db):
    pa = analyse(chess.Board())
    assert len(pa.lines) == 3 and pa.depth == 8

def test_analyse_is_cached(db, mocker):
    analyse(chess.Board())
    spy = mocker.spy(engine_mod, "get_engine")
    analyse(chess.Board())
    spy.assert_not_called()

def test_checkmate_position_needs_no_engine(db, mocker):
    b = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    spy = mocker.spy(engine_mod, "get_engine")
    pa = analyse(b)
    assert pa.lines == [] and pa.mate_for_side_to_move() == 0
    spy.assert_not_called()

def test_concurrent_insert_same_fen_keeps_one_row(db, mocker):
    # another worker inserts the row between our cache lookup and our insert
    existing = PositionAnalysis.objects.create(fen=normalize_fen(chess.Board()), depth=8, lines=[])
    mocker.patch.object(engine_mod, "_cached", return_value=None)  # _cached(fen) is the lookup helper
    pa = analyse(chess.Board())
    assert pa.pk == existing.pk and PositionAnalysis.objects.count() == 1
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Insert with `get_or_create` inside `transaction.atomic()`, catching `IntegrityError` and re-reading. Add `PositionAnalysis.mate_for_side_to_move() -> int | None` and `best_cp() -> int | None` helpers.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: stockfish wrapper with shared position cache"`

---

### Task 5: Win% and move grading

**Files:**
- Create: `analysis/grading.py`
- Test: `tests/test_grading.py`

**Interfaces:**
- Consumes: `PositionAnalysis`
- Produces:
  - `win_percent(cp: int | None, mate: int | None) -> float` (mover's POV)
  - `grade_move(wp_before: float, wp_after: float, is_engine_best: bool) -> str` in `{"best","good","inaccuracy","mistake","blunder"}`
  - `is_key_moment(grade: str) -> bool`
  - `mover_wp_after(analysis_after: PositionAnalysis) -> float` (flips the opponent's POV: `100 - wp`)

- [ ] **Step 1: Write the failing tests**

```python
def test_win_percent_values():
    assert win_percent(0, None) == pytest.approx(50.0)
    assert win_percent(100, None) == pytest.approx(59.1, abs=0.1)
    assert win_percent(None, 3) == 100.0
    assert win_percent(None, -2) == 0.0

@pytest.mark.parametrize("before,after,best,expected", [
    (60, 60, True, "best"), (60, 52, False, "good"), (60, 50, False, "inaccuracy"),
    (60, 40, False, "mistake"), (60, 30, False, "blunder")])
def test_grade_thresholds(before, after, best, expected):
    assert grade_move(before, after, best) == expected

@pytest.mark.parametrize("grade,expected", [
    ("best", False), ("good", False), ("inaccuracy", True), ("mistake", True), ("blunder", True)])
def test_key_moment(grade, expected):
    assert is_key_moment(grade) is expected
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** with the Global Constraints formula and thresholds.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: win percent and move grading"`

---

### Task 6: Fact packets

**Files:**
- Create: `analysis/facts.py`
- Test: `tests/test_facts.py`

**Interfaces:**
- Consumes: `PositionAnalysis`, `grading.*`
- Produces: frozen dataclass

```python
@dataclass(frozen=True)
class FactPacket:
    ply: int
    mover: str                 # "white" | "black"
    san: str
    grade: str
    key_moment: bool
    wp_before: float
    wp_after: float
    best_san: str | None       # None when the played move is the best
    best_line_san: list[str]   # up to 6 plies from the position before
    replies_san: list[str]     # opponent's top 3 replies after the played move
    is_check: bool
    captured: str | None       # piece name, e.g. "knight"
    hanging_after: list[str]   # mover's pieces attacked and undefended after the move, e.g. ["queen on d5"]
    forks: list[str]           # enemy pieces attacked by the moved piece when >= 2 of them are worth more than a pawn
    material_diff: int         # mover minus opponent, pawn = 1, minor = 3, rook = 5, queen = 9
    def allowed_san(self) -> set[str]: ...  # san, best_san, best_line_san, replies_san
```

- `build_fact_packet(board_before: chess.Board, move: chess.Move, before: PositionAnalysis, after: PositionAnalysis, ply: int) -> FactPacket`

- [ ] **Step 1: Write the failing tests** (each uses a fixed FEN)

```python
def test_hanging_queen_detected(db): ...      # after Qd5?? in a set FEN, "queen on d5" in packet.hanging_after
def test_knight_fork_detected(db): ...        # Nc7+ forking king and rook: packet.forks == ["king on e8", "rook on a8"]
def test_capture_named(db): ...               # Bxf7: packet.captured == "pawn"
def test_best_move_is_none_when_played(db): ...  # starting position, play the engine's first line move: best_san is None
def test_replies_are_opponent_moves_in_san(db): ...  # every replies_san item is legal in board_after
def test_allowed_san_covers_all_lists(db): ...
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** using `board.attackers()`/`board.attacks()`; convert engine UCI lines to SAN by replaying on a copy of the board.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: fact packet per move"`

---

### Task 7: Template sentences (FR/EN)

**Files:**
- Create: `analysis/phrases.py`
- Test: `tests/test_phrases.py`

**Interfaces:**
- Consumes: `FactPacket`
- Produces: `template_text(p: FactPacket, lang: str, depth: str) -> str`, `depth in {"short","full"}`. Short = one or two sentences for ordinary moves. Full = what went wrong, the better move and the opponent's replies, built only from packet fields.

- [ ] **Step 1: Write the failing tests**

```python
def test_short_en_mentions_move(packet_good):
    assert "Nf3" in template_text(packet_good, "en", "short")

def test_full_fr_names_better_move_and_replies(packet_blunder):
    t = template_text(packet_blunder, "fr", "full")
    assert packet_blunder.best_san in t and "Mieux" in t
    assert all(r in t for r in packet_blunder.replies_san)

def test_hanging_piece_sentence_en(packet_hanging_queen):
    assert "queen on d5" in template_text(packet_hanging_queen, "en", "full")

def test_only_packet_moves_appear(packet_blunder):
    assert validate_text(template_text(packet_blunder, "en", "full"), packet_blunder)  # from Task 8
```

(Move the last test into Task 8's file if Task 8 is not done yet; it must pass by the end of Task 8.)

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement** with a small dict of phrase strings per language; piece names translated (`queen` → `dame`, `knight` → `cavalier`, `bishop` → `fou`, `rook` → `tour`, `pawn` → `pion`, `king` → `roi`). SAN stays in English letters in both languages.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: template explanations in french and english"`

---

### Task 8: AI provider and validator

**Files:**
- Create: `analysis/ai.py`
- Test: `tests/test_ai.py`

**Interfaces:**
- Consumes: `FactPacket`
- Produces:
  - `class Provider(Protocol): name: str; def explain(self, p: FactPacket, lang: str) -> str`
  - `class QuotaExceeded(Exception)`, `class ProviderError(Exception)`
  - `GeminiProvider(model: str, api_key: str)` — maps HTTP 429 / `RESOURCE_EXHAUSTED` to `QuotaExceeded`; timeouts and other failures to `ProviderError`; timeout 20 s
  - `NoneProvider` — always raises `QuotaExceeded` (so `AI_PROVIDER="none"` behaves like an empty quota)
  - `get_provider() -> Provider` from settings
  - `build_prompt(p: FactPacket, lang: str) -> str`
  - `validate_text(text: str, p: FactPacket) -> bool` — every SAN-looking token (regex `\b(?:[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|O-O(?:-O)?)(?:=[QRBN])?[+#]?`) must be in `p.allowed_san()` after stripping `+`/`#`; empty text is invalid

- [ ] **Step 1: Write the failing tests**

```python
def test_validate_rejects_invented_move(packet_blunder):
    assert not validate_text("Better was Qh5 winning.", packet_blunder)  # Qh5 not in packet

def test_validate_accepts_packet_moves(packet_blunder):
    assert validate_text(f"Better was {packet_blunder.best_san}.", packet_blunder)

def test_prompt_contains_facts_and_rules(packet_blunder):
    pr = build_prompt(packet_blunder, "fr")
    assert packet_blunder.best_san in pr
    assert "1300" in pr and "only the moves listed" in pr and "French" in pr

def test_gemini_429_raises_quota(mocker, packet_blunder):
    ...  # mock the SDK client call to raise the SDK's 429 error; expect QuotaExceeded

def test_none_provider_raises_quota(packet_blunder):
    with pytest.raises(QuotaExceeded): NoneProvider().explain(packet_blunder, "en")
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** The prompt lists the packet fields as plain lines, says the reader is ~1300, asks for at most 5 short sentences in the target language, and says to mention only the moves listed. Use the `google-genai` SDK's `generate_content`.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: pluggable AI provider with gemini and move validator"`

---

### Task 9: Explanation service and cache

**Files:**
- Modify: `analysis/models.py` (add `MoveExplanation`)
- Create: `analysis/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `FactPacket`, `template_text`, `get_provider`, `validate_text`, `PositionAnalysis`
- Produces:
  - `MoveExplanation(position FK PositionAnalysis, move_uci, language, depth, text, source: "template"|"ai", model, needs_ai: bool, created_at)`, unique on `(position, move_uci, language, depth)`
  - `get_explanation(position: PositionAnalysis, move_uci: str, p: FactPacket, lang: str) -> MoveExplanation` — depth = `"full"` if `p.key_moment` else `"short"`; cache-first; short → template; full → provider, retry once on invalid text, then template with `needs_ai=True`; `QuotaExceeded`/`ProviderError` → template with `needs_ai=True`
  - Celery task `upgrade_pending_explanations()` in `analysis/tasks.py` — retries `needs_ai=True` rows, oldest first, stopping at the first `QuotaExceeded`; scheduled daily at 08:05 UTC (just after the Pacific-midnight reset)

- [ ] **Step 1: Write the failing tests**

```python
def test_ordinary_move_uses_template_no_ai(db, packet_good, fake_provider):
    e = get_explanation(pos, "g1f3", packet_good, "en")
    assert e.source == "template" and fake_provider.calls == 0

def test_key_moment_uses_ai(db, packet_blunder, fake_provider):
    e = get_explanation(pos, "d1d5", packet_blunder, "en")
    assert e.source == "ai" and e.depth == "full"

def test_cached_second_call_free(db, packet_blunder, fake_provider):
    get_explanation(...); get_explanation(...)
    assert fake_provider.calls == 1

def test_invalid_ai_text_retries_once_then_template(db, packet_blunder, fake_provider_invents):
    e = get_explanation(...)
    assert fake_provider_invents.calls == 2 and e.source == "template" and e.needs_ai

def test_quota_exceeded_falls_back(db, packet_blunder, quota_provider):
    e = get_explanation(...)
    assert e.source == "template" and e.needs_ai

def test_languages_cached_separately(db, packet_blunder, fake_provider):
    get_explanation(..., "en"); get_explanation(..., "fr")
    assert MoveExplanation.objects.count() == 2

def test_upgrade_stops_at_quota(db, two_pending, quota_after_one_provider):
    upgrade_pending_explanations()
    assert MoveExplanation.objects.filter(needs_ai=True).count() == 1
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement**, with the same `get_or_create` + `IntegrityError` re-read pattern as Task 4.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: cached explanations with template fallback"`

---

### Task 10: Review job and weekly limits

**Files:**
- Modify: `analysis/models.py` (add `GameReview`), `players/models.py` (add `UsageCounter`)
- Create: `players/limits.py`, `analysis/tasks.py` (add `run_review`)
- Test: `tests/test_review_job.py`, `tests/test_limits.py`

**Interfaces:**
- Consumes: `Game`, `Player`, `analyse`, `grading.*`, `build_fact_packet`, `get_explanation`
- Produces:
  - `UsageCounter(player, iso_year, iso_week, reviews_used, explains_used)` unique on `(player, iso_year, iso_week)`
  - `try_consume(player: Player, kind: str, now: datetime) -> bool` — `kind in {"reviews","explains"}`; atomic `F()` increment only when under the limit
  - `GameReview(game FK, player FK, language: "fr"|"en" copied from the player at start, status: "queued"|"running"|"done"|"failed", counts: JSON {grade: n}, moves: JSON list of {ply, san, uci, fen_before, grade, key_moment, explanation_id, best_uci, replies_uci}, error, created_at, finished_at)`, unique on `(game, player)`
  - `start_review(player: Player, game: Game) -> GameReview | None` in `analysis/tasks.py` — returns the existing review if one exists; free (no `try_consume`) when any `GameReview` for that game is `done`; otherwise `try_consume(..., "reviews")`, `None` when over the limit; queues `run_review.delay(review.id)`
  - Celery task `run_review(review_id: int) -> None` — walks every ply, fills `moves` and `counts`, sets `done`; any unexpected exception sets `failed` with `error` and refunds the review count

- [ ] **Step 1: Write the failing tests**

```python
def test_sixth_review_in_week_refused(db, player, six_games):
    results = [start_review(player, g) for g in six_games]
    assert sum(r is not None for r in results) == 5

def test_limit_resets_next_iso_week(db, player):
    sunday = datetime(2026, 11, 22, 23, 0, tzinfo=UTC)   # ISO week 47
    monday = datetime(2026, 11, 23, 1, 0, tzinfo=UTC)    # ISO week 48
    assert all(try_consume(player, "reviews", sunday) for _ in range(5))
    assert not try_consume(player, "reviews", sunday)
    assert try_consume(player, "reviews", monday)

def test_same_game_twice_counts_once(db, player, game):
    start_review(player, game); start_review(player, game)
    assert UsageCounter.objects.get().reviews_used == 1

def test_opponent_review_of_done_game_is_free(db, player, opponent, game_done_by_player):
    start_review(opponent, game)
    assert not UsageCounter.objects.filter(player=opponent, reviews_used__gt=0).exists()

def test_run_review_fills_every_ply(db, player, short_game):  # 10-ply real game, depth 8, provider none
    r = start_review(player, short_game)
    r.refresh_from_db()
    assert r.status == "done" and len(r.moves) == 10
    assert all(m["explanation_id"] for m in r.moves)

def test_game_ending_in_mate_reviews(db, player, scholars_mate_game):
    r = start_review(player, scholars_mate_game); r.refresh_from_db()
    assert r.status == "done"

def test_failure_refunds(db, player, game, mocker):
    mocker.patch("analysis.tasks.analyse", side_effect=RuntimeError("boom"))
    r = start_review(player, game); r.refresh_from_db()
    assert r.status == "failed" and UsageCounter.objects.get().reviews_used == 0
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat: review job with weekly limits"`

---

### Task 11: Review page, status endpoint, French UI

**Files:**
- Create: `analysis/views.py`, `templates/review.html`, `static/js/review.js`, `static/vendor/cm-chessboard/*` (+ LICENSE), `static/vendor/chess.js` (+ LICENSE), `locale/fr/LC_MESSAGES/django.po`
- Modify: `templates/game_list.html` (Review button, remaining reviews this week), `config/urls.py`, `templates/base.html` (FR/EN switch, footer link "Stockfish — GPL-3.0 — source")
- Test: `tests/test_review_views.py`

**Interfaces:**
- Consumes: `start_review`, `GameReview`, `MoveExplanation`, `current_player`
- Produces:
  - POST `/games/<game_id>/review/` → redirect to review page; when `start_review` returns `None`, back to game list with message "You've used your 5 reviews this week" (FR: "Tu as utilisé tes 5 analyses de la semaine")
  - GET `/reviews/<review_id>/` → page
  - GET `/reviews/<review_id>/status.json` → `{"status": str, "counts": {...}, "moves": [{"ply", "san", "fen_before", "grade", "key_moment", "best_uci", "replies_uci", "text"}]}` with `text` in the review's language (switching UI language later doesn't re-explain an old review; v1 keeps it that simple); 404 for another player's review

- [ ] **Step 1: Write the failing tests**

```python
def test_status_json_shape(client, signed_in, done_review):
    d = client.get(f"/reviews/{done_review.id}/status.json").json()
    assert d["status"] == "done"
    assert set(d["moves"][0]) == {"ply","san","fen_before","grade","key_moment","best_uci","replies_uci","text"}

def test_status_text_in_review_language(client, signed_in_fr, done_review_fr):
    d = client.get(f"/reviews/{done_review_fr.id}/status.json").json()
    e = MoveExplanation.objects.get(id=done_review_fr.moves[0]["explanation_id"])
    assert e.language == "fr" and d["moves"][0]["text"] == e.text

def test_other_players_review_is_404(client, signed_in, someone_elses_review):
    assert client.get(f"/reviews/{someone_elses_review.id}/status.json").status_code == 404

def test_over_limit_message_fr(client, signed_in_fr, limit_used_up, game):
    r = client.post(f"/games/{game.id}/review/", follow=True)
    assert "Tu as utilisé tes 5 analyses de la semaine" in r.content.decode()

def test_signed_out_redirects_to_signin(client, done_review):
    r = client.get(f"/reviews/{done_review.id}/")
    assert r.status_code == 302 and r.url == "/"
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** `review.js`: poll `status.json` every 3 s until `done`/`failed`; render a move list with grade badges (colours: best/good neutral, inaccuracy yellow, mistake orange, blunder red); clicking a move sets the board to `fen_before`, shows the played move and, for key moments, an arrow for `best_uci` and clickable `replies_uci` that play out on the board with chess.js. Left/right arrow keys step through moves. Layout stacks board above text under 576 px wide.
- [ ] **Step 4: Run to verify pass**, then the manual check: `docker compose up`, sign in with a real username, review a real game on a phone-width window (375 px) in both languages.
- [ ] **Step 5: Commit** — `git commit -m "feat: review page with board, explanations and french ui"`

---

## Self-review notes

- Spec coverage for this plan's slice: sign-in, import, server engine, grading, fact packets, two-depth explanations, $0 AI path with fallback and later upgrade, shared caches, weekly review limit, FR/EN, phone layout, GPL-safe front-end libraries, Oracle ARM deploy notes. Deferred on purpose to plans 2–5: exploration board and its 20/week limit (`explains_used` is created here so plan 2 only adds the endpoint), opening lessons, endgame lessons with tablebase, My patterns.
- Names checked across tasks: `analyse`, `PositionAnalysis`, `FactPacket.allowed_san`, `get_explanation`, `start_review`, `run_review`, `try_consume`, `current_player`.
