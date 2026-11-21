# ChessMind Foundation (Milestone 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A newcomer opens ChessMind on a phone, plays a hand-made lesson as a guest, earns XP and a streak, signs up with email and password and keeps everything; staff publish lessons through a validated, reviewed workflow.

**Architecture:** Four new Django apps (`accounts`, `curriculum`, `learning`, `gamification`) sit beside `players`, `games`, `analysis`. Rules live in pure `domain/` modules (no ORM, no I/O), `services.py` wraps them in transactions, views are thin. The lesson player is a set of ES modules on the vendored cm-chessboard + chess.js: it checks answers instantly and sends every try to `/api/v1/attempts/<id>/finish`, where the server re-scores before awarding XP.

**Tech Stack:** Python 3.12, Django 5.2, Postgres 16, Redis 7, Celery 5, python-chess, Stockfish (lesson validation only), pytest-django, responses, pytest-mock; cm-chessboard (MIT) and chess.js (BSD) already in `static/vendor/`; Playwright for Python (dev-only, end-to-end tests).

**Spec:** ChessMind Learning Platform: Design — https://claude.ai/artifact/DboSaF5t4A3pQ3Hrachk2j. This plan is roadmap milestone 1, "Foundation". Read the spec sections Lesson format, Database schema, API contract, XP/streaks, UI/UX and Testing alongside it.

**Branch:** `chessmind-foundation` (never commit to `main`).

**Not in this plan:** lesson generation, datasets and AI lesson text (M2); opening catalog, review cards, Daily training, favourites (M3); endgame catalog and tablebase (M4). `ReviewCard`, `CardReview`, `FavoriteOpening`, `OpeningLine`, `Puzzle`, `TablebaseEntry` are not created here.

## Global Constraints

- Stack: Django 5, Postgres 16, Redis 7, Celery 5. No Django REST Framework, no SPA, no JS build step. New Python runtime dependencies: none. Dev-only: `playwright==1.49.0`, `pytest-playwright>=0.5,<0.8`.
- Languages: `fr` and `en` for every UI string and every lesson text. Every new template/JS string gets a French entry in `locale/fr/LC_MESSAGES/django.po`; run `compilemessages` and commit `.po` and `.mo` together.
- Lesson text is written with English SAN (K Q R B N) in both languages. French display converts piece letters K→R, Q→D, R→T, B→F, N→C (server in `localize()`, browser in `san.js`).
- Learners only ever receive a lesson's published version; an attempt is pinned to the version it started on.
- No learner request calls Gemini, Lichess or the Stockfish engine. Chess.com is called only by the existing game import and by "Connect Chess.com".
- XP: first completion 10; +5 once per lesson when first-try accuracy ≥ 0.9; replay 3, only for the first replay of that lesson per local day. Amounts are settings.
- Streak: a local day (learner's time zone) counts when the learner earns any XP that day; the day after the last active day adds 1, a gap resets to 1; the page shows 0 once a day has been missed.
- Levels: level *n* starts at `25 × n × (n − 1)` XP. Daily goal choices `(10, 20, 30, 50)`, default 20.
- Sessions last 1 year (`SESSION_COOKIE_AGE = 31536000`). Guests idle 180 days are deleted. Attempts expire after 24 hours (HTTP 410).
- API errors: `{"error": {"code": "...", "message": "..."}}`; another learner's object answers 404; every POST needs the CSRF token.
- Lesson checks: 6 to 15 steps and texts ≤ 280 characters are warnings, not failures.
- Phones first: every page works at 390 px wide; touch targets ≥ 44 px; the lesson player is full-screen.
- Run tests in Docker with the code mounted: `docker compose run --rm test pytest <path> -v` (engine depth 8, `AI_PROVIDER=none`, eager Celery).

## Review Focus

1. A learner near midnight or across a daylight-saving change (Europe/Paris, America/Montreal): XP at 23:30 and at 00:10 local time falls on two local days and the streak counts them as consecutive, even when both are the same UTC day. Test in Task 11.
2. A double-tapped or retried Finish on a slow phone network: the second call returns the stored result with 200 and no extra XP rows. Test in Task 12.
3. A guest with progress logs into an account that already did some of the same lessons: no double first-completion XP, best accuracy kept, streak rebuilt from both histories. Tests in Tasks 10 and 11.
4. A lesson is republished while someone is mid-lesson: their Finish is scored against the version they started, not the new one. Test in Task 12.
5. A garbled or hostile Finish body (illegal moves, wrong shapes, unknown step ids, thousands of tries, a body over 64 KB): HTTP 400 with no `StepResult`, no progress and no XP written. Tests in Tasks 9 and 12.

---

## File Structure

```
chess-coach/
  docker-compose.yml          # + test service (code mounted), + e2e service (profile e2e), worker -Q celery,content
  Dockerfile.e2e              # Playwright image + app requirements
  requirements-dev.txt        # playwright, pytest-playwright
  pytest.ini                  # + testpaths = tests
  conftest.py                 # + learner/user/staff/lesson factories shared by tests and e2e
  config/settings.py, test_settings.py, urls.py, celery.py
  accounts/                   # Learner, guests, signup/login/merge, settings, Chess.com link, deletion
    models.py services.py middleware.py context.py signals.py forms.py views.py urls.py tasks.py admin.py
  curriculum/                 # courses, lessons, versions, workflow, validation, studio, import
    models.py services.py validation.py tasks.py studio.py urls.py admin.py
    domain/workflow.py domain/schema.py domain/san.py
    management/commands/import_lessons.py
    seed/foundation.json      # the three hand-made lessons
  learning/                   # attempts, progress, unlocking, lesson API, pages
    models.py services.py api.py urls_api.py views.py urls.py admin.py
    domain/scoring.py domain/unlock.py
  gamification/               # XP ledger, streak, levels, achievements
    models.py services.py admin.py
    domain/xp.py domain/streak.py domain/levels.py domain/achievements.py
  players/views.py            # current_player() now reads request.learner; signin/signout removed (Task 13)
  templates/base.html         # rewritten as the ChessMind shell (Task 13)
  templates/accounts/ registration/ studio/ learning/
  static/css/chessmind.css    # tokens + components
  static/fonts/nunito/        # nunito-latin-wght-normal.woff2 + OFL.txt
  static/js/player/           # main.js queue.js board.js ui.js san.js steps/*.js
  e2e/                        # Playwright tests + fixture lesson
  tests/                      # one module per area (names in each task)
```

---

### Task 1: Test service, new apps, authentication middleware, admin

**Files:**
- Modify: `docker-compose.yml`, `pytest.ini`, `config/settings.py`, `config/test_settings.py`, `config/urls.py`, `README.md`
- Create: `accounts/`, `curriculum/`, `learning/`, `gamification/` — each with `__init__.py`, `apps.py`, `models.py` (empty), `migrations/__init__.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: `docker compose run --rm test …` runs against the mounted code; `/admin/`; settings `SESSION_COOKIE_AGE`, `LOGIN_URL = "/login/"`, `CACHES` (Redis), `CELERY_TASK_ROUTES = {"curriculum.tasks.*": {"queue": "content"}}`, `AUTH_PASSWORD_VALIDATORS` (Django's four defaults).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_setup.py`)

```python
def test_foundation_settings(settings):
    assert settings.SESSION_COOKIE_AGE == 365 * 24 * 3600
    assert settings.LOGIN_URL == "/login/"
    assert settings.CELERY_TASK_ROUTES["curriculum.tasks.*"] == {"queue": "content"}
    assert {"django.contrib.admin", "accounts", "curriculum", "learning", "gamification"} <= set(settings.INSTALLED_APPS)
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE

def test_admin_asks_for_login(client, db):
    r = client.get("/admin/")
    assert r.status_code == 302 and r.url.startswith("/admin/login/")
```

- [ ] **Step 2: Add the `test` service, then run to verify failure**

`test` service: `build: .`, `profiles: ["test"]`, `env_file: .env`, `volumes: [".:/app"]`, `depends_on: [db, redis]`, `command: pytest`. Add `testpaths = tests` to `pytest.ini`. Change the worker command to `celery -A config worker -B -Q celery,content -c 2 -l info`.

Run: `docker compose run --rm test pytest tests/test_setup.py -v` — Expected: the two new tests FAIL.

- [ ] **Step 3: Implement the settings and apps.** `django.contrib.admin` goes first in `INSTALLED_APPS`; the four apps go after `analysis`. `AuthenticationMiddleware` goes right after `SessionMiddleware`. Add the `django.contrib.auth.context_processors.auth` context processor. `CACHES` uses `django.core.cache.backends.redis.RedisCache` on `REDIS_URL`; `test_settings.py` overrides it with `LocMemCache` and sets `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]`. Mount `admin.site.urls` at `admin/`. In the README, the test command becomes `docker compose run --rm test pytest`.

- [ ] **Step 4: Run all tests** — `docker compose run --rm test pytest -v` → every existing test plus the two new ones PASS.

- [ ] **Step 5: Commit** — `git commit -m "chore: test service, chessmind apps, auth middleware and admin"`

---

### Task 2: Learner, guests and the learner middleware

**Files:**
- Create: `accounts/models.py` (`Learner`), `accounts/services.py`, `accounts/middleware.py`, `accounts/context.py`, `accounts/tasks.py`, `accounts/admin.py`, migration
- Modify: `config/settings.py` (middleware after `AuthenticationMiddleware`; context processor `accounts.context.learner`; `GUEST_IDLE_DAYS = 180`; `DAILY_GOAL_CHOICES = (10, 20, 30, 50)`; `DAILY_GOAL_DEFAULT = 20`), `config/celery.py` (beat `delete-idle-guests`, Mondays 03:30 UTC), `players/views.py`
- Test: `tests/test_learner.py`

**Interfaces:**
- Produces:
  - `Learner`: `user` (1:1 `AUTH_USER_MODEL`, null, `related_name="learner"`, CASCADE), `player` (FK `players.Player`, null, SET_NULL, `related_name="learners"`), `display_name` (40, blank), `language` ("fr"/"en", default "en"), `timezone` (64, default "UTC"), `daily_goal_xp` (default `DAILY_GOAL_DEFAULT`), `start_level` ("new"/"rules"/"club", blank), `xp_total`, `current_streak`, `longest_streak` (ints, default 0), `last_active_date` (date, null), `created_at`, `last_seen_at` (default now)
  - `Learner.is_guest -> bool` (no user); `Learner.local_date(now: datetime) -> date` (in `ZoneInfo(self.timezone)`)
  - `accounts.services.ensure_learner(request, *, timezone: str | None = None) -> Learner` — returns `request.learner`, or creates a guest, stores `session["learner_id"]` and sets `request.learner`. Language is "fr" when `request.LANGUAGE_CODE` starts with "fr", else "en". Time zone is the given one if `valid_timezone`, else "UTC".
  - `accounts.services.valid_timezone(name: str) -> bool` (membership in `zoneinfo.available_timezones()`)
  - `request.learner: Learner | None` on every request: the authenticated user's learner (created if missing), else the session guest, else `None`. A legacy session holding `player_id` becomes a guest learner linked to that `Player`, once: `learner_id` is set and `player_id` removed.
  - `players.views.current_player(request) -> Player | None` = `request.learner.player` when there is a learner, else `None`
  - Template variable `learner`
  - `accounts.tasks.delete_idle_guests() -> int` (number deleted)

- [ ] **Step 1: Write the failing tests**

```python
def test_page_view_creates_no_learner(client):
    client.get("/games/")
    assert Learner.objects.count() == 0

def test_ensure_learner_one_guest_per_session(rf_with_session):   # conftest: RequestFactory request with session + learner=None
    req = rf_with_session(HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9")
    a, b = ensure_learner(req, timezone="Mars/Base"), ensure_learner(req)
    assert a.id == b.id and a.is_guest and a.language == "fr" and a.timezone == "UTC"

def test_local_date_uses_learner_timezone():
    l = Learner(timezone="Europe/Paris")
    assert l.local_date(datetime(2026, 11, 21, 23, 30, tzinfo=UTC)) == date(2026, 11, 22)

def test_legacy_player_session_becomes_guest(client, db):
    p = Player.objects.create(chesscom_username="farel")
    s = client.session; s["player_id"] = p.id; s.save()
    client.get("/games/")
    learner = Learner.objects.get()
    assert learner.player == p and client.session["learner_id"] == learner.id and "player_id" not in client.session

def test_logged_in_user_gets_a_learner(client, django_user_model):
    u = django_user_model.objects.create_user("a@b.c", "a@b.c", "pw-Long-enough-1")
    client.force_login(u); client.get("/games/")
    assert Learner.objects.get().user == u

def test_last_seen_written_once_per_day(client, guest, mocker): ...   # two requests same day -> one UPDATE (assertNumQueries or spy)

def test_delete_idle_guests(db, django_user_model):
    old = timezone.now() - timedelta(days=181)
    Learner.objects.create(last_seen_at=old)                                              # deleted
    Learner.objects.create(last_seen_at=timezone.now() - timedelta(days=179))             # kept
    Learner.objects.create(user=django_user_model.objects.create_user("x", "x@x.x", "p"), last_seen_at=old)  # kept
    assert delete_idle_guests() == 1 and Learner.objects.count() == 2
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_learner.py -v` → FAIL (no `accounts.models.Learner`).
- [ ] **Step 3: Implement** the model, `makemigrations accounts`, the services, the middleware (update `last_seen_at` with `.update()` only when its UTC date is before today), the context processor, `current_player`, the task and its beat entry. Add the `rf_with_session` and `guest` fixtures to `conftest.py`.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` → all PASS. The existing review and importer tests still pass through the legacy-session conversion.
- [ ] **Step 5: Commit** — `git commit -m "feat: learner model, guest sessions and learner middleware"`

---

### Task 3: Sign up, log in, log out, password reset, guest merge signal

**Files:**
- Create: `accounts/forms.py`, `accounts/views.py`, `accounts/urls.py`, `accounts/signals.py`, `templates/accounts/signup.html`, `templates/accounts/login.html`, `templates/registration/password_reset_form.html`, `password_reset_done.html`, `password_reset_confirm.html`, `password_reset_complete.html`, `password_reset_email.txt`, `password_reset_subject.txt`
- Modify: `accounts/services.py`, `config/urls.py` (include `accounts.urls` at ""), `config/settings.py` (`EMAIL_BACKEND` from env, default console; `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` from env; `LOGIN_FAILURE_LIMIT = 5`; `LOGIN_FAILURE_WINDOW = 900`), `.env.example`, `locale/fr/LC_MESSAGES/django.po`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Learner`, `ensure_learner`, `request.learner`
- Produces:
  - `accounts.signals.merge_learners = Signal()` — sent with `source: Learner` (guest) and `target: Learner` (account). Tasks 10 and 11 connect receivers that move their rows.
  - `accounts.services.signup_user(request, *, email: str, password: str, display_name: str = "", timezone: str | None = None) -> User` — the lowercased email goes in `username` and `email`. A session guest gets `user` set (no row moves); otherwise a new learner is created. Logs the user in.
  - `accounts.services.login_user(request, user) -> Learner` — `django.contrib.auth.login`. If the session holds a guest different from the user's learner, it sends `merge_learners` inside `transaction.atomic()`, then deletes the guest and removes `learner_id` from the session.
  - `accounts.services.login_blocked(email: str, ip: str) -> bool`, `record_login_failure(email, ip)`, `clear_login_failures(email, ip)` — cache key `login-fail:{email}:{ip}`, limit and window from settings
  - URL names: `signup` `/signup/`, `login` `/login/`, `logout` `/logout/` (POST only), `password_reset` `/password-reset/`, `password_reset_done` `/password-reset/sent/`, `password_reset_confirm` `/password-reset/<uidb64>/<token>/`, `password_reset_complete` `/password-reset/done/`
  - After signup or login: redirect to a safe `next` (`url_has_allowed_host_and_scheme`), else `/learn/`. Logout redirects to `/`. The signup form carries a hidden `timezone` field filled by JS from `Intl.DateTimeFormat().resolvedOptions().timeZone`.
  - Form fields `email`, `password`, `display_name` (signup only). Submit labels: "Create account" on signup, "Log in" on login.
  - `conftest.py` fixtures: `account` (user `farel@example.com`, password `Chess-is-fun-42`, with a learner), `guest_client` (returns `(client, guest)` with the guest's id in the client session).

- [ ] **Step 1: Write the failing tests**

```python
def test_signup_turns_guest_into_account(client, guest_client):          # guest_client: client whose session holds a guest
    client, guest = guest_client
    r = client.post("/signup/", {"email": "Farel@Example.com", "password": "Chess-is-fun-42", "display_name": "Farel"})
    guest.refresh_from_db()
    assert r.status_code == 302 and guest.user.username == "farel@example.com" and Learner.objects.count() == 1

def test_signup_email_is_case_insensitive_unique(client, account):        # account: user farel@example.com
    r = client.post("/signup/", {"email": "FAREL@example.com", "password": "Chess-is-fun-42"})
    assert r.status_code == 200 and User.objects.count() == 1

def test_signup_rejects_weak_password(client, db):
    client.post("/signup/", {"email": "a@b.c", "password": "123"})
    assert User.objects.count() == 0

def test_login_merges_guest_and_sends_signal(guest_client, account):
    client, guest = guest_client
    seen = []
    merge_learners.connect(lambda sender, source, target, **kw: seen.append((source.id, target.id)), weak=False)
    client.post("/login/", {"email": "farel@example.com", "password": "Chess-is-fun-42"})
    assert seen == [(guest.id, account.learner.id)] and not Learner.objects.filter(id=guest.id).exists()
    assert "learner_id" not in client.session

def test_login_throttled_after_five_failures(client, account):
    for _ in range(5):
        client.post("/login/", {"email": "farel@example.com", "password": "wrong"})
    r = client.post("/login/", {"email": "farel@example.com", "password": "Chess-is-fun-42"})
    assert "Too many attempts" in r.content.decode() and "_auth_user_id" not in client.session

def test_logout_is_post_only(client, account): ...          # GET -> 405; POST -> 302 "/" and logged out
def test_password_reset_sends_email(client, account, mailoutbox): ...   # 1 mail, body contains "/password-reset/"
def test_next_must_be_safe(client, account): ...            # next=https://evil.example -> redirect "/learn/"
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_auth.py -v` → FAIL.
- [ ] **Step 3: Implement** the forms, views, services, signal and URLs. Templates extend the current `base.html` for now (Task 13 restyles them). The login error message is "Too many attempts. Try again in 15 minutes." Add the French entries and compile them.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` → all PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: email accounts with guest merge, login throttling and password reset"`

---

### Task 4: Settings, Chess.com link, account deletion; game review behind the link

**Files:**
- Modify: `accounts/forms.py`, `accounts/views.py`, `accounts/services.py`, `accounts/urls.py`, `games/views.py`, `analysis/views.py`, `players/views.py` (`set_language` also saves `learner.language`), `locale/fr/LC_MESSAGES/django.po`
- Create: `templates/accounts/settings.html`, `templates/accounts/chesscom.html`, `templates/accounts/delete.html`
- Modify tests: `tests/test_review_views.py`, `tests/test_importer.py` (signed-out redirects now go to `/profile/chess-com/`)
- Test: `tests/test_settings_and_link.py`

**Interfaces:**
- Consumes: `ensure_learner`, `games.chesscom.get_player`, `ChessComUnavailable`
- Produces:
  - `accounts.services.update_settings(learner, *, display_name: str | None = None, language: str | None = None, daily_goal_xp: int | None = None, timezone: str | None = None) -> Learner` — raises `ValueError(<field name>)` when a value is invalid
  - `accounts.services.link_chesscom(learner, username: str) -> Player` — strips and lowercases; raises `UnknownChessComUser` when `get_player` returns `None`; lets `ChessComUnavailable` through; uses `Player.get_or_create`. Several learners may link the same username.
  - `accounts.services.delete_account(request) -> None` — deletes the learner (cascade) and its user, then flushes the session. Shared `Player`, `Game` and `PositionAnalysis` rows stay.
  - URL names: `settings` `/profile/settings/`, `chesscom_link` `/profile/chess-com/` (GET form, POST link), `chesscom_unlink` `/profile/chess-com/unlink/` (POST), `delete_account` `/profile/delete/` (GET confirmation, POST), `password_change` `/profile/password/` (Django `PasswordChangeView`, accounts only; on success it redirects to `/profile/settings/` with a message). Every view except `password_change` calls `ensure_learner`, so guests can use them. Deleting an account needs its password; deleting a guest doesn't.
  - `game_list`, `review_page`, `review_status`, `start_review` redirect to `chesscom_link` when `current_player(request)` is `None`.

- [ ] **Step 1: Write the failing tests** — move the Chess.com cases from `tests/test_signin.py` here, aimed at `/profile/chess-com/`:

```python
@responses.activate
def test_link_unknown_username_shows_error(client, db):
    responses.get("https://api.chess.com/pub/player/nobody_xyz", status=404)
    r = client.post("/profile/chess-com/", {"username": "nobody_xyz"})
    assert "nobody_xyz" in r.content.decode() and Player.objects.count() == 0

@responses.activate
def test_link_is_case_insensitive(client, db):
    responses.get("https://api.chess.com/pub/player/farel", json={"username": "farel"})
    client.post("/profile/chess-com/", {"username": "Farel"}); client.post("/profile/chess-com/", {"username": "farel"})
    assert Player.objects.get().chesscom_username == "farel" and Learner.objects.get().player.chesscom_username == "farel"

def test_link_when_chesscom_down(client, db): ...           # 503 -> "Chess.com" message, no Player
def test_two_learners_can_link_same_username(db): ...
def test_settings_reject_bad_goal_and_timezone(guest_client): ...   # goal 15 and "Mars/Base" -> form errors, unchanged
def test_settings_language_sets_cookie(guest_client): ...   # language fr -> cookie django_language == "fr"
def test_delete_account_needs_password(client, account): ...        # wrong -> nothing deleted; right -> User and Learner gone
def test_delete_keeps_shared_games(client, account_with_player_and_game): ...
def test_guest_deletes_without_password(guest_client): ...
def test_password_change_needs_old_password(client, account): ...   # wrong old password -> error; right -> new password logs in
```

In `tests/test_review_views.py` and `tests/test_importer.py`, the signed-out assertions become `r.url == "/profile/chess-com/"`. Their `sign_in` helpers keep working through the legacy session conversion from Task 2.

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_settings_and_link.py tests/test_review_views.py tests/test_importer.py -v` → FAIL.
- [ ] **Step 3: Implement** the services, forms, views and templates (they extend the current `base.html`), plus the French entries.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` → all PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: learner settings, chess.com link and account deletion"`

---

### Task 5: Curriculum models and the publication workflow

**Files:**
- Create: `curriculum/models.py`, `curriculum/domain/__init__.py`, `curriculum/domain/workflow.py`, `curriculum/services.py`, `curriculum/admin.py`, migration
- Test: `tests/test_workflow.py`

**Interfaces:**
- Produces:
  - `Course(slug unique, track ∈ {"path","openings","endgames","tactics"}, order, title JSON {fr,en}, description JSON, is_active=True)`
  - `Unit(course FK related "units", order, slug, title JSON, description JSON)`, unique (course, slug)
  - `Lesson(unit FK related "lessons", order, slug unique, kind ∈ {"concept","tactic","opening","endgame"}, difficulty 1–5, side ∈ {"white","black","both"} default "both", eco blank, prerequisites M2M self non-symmetric, published_version FK LessonVersion null SET_NULL related "+", created_at)`
  - `LessonVersion(lesson FK related "versions", number, status, brief JSON, content JSON, validation_report JSON, generator JSON, error text, retry_after null, created_by FK user null, created_at, reviewed_by FK user null, reviewed_at null, published_at null)`, unique (lesson, number)
  - `VersionEvent(version FK related "events", actor FK user null = system, kind ∈ {"transition","edit"}, from_status, to_status, note, content_snapshot JSON null, at)`, ordered by (at, id)
  - `curriculum.domain.workflow`: the constants `DRAFT GENERATING VALIDATING PENDING_REVIEW APPROVED PUBLISHED REJECTED ARCHIVED` (values `"draft"` … `"archived"`), `EDITABLE = {DRAFT, PENDING_REVIEW}`, `IllegalTransition`, `check_transition(current: str, target: str) -> None`, and exactly:

```python
ALLOWED = {
    DRAFT: {GENERATING, VALIDATING}, GENERATING: {VALIDATING, DRAFT}, VALIDATING: {PENDING_REVIEW, DRAFT},
    PENDING_REVIEW: {VALIDATING, APPROVED, REJECTED}, APPROVED: {PUBLISHED}, PUBLISHED: {ARCHIVED},
    REJECTED: set(), ARCHIVED: set(),
}
```

  - `curriculum.services.new_version(lesson, actor, content: dict | None = None) -> LessonVersion` — number = last + 1; with no content, copies the latest version's; status draft; logs a transition event `"" → draft`
  - `curriculum.services.edit_content(version, content: dict, actor) -> LessonVersion` — allowed only when the status is in `EDITABLE`, else `IllegalTransition`; logs an `edit` event with `content_snapshot`; from pending review it then transitions to validating
  - `curriculum.services.transition(version, to: str, actor, note: str = "") -> LessonVersion` — `check_transition`; `actor` must be staff unless `None` (system), else `PermissionDenied`; rejecting needs a non-blank note (`ValueError("note")`); approving sets `reviewed_by` and `reviewed_at`; moving to published goes through `publish`; logs a transition event
  - `curriculum.services.publish(version, actor) -> LessonVersion` — inside `transaction.atomic()` with the lesson row locked: the previous published version goes to archived (with its event), then `lesson.published_version = version` and `published_at = now`
  - `curriculum.services.published_content(lesson) -> tuple[LessonVersion, dict] | None`

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("current,target", itertools.product(STATUSES, STATUSES))
def test_transition_table(current, target):
    if target in ALLOWED[current]:
        check_transition(current, target)
    else:
        with pytest.raises(IllegalTransition):
            check_transition(current, target)

def test_reject_needs_note(pending_version, staff): ...           # ValueError, status unchanged
def test_non_staff_cannot_approve(pending_version, account): ...  # PermissionDenied
def test_publish_archives_previous(lesson_with_v1_published, approved_v2, staff):
    publish(approved_v2, staff)
    lesson = approved_v2.lesson; lesson.refresh_from_db()
    assert lesson.published_version == approved_v2
    assert lesson.versions.get(number=1).status == "archived"
def test_every_change_is_logged(...): ...   # events' (from,to,actor) match the sequence performed
def test_edit_only_when_editable(...): ...  # approved -> IllegalTransition; pending_review -> validating
def test_new_version_copies_and_numbers(...): ...
def test_unpublished_lesson_has_no_content(lesson_with_only_pending): assert published_content(lesson) is None
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_workflow.py -v`.
- [ ] **Step 3: Implement** the models, migration, workflow, services and admin registrations (the content shown read-only in admin). Add `staff`, `lesson_factory` and version fixtures to `conftest.py`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: curriculum models and lesson publication workflow"`

---

### Task 6: Lesson schema check and localisation

**Files:**
- Create: `curriculum/domain/schema.py`, `curriculum/domain/san.py`, `tests/fixtures/lessons/valid_lesson.json` (7 steps using all five types, both languages, from the start position), `tests/test_schema.py`

**Interfaces:**
- Produces:
  - `Issue(check: str, level: Literal["fail","warn"], detail: str, step_id: str | None = None)` (frozen dataclass)
  - `check_structure(content: dict) -> list[Issue]`, `has_failures(issues) -> bool`
  - `player_move_indexes(step: dict) -> list[int]` — indexes into a `play_line`'s `moves` that `side` plays, from the side to move in `fen`
  - `allowed_san(step: dict) -> set[str]` — the SAN of every move the step contains, each computed in its own position
  - `localize(content: dict, lang: str) -> dict` — the same shape, with every `{fr,en}` replaced by the string in that language; French texts go through `san.frenchify`
  - `curriculum.domain.san.frenchify(text: str) -> str` — rewrites only the tokens `analysis.ai.MOVE_RE` matches: the leading piece letter and the promotion piece, K→R Q→D R→T B→F N→C; castling untouched
  - Check codes: `schema`, `language`, `duplicate_id`, `illegal_position`, `illegal_move`, `unknown_move_in_text`, `engine_numbers` (fail); `text_too_long` (> 280), `step_count` (outside 6–15) (warn)
- Content format (T = `{"fr": str, "en": str}`, both non-empty). Top level: `schema: 1`; `meta` (`title` T, `description` T, `objectives` [T] with at least 1, `difficulty` 1–5, `estimated_minutes` 1–15, `orientation` "white"/"black"); optional `completion.min_accuracy` (0–1); `steps`. Every step has `id` (matches `^[a-z0-9_-]{1,20}$`, unique), `type`, and a legal `fen`; `arrows` [[from, to]], `highlights` [square] and `skills` [str] are optional.

| Type | Required fields | Optional |
| --- | --- | --- |
| `explain` | `text` T | – |
| `show_moves` | `moves` [{`uci`, `caption` T}] (≥ 1, legal in sequence) | `text` T |
| `find_move` | `prompt` T, `accept` [uci] (≥ 1), `correct` T, `hint` T | `also_good` [{`uci`, `note` T}], `wrong` [{`uci`, `feedback` T}] |
| `choice` | `question` T, `options` 2–4 of {`text` T} or {`uci`}, `answer` (index), `explanation` T, `hint` T | – |
| `play_line` | `prompt` T, `side`, `moves` [uci] (≥ 2, legal in sequence), `hint` T | `also_accept` {"<index>": [uci]}, `notes` {"<index>": T}, `srs` {`line_key`} |

  Meta texts may name any move that any step allows.

- [ ] **Step 1: Write the failing tests**

```python
def test_valid_fixture_has_no_issues(valid): assert check_structure(valid) == []
def test_missing_english_fails(valid): ...                 # drop steps[1].prompt.en -> Issue("language","fail",…,"s2")
def test_illegal_fen_and_move(valid): ...                  # bad fen -> illegal_position; accept "e2e5" -> illegal_move
def test_play_line_illegal_at_index_three(valid): ...      # detail mentions index 3
def test_duplicate_step_id(valid): ...
def test_text_names_unknown_move(valid): ...               # "Qh5" -> unknown_move_in_text; "d5" (a square) passes; "Cf3" in fr text fails
@pytest.mark.parametrize("text,bad", [("+1.3", True), ("45 cp", True), ("-0,8", True), ("3 pieces", False), ("move 12", False)])
def test_engine_numbers(valid, text, bad): ...
def test_warnings_only(valid): ...                         # 300-char text -> text_too_long warn; 4 steps -> step_count warn
def test_choice_answer_out_of_range(valid): ...            # schema fail
def test_player_move_indexes():
    assert player_move_indexes({"fen": START, "side": "white", "moves": ["e2e4","e7e5","g1f3","b8c6","f1c4"]}) == [0, 2, 4]
@pytest.mark.parametrize("en,fr", [("Nf3", "Cf3"), ("Kxe2", "Rxe2"), ("e8=Q", "e8=D"), ("O-O", "O-O"), ("exd5", "exd5"), ("Rd1+", "Td1+")])
def test_frenchify(en, fr): assert frenchify(f"Play {en} now") == f"Play {fr} now"
def test_localize_flattens_and_keeps_answers(valid): ...   # fr strings; accept lists unchanged
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_schema.py -v`.
- [ ] **Step 3: Implement** `schema.py` and `san.py` with python-chess, with no Django imports except `analysis.ai.MOVE_RE`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: lesson content schema check and localisation"`

---

### Task 7: Engine checks and the validation job

**Files:**
- Create: `curriculum/validation.py`, `curriculum/tasks.py`
- Modify: `curriculum/services.py`
- Test: `tests/test_validation.py` (real Stockfish, depth 8)

**Interfaces:**
- Consumes: `analysis.engine.analyse`, `analysis.grading.grade_move/wp_of/mover_wp_after`, `check_structure`, `transition`
- Produces:
  - `curriculum.validation.grade(board: chess.Board, uci: str) -> str` — `grade_move(wp_of(before), mover_wp_after(after), is_best)` where `is_best` means the move is the first move of the engine's best line
  - `curriculum.validation.engine_issues(content: dict) -> list[Issue]`
    - `find_move`: every `accept` and `also_good` move must grade best or good, else `answer_refuted` (fail). A `wrong` move that grades best or good gives `wrong_move_is_fine` (warn).
    - `play_line`: each player move and each `also_accept` move. Inaccuracy gives `inaccurate_line_move` (warn); mistake or blunder gives `line_move_refuted` (fail).
  - `curriculum.tasks.validate_version(version_id: int) -> str` (Celery `shared_task`, routed to `content`) — does nothing unless the status is validating. Engine checks run only when there are no structure failures. It stores `validation_report = {"issues": [asdict…], "checked_at": iso, "engine_depth": ENGINE_DEPTH}`. A failure moves the version to draft (actor `None`, note "validation failed"); otherwise to pending review. Returns the new status.
  - `curriculum.services.request_validation(version, actor) -> LessonVersion` = `transition(version, VALIDATING, actor)`. Every transition to validating schedules `validate_version.delay(id)` with `transaction.on_commit`.

- [ ] **Step 1: Write the failing tests** (wrap with `django_capture_on_commit_callbacks(execute=True)` where a transition is made)

```python
def test_blunder_as_answer_is_refuted(): ...      # Scholar's-mate-defence position, accept a queen-hanging move -> answer_refuted
def test_mate_in_one_answer_passes(): ...         # back-rank mate position, accept the mate -> no issues
def test_wrong_move_that_is_fine_warns(): ...
def test_valid_lesson_reaches_pending_review(draft_version_of_valid_fixture, staff, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        request_validation(draft_version_of_valid_fixture, staff)
    v = refresh(draft_version_of_valid_fixture)
    assert v.status == "pending_review" and not [i for i in v.validation_report["issues"] if i["level"] == "fail"]
def test_failure_returns_to_draft_with_report(...): ...
def test_structure_failure_skips_engine(mocker, ...): ...   # spy on analysis.engine.analyse: not called
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_validation.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: engine checks and lesson validation job"`

---

### Task 8: Studio, lesson import and the three seed lessons

**Files:**
- Create: `curriculum/studio.py`, `curriculum/urls.py`, `templates/studio/lesson_list.html`, `templates/studio/version.html`, `curriculum/management/__init__.py`, `curriculum/management/commands/__init__.py`, `curriculum/management/commands/import_lessons.py`, `curriculum/seed/foundation.json`
- Modify: `config/urls.py` (`curriculum.urls` at `studio/`)
- Test: `tests/test_studio.py`, `tests/test_seed.py`

**Interfaces:**
- Consumes: workflow services, `request_validation`, `check_structure`
- Produces:
  - `staff_only` decorator: anonymous users are redirected to `/login/?next=…`; signed-in non-staff get 403
  - URL names: `studio_lessons` `/studio/`, `studio_version` `/studio/versions/<int:pk>/`, `studio_version_content` POST `/studio/versions/<pk>/content` (field `content`), `studio_version_transition` POST `/studio/versions/<pk>/transition` (fields `to`, `note`), `studio_new_version` POST `/studio/lessons/<slug>/versions/new`
  - The lesson list is grouped by course and unit, with each lesson's published version number and latest version (number and status).
  - The version page shows the status, a report table (level, step, check, detail), the history (time, actor email or "system", from → to, note), a JSON textarea (read-only unless the status is editable), and the buttons that fit the status. Draft: Save, Validate. Pending review: Save (re-validates), Approve, Reject (note). Approved: Publish. Any status: a Preview link to `/lessons/<slug>/?version=<pk>`.
  - `python manage.py import_lessons <path>` — the file holds `{"courses": [{slug, track, order, title, description?, units: [{slug, order, title, description?, lessons: [{slug, order, kind, difficulty, side?, prerequisites?: [slug], content}]}]}]}`. It upserts by slug, creates a new draft only when the content differs from the latest version, and prints `lessons: <created> created, <updated> updated; drafts: <n>`.
  - `curriculum/seed/foundation.json`: course `fundamentals` (track `path`, title Fondamentaux / Fundamentals), unit `basics` (Les bases / The basics), and lessons `piece-values` (concept), `checks-captures-threats` (concept) and `mate-in-one` (tactic). Each has 6 to 10 steps in both languages, with English SAN in the texts. Together they use all five step types; at least one `play_line` has two or more player moves; `mate-in-one` accepts every mating move in each of its positions. All three must pass validation with no failure.

- [ ] **Step 1: Write the failing tests**

```python
def test_studio_access(client, account, staff): ...   # anon -> 302 /login/?next=/studio/ ; account -> 403 ; staff -> 200
def test_invalid_json_not_saved(staff_client, draft_version):
    r = staff_client.post(f"/studio/versions/{draft_version.pk}/content", {"content": "{bad"}, follow=True)
    assert "Not valid JSON" in r.content.decode() and refresh(draft_version).content == draft_version.content
def test_reject_without_note_is_refused(staff_client, pending_version): ...
def test_approve_then_publish(staff_client, pending_version): ...     # lesson.published_version set, events logged
def test_import_is_idempotent(tmp_path, db): ...                      # second run: 0 created, 0 drafts
def test_seed_lessons_pass_validation(db, staff, django_capture_on_commit_callbacks):
    call_command("import_lessons", "curriculum/seed/foundation.json")
    for v in LessonVersion.objects.all():
        with django_capture_on_commit_callbacks(execute=True):
            request_validation(v, staff)
    assert set(LessonVersion.objects.values_list("status", flat=True)) == {"pending_review"}
    types = {s["type"] for v in LessonVersion.objects.all() for s in v.content["steps"]}
    assert types == {"explain", "show_moves", "find_move", "choice", "play_line"}
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_studio.py tests/test_seed.py -v`.
- [ ] **Step 3: Implement** the views, templates (plain Bootstrap), command and seed file. Write the seed lessons as real teaching content and check them with the validator as you go.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: lesson studio, import command and foundation seed lessons"`

---

### Task 9: Server-side lesson scoring

**Files:**
- Create: `learning/domain/__init__.py`, `learning/domain/scoring.py`
- Test: `tests/test_scoring.py` (no database)

**Interfaces:**
- Consumes: `curriculum.domain.schema.player_move_indexes`
- Produces:
  - `InvalidResult(ValueError)`
  - `StepScore(step_id, step_type, items: int, correct_items: int, cleared: bool, tries: list, hints, ms: int, skills: list[str])`, with property `correct = items > 0 and correct_items == items`
  - `Scored(steps: list[StepScore], items: int, correct_items: int, accuracy: float, completed: bool)`
  - `score_attempt(content: dict, submitted: list[dict]) -> Scored`
- Rules. Each submitted entry is `{"id", "tries", "hints", "ms"}`.
  - `explain` and `show_moves` score nothing (0 items) and are ignored if sent.
  - `find_move`: `tries` holds 1 to 10 UCI moves, each legal in `fen`. Right = `accept` ∪ `also_good` moves. Correct = first try right and `hints == 0`; cleared = last try right.
  - `choice`: `tries` holds 1 to 10 option indexes, each in range. Correct = first try is `answer` and `hints == 0`; cleared = last try is `answer`.
  - `play_line`: `tries` holds one list per player move (`len == len(player_move_indexes)`), each with 1 to 10 UCI moves legal in the position after `moves[:i]`. `hints` is a list of ints with the same length. Right at index *i* = `{moves[i]}` ∪ `also_accept[str(i)]`. A move is correct when its first try is right and its hint count is 0; the step is cleared when every list ends with a right move.
  - `InvalidResult` for: an unknown id, a duplicate id, more than 50 entries, wrong types, a size outside the limits, an illegal move.
  - A scored step that wasn't submitted counts its items as wrong and not cleared.
  - `accuracy = correct_items / items`, rounded to 4 decimals (1.0 when there are no items). `completed` = every scored step cleared and `accuracy >= content.get("completion", {}).get("min_accuracy", 0)`.

- [ ] **Step 1: Write the failing tests** (on `tests/fixtures/lessons/valid_lesson.json`; `perfect(valid)` builds a perfect submission)

```python
def test_perfect_run(valid): s = score_attempt(valid, perfect(valid)); assert s.accuracy == 1.0 and s.completed
def test_wrong_first_try_still_completes(valid): ...       # find_move tries ["d2d3", "e2e4"] -> completed, accuracy == (items-1)/items
def test_also_good_counts_as_correct(valid): ...
def test_hint_makes_item_incorrect(valid): ...
def test_play_line_alternative_from_also_accept(valid): ...
def test_missing_scored_step_not_completed(valid): ...
def test_min_accuracy_blocks_completion(valid): ...        # min_accuracy 0.8, one wrong of 4 items -> completed False
@pytest.mark.parametrize("mutate", [illegal_move, unknown_id, duplicate_id, wrong_line_count, eleven_tries, tries_not_list, fifty_one_entries])
def test_hostile_payloads_raise(valid, mutate):
    with pytest.raises(InvalidResult):
        score_attempt(valid, mutate(perfect(valid)))
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_scoring.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: server-side lesson scoring"`

---

### Task 10: Attempts, progress, unlocking and merging progress

**Files:**
- Create: `learning/models.py`, `learning/domain/unlock.py`, `learning/services.py`, `learning/admin.py`, migration
- Modify: `learning/apps.py` (`ready()` connects `on_merge` to `merge_learners`)
- Test: `tests/test_unlock.py` (no database), `tests/test_attempts.py`

**Interfaces:**
- Consumes: `Lesson`, `published_content`, `merge_learners`
- Produces:
  - `LessonAttempt(id UUID pk default uuid4, learner FK CASCADE related "attempts", lesson FK CASCADE, version FK LessonVersion PROTECT, started_at, finished_at null, completed null, accuracy null, xp_awarded=0, result JSON null)`
  - `StepResult(attempt FK CASCADE related "steps", step_id, step_type, correct, cleared, tries JSON, hints JSON, ms, skills JSON)`
  - `LessonProgress(learner FK CASCADE related "progress", lesson FK CASCADE, first_completed_at null, best_accuracy=0.0, completions=0, last_attempt_at null)`, unique (learner, lesson). Whether replay XP was already earned today is read from the XP ledger in Task 11, not stored here.
  - `LessonNode(slug, track, unit_index: int, position: int, prerequisites: frozenset[str])`
  - `lesson_states(nodes: list[LessonNode], completed: set[str], start_level: str) -> dict[str, str]` returns "done", "current", "open" or "locked":
    - Path track, in `position` order: lesson *k* unlocks when *k* = 0 or lesson *k* − 1 is done, or when its `unit_index` is opened by the start level ("rules" opens 0; "club" opens 0 and 1).
    - Other tracks are open unless a prerequisite is missing.
    - Prerequisites must be done on every track.
    - "current" is the first unlocked path lesson not done.
  - `next_up(states: dict[str, str], nodes, best_accuracy: dict[str, float]) -> str | None` — the current lesson; else the done lesson with the lowest best accuracy under `REVISIT_BELOW = 0.7`; else `None`
  - `learning.services.path_nodes() -> list[LessonNode]` (only lessons of active courses with a published version, ordered by course, unit and lesson), `states_for(learner | None) -> dict[str, str]`, `set_start_level(learner, level: str) -> str | None` (`ValueError` for an unknown level; returns `next_up`)
  - `learning.services.start_attempt(learner, lesson, now) -> LessonAttempt` — raises `NotPublished` or `Locked`; pins `lesson.published_version`
  - `learning.services.on_merge(sender, source, target, **kw)` — moves attempts to the target. For progress on a lesson both have: best accuracy is the max, `first_completed_at` the earliest non-null, completions the sum, `last_attempt_at` the max. The source's start level is used only when the target's is blank.

- [ ] **Step 1: Write the failing tests**

```python
def test_new_learner_path(nodes3): assert lesson_states(nodes3, set(), "new") == {"a": "current", "b": "locked", "c": "locked"}
def test_completing_unlocks_next(nodes3): assert lesson_states(nodes3, {"a"}, "new") == {"a": "done", "b": "current", "c": "locked"}
def test_rules_opens_unit_one(nodes_two_units): ...   # every unit-0 lesson open (first one current), unit 1 locked
def test_club_opens_two_units(nodes_two_units): ...
def test_prerequisite_locks_catalog_lesson(...): ...
def test_next_up_revisits_weakest(...): ...            # all done, best {a: 0.9, b: 0.5, c: 0.65} -> "b"
def test_start_attempt_locked_and_unpublished(db, ...): ...
def test_attempt_pins_version(db, ...): ...            # start, publish v2, attempt.version is still v1
def test_merge_combines_progress(db, ...):             # Review Focus 3
    # target best 0.6 (1 completion), source best 0.9 (2 completions) on the same lesson
    merge_learners.send(sender=Learner, source=src, target=tgt)
    p = LessonProgress.objects.get(learner=tgt)
    assert (p.best_accuracy, p.completions) == (0.9, 3) and src.attempts.count() == 0
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_unlock.py tests/test_attempts.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: lesson attempts, progress, unlocking and progress merge"`

---

### Task 11: XP, streaks, levels and achievements

**Files:**
- Create: `gamification/models.py`, `gamification/domain/__init__.py`, `gamification/domain/xp.py`, `streak.py`, `levels.py`, `achievements.py`, `gamification/services.py`, `gamification/admin.py`, migration
- Modify: `gamification/apps.py` (connects `on_merge`), `config/settings.py` (`XP_LESSON_FIRST = 10`, `XP_ACCURACY_BONUS = 5`, `XP_ACCURACY_BONUS_MIN = 0.9`, `XP_LESSON_REPLAY = 3`)
- Test: `tests/test_xp_rules.py`, `tests/test_streak.py` (no database), `tests/test_award.py`

**Interfaces:**
- Consumes: `Learner.local_date`, `LessonAttempt`, `merge_learners`
- Produces:
  - `XpEvent(learner FK CASCADE related "xp_events", amount, reason ∈ {"lesson_first","accuracy_bonus","lesson_replay","review"}, lesson FK null, attempt FK null CASCADE, local_date, created_at)`, unique (attempt, reason) when `attempt` is set
  - `LearnerAchievement(learner FK CASCADE, code, earned_at)`, unique (learner, code)
  - `xp.XpRules` (frozen; `from_settings()`), `xp.XpContext(completed, accuracy, first_completion, bonus_earned_before, replay_xp_today)`, `xp.xp_for_attempt(ctx, rules) -> list[tuple[str, int]]`:
    - not completed → `[]`
    - first completion → `lesson_first`
    - otherwise → `lesson_replay`, unless replay XP was already earned today
    - in both completed cases, add `accuracy_bonus` when accuracy ≥ 0.9 and the bonus wasn't earned before
  - `streak.Streak(current, longest, last_active: date | None)`, `advance(s, day) -> Streak`, `displayed(s, today) -> int`, `from_dates(days) -> Streak` (rules in Global Constraints)
  - `levels.level_for(xp: int) -> int`, `levels.level_floor(level: int) -> int` (`25 * n * (n - 1)`)
  - `achievements.ProgressStats(lessons_completed, units_completed, perfect_lessons)`, `achievements.earned(stats, current_streak: int, have: set[str]) -> list[str]` over the codes `first_lesson`, `first_unit`, `streak_3`, `streak_7`, `streak_30`, `perfect_10`, in that order
  - `gamification.services.award_for_attempt(learner, attempt, *, completed: bool, accuracy: float, first_completion: bool, stats: ProgressStats, now: datetime) -> dict`. It runs in the caller's transaction and locks the learner row. Earlier bonus and today's replay XP for `attempt.lesson` come from the ledger. It writes the `XpEvent` rows with `local_date = learner.local_date(now)`. When the total is above 0, it updates `xp_total` and advances the streak. It creates the new achievements. Returns `{"xp": {"awarded", "total", "level", "level_up"}, "streak": {"current", "longest", "today_done"}, "daily_goal": {"target", "today_xp"}, "achievements": [code]}`.
  - `gamification.services.summary(learner, now) -> dict` — `{"xp_total", "level", "level_floor", "next_level_at", "streak": {…}, "daily_goal": {…}}`
  - `gamification.services.on_merge(sender, source, target, **kw)` — moves the XP events, dropping the source's `lesson_first` and `accuracy_bonus` events for a lesson where the target already has that same reason. Moves achievements the target lacks. Recomputes the target's `xp_total` from the ledger and its streak with `from_dates` over the ledger's local dates.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("ctx,expected", [
    (XpContext(True, 0.85, True, False, False), [("lesson_first", 10)]),
    (XpContext(True, 0.95, True, False, False), [("lesson_first", 10), ("accuracy_bonus", 5)]),
    (XpContext(True, 0.70, False, False, False), [("lesson_replay", 3)]),
    (XpContext(True, 0.70, False, False, True), []),
    (XpContext(True, 0.95, False, False, True), [("accuracy_bonus", 5)]),
    (XpContext(False, 1.0, False, False, False), []),
])
def test_xp_rules(ctx, expected): assert xp_for_attempt(ctx, XpRules()) == expected

def test_streak_across_local_midnight_same_utc_day():          # Review Focus 1
    paris = ZoneInfo("Europe/Paris")
    d1 = datetime(2026, 11, 21, 23, 30, tzinfo=paris).date(); d2 = datetime(2026, 11, 22, 0, 10, tzinfo=paris).date()
    assert advance(advance(Streak(0, 0, None), d1), d2).current == 2
def test_streak_across_dst_change(): ...                       # 2027-03-27 -> 2027-03-28 in Europe/Paris: +1
def test_gap_resets_and_display_shows_zero(): ...
@pytest.mark.parametrize("xp,level", [(0, 1), (49, 1), (50, 2), (149, 2), (150, 3), (300, 4), (500, 5)])
def test_levels(xp, level): assert level_for(xp) == level
def test_achievements_once(): ...

def test_award_first_completion(db, paris_learner, attempt): ...   # 0.95 -> awarded 15, total 15, streak 1, today_xp 15
def test_duplicate_reason_for_attempt_is_rejected(db, ...): ...    # IntegrityError
def test_merge_no_double_first_completion(db, ...):                # Review Focus 3
    # target: lesson L first (10) on D1. source: L first + bonus (15) and M first (10) on D2.
    merge_learners.send(sender=Learner, source=src, target=tgt); tgt.refresh_from_db()
    assert tgt.xp_total == 25 and tgt.current_streak == 2
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_xp_rules.py tests/test_streak.py tests/test_award.py -v`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: xp ledger, streaks, levels and achievements"`

---

### Task 12: Finishing attempts and the JSON API

**Files:**
- Create: `learning/api.py`, `learning/urls_api.py`
- Modify: `learning/services.py`, `config/urls.py` (`api/v1/` → `learning.urls_api`), `config/settings.py` (`ATTEMPT_EXPIRY_HOURS = 24`, `API_MAX_BODY = 65536`), `locale/fr/LC_MESSAGES/django.po`
- Test: `tests/test_finish.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `score_attempt`, `InvalidResult`, `lesson_states`, `path_nodes`, `award_for_attempt`, `summary`, `ensure_learner`, `update_settings`, `set_start_level`, `localize`
- Produces:
  - `learning.services.progress_stats(learner) -> ProgressStats`:
    - `lessons_completed` = progress rows with `first_completed_at` set
    - `units_completed` = units with at least one published lesson, every published lesson done
    - `perfect_lessons` = progress rows with `best_accuracy == 1.0`
  - `learning.services.finish_attempt(learner, attempt_id, steps: list[dict], now) -> dict`. Inside `transaction.atomic()`:
    - Lock the attempt owned by the learner (`LessonAttempt.DoesNotExist` otherwise).
    - If it's already finished, return the stored `result`. If it started more than 24 h ago, raise `Expired`.
    - Score it against `attempt.version.content`; `InvalidResult` propagates before any write.
    - Write the `StepResult` rows and update `LessonProgress`.
    - `first_completion` = completed now with no earlier `first_completed_at`.
    - `unlocked` = path slugs locked before and not locked after.
    - Call `award_for_attempt`, then store `result`, `finished_at`, `completed`, `accuracy`, `xp_awarded`.
    - Returns `{"completed", "accuracy", "xp", "streak", "daily_goal", "unlocked", "achievements", "new_cards": 0}`.
  - Endpoints (plain `JsonResponse`; JSON body over `API_MAX_BODY` → 400 `bad_request`):

| Method and path | Body | 2xx response | Errors |
| --- | --- | --- | --- |
| `GET /api/v1/me` | – | `{"learner": null}` or `{"learner": {is_guest, display_name, language, timezone, start_level, **summary}}` | – |
| `POST /api/v1/me/start-level` | `{level, timezone?}` | `{"next_lesson": slug \| null}` (creates the guest) | 400 `bad_request` |
| `POST /api/v1/me/settings` | `{display_name?, language?, daily_goal_xp?, timezone?}` | same as `GET /me` | 400 `bad_request` |
| `GET /api/v1/lessons/<slug>` | – (`?version=<id>` honoured for staff only) | `{"lesson": {slug, kind, title, objectives, minutes, difficulty, orientation}, "version_id", "completion", "steps"}` in the learner's language | 403 `locked`, 404 `not_found` |
| `POST /api/v1/lessons/<slug>/attempts` | `{timezone?}` | 201 `{"attempt_id", "version_id"}` | 403 `locked`, 404 `not_found` |
| `POST /api/v1/attempts/<uuid>/finish` | `{"steps": [...]}` | 200 result | 400 `invalid_result`/`bad_request`, 404 `not_found`, 410 `expired` |

- [ ] **Step 1: Write the failing tests**

```python
def test_finish_awards_and_unlocks(db, learner, two_lesson_path): ...   # perfect run on lesson 1 -> xp.awarded 15, unlocked == ["lesson-2"]
def test_finish_is_idempotent(db, learner, attempt):                    # Review Focus 2
    first = finish_attempt(learner, attempt.id, perfect(attempt), NOW)
    assert finish_attempt(learner, attempt.id, perfect(attempt), NOW) == first
    assert XpEvent.objects.count() == 2
def test_finish_expires_after_24h(db, ...): ...                         # Expired
def test_finish_scores_pinned_version(db, ...):                         # Review Focus 4
    # v1 accepts e2e4; start attempt; publish v2 accepting d2d4 only; finish with e2e4
    assert finish_attempt(learner, attempt.id, steps_with("e2e4"), NOW)["completed"] is True
def test_hostile_finish_writes_nothing(client_with_attempt):            # Review Focus 5
    for body in (illegal_move_body, '{"steps": 5}', "not json", "x" * 70_000):
        r = client.post(finish_url, body, content_type="application/json")
        assert r.status_code == 400
    assert StepResult.objects.count() == 0 and XpEvent.objects.count() == 0
def test_me_before_any_action(client, db): assert client.get("/api/v1/me").json() == {"learner": None}
def test_start_level_creates_guest_and_returns_first_lesson(client, two_lesson_path): ...
def test_lesson_json_in_french(client_fr, ...): ...       # a step text with "Nf3" arrives as "Cf3"
def test_locked_and_unpublished(client, ...): ...         # 403 locked ; 404 not_found
def test_other_learners_attempt_is_404(client, ...): ...
def test_csrf_enforced(db, ...): ...                      # Client(enforce_csrf_checks=True) POST without token -> 403
def test_staff_preview_param_ignored_for_learners(...): ...
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_finish.py tests/test_api.py -v`.
- [ ] **Step 3: Implement** the service, the endpoints, a `json_error(code, message, status)` helper, and translated error messages.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` → all PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: finish attempts and the learning json api"`

---

### Task 13: Design shell, landing page and level picker

**Files:**
- Create: `static/css/chessmind.css`, `static/fonts/nunito/nunito-latin-wght-normal.woff2`, `static/fonts/nunito/OFL.txt` (both from the npm package `@fontsource-variable/nunito`, pinned version, latin subset), `templates/partials/nav.html`, `templates/learning/landing.html`, `templates/learning/start.html`, `learning/views.py`, `learning/urls.py`
- Modify: `templates/base.html` (rewrite), `config/urls.py` (`learning.urls` at ""), `players/urls.py` and `players/views.py` (remove `signin`/`signout`; keep `set_language` at `/language/`), all existing templates (new shell blocks), `locale/fr/LC_MESSAGES/django.po`
- Delete: `templates/signin.html`, `tests/test_signin.py` (its Chess.com cases moved to `tests/test_settings_and_link.py` in Task 4)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `request.learner`, `summary`, `POST /api/v1/me/start-level`
- Produces:
  - `chessmind.css` design tokens (starting values from the reference screens): `--cm-ink #1f2a22`, `--cm-muted #5b6b60`, `--cm-bg #ffffff`, `--cm-surface #f6f7f3`, `--cm-border #e3e6df`, `--cm-green #7ccf45`, `--cm-green-dark #5aa52c`, `--cm-green-tint #eef7e6`, `--cm-purple #7350e6`, `--cm-purple-dark #5634c9`, `--cm-purple-tint #efeafe`, `--cm-orange #f5a524`, `--cm-orange-tint #fdf0dd`, `--cm-red #e5484d`, `--cm-red-tint #fdecec`, `--cm-radius 16px`, `--cm-font "Nunito", system-ui, sans-serif`
  - Components: `.cm-btn` (`--primary` green, `--purple`, `--secondary` white) with a 4 px darker bottom edge that flattens on `:active`; `.cm-card`, `.cm-tabs`, `.cm-stat`, `.cm-row` (with a chevron), `.cm-label` (uppercase, letter-spaced); minimum touch size 44 px
  - Shell (`base.html`, blocks `title`, `head`, `content`, `aside`, `scripts`): a left sidebar ≥ 992 px with the "ChessMind" wordmark and nav Learn `/learn/`, Analysis `/games/`, Profile `/profile/`; a bottom tab bar under 992 px; a header with the streak flame (`summary.streak.current`, when there is a learner), the FR/EN switch and an avatar or Log in link. Bootstrap CSS stays loaded for its grid and utilities.
  - `learning.views.landing` at `/` (name `landing`): a learner with an account or any progress is redirected to `/learn/`. Otherwise the page shows the hero "Learn chess, one short lesson a day", a Start button to `/start/`, and "I already have an account" to `/login/`. It creates no learner.
  - `learning.views.start` at `/start/` (name `start`): three buttons `data-level="new|rules|club"`. A small inline module posts `{level, timezone}` to the start-level endpoint, then goes to `/lessons/<next_lesson>/`, or to `/learn/` when it's null.

- [ ] **Step 1: Write the failing tests**

```python
def test_landing_for_new_visitor(client, db):
    r = client.get("/")
    assert r.status_code == 200 and 'href="/start/"' in r.content.decode() and Learner.objects.count() == 0
def test_landing_redirects_account(client, account): ...   # 302 "/learn/"
def test_start_page_has_three_levels(client, db): ...      # data-level="new", "rules", "club"
def test_shell_nav_and_font(client, db): ...               # /learn/, /games/, /profile/ links; chessmind.css linked; css has "@font-face" and "Nunito"
def test_landing_in_french(client, db): ...                # Accept-Language fr -> the French hero text
def test_streak_in_header(client, learner_with_streak): ...
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_pages.py -v`.
- [ ] **Step 3: Implement** the shell, CSS, font, the landing and start pages, the removal of the old sign-in, and the move of existing pages into the shell. The review page keeps loading `review.js` and the cm-chessboard CSS. Add the French entries.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` → all PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: chessmind design shell, landing page and level picker"`

---

### Task 14: Path page and profile

**Files:**
- Create: `templates/learning/path.html`, `templates/learning/profile.html`
- Modify: `learning/views.py`, `learning/urls.py`, `static/css/chessmind.css`, `locale/fr/LC_MESSAGES/django.po`
- Test: `tests/test_path_profile.py`

**Interfaces:**
- Consumes: `states_for`, `path_nodes`, `next_up`, `summary`, `progress_stats`, `LessonProgress`
- Produces:
  - `learning.views.path` at `/learn/` (name `path`). With no learner, it redirects to `/start/`.
    - Per unit of the path course: a header card with the course and unit name, "`k / n`" lessons done and the next lesson's title.
    - Zig-zag nodes (CSS offset by index mod 4) with the classes `is-done`, `is-current` (a "Start" bubble linking to `/lessons/<slug>/`), `is-open` and `is-locked` (a lock icon and no link). A coach bubble greets the player.
    - Aside: a streak card (displayed current streak and the record) and a daily goal ring (`today_xp / target`).
    - The Openings and Endgames tabs don't appear in this milestone.
  - `learning.views.profile` at `/profile/` (name `profile`), with `?tab=performance|mastery|settings`:
    - Header: initial avatar, display name or "Guest", "Level N · X XP".
    - Performance: stat cards for streak (current, record), level and XP, lessons completed, and average best accuracy per course track.
    - Mastery: one row per unit with `k / n` and a progress bar.
    - Settings: links to `/profile/settings/`, `/profile/chess-com/`, `/profile/password/` (accounts only) and `/profile/delete/`.
    - Rows: "My level" → `/start/`, "Connect Chess.com" → `/profile/chess-com/`, "My game reviews" → `/games/`.
    - A guest sees the "Keep your progress" panel with Create account (`/signup/?next=/profile/`) and "I already have an account" (`/login/?next=/profile/`).

- [ ] **Step 1: Write the failing tests**

```python
def test_path_without_learner_redirects(client, db): assert client.get("/learn/").url == "/start/"
def test_path_node_states(client_with_first_lesson_done, three_lesson_path):
    html = client.get("/learn/").content.decode()
    assert 'class="node is-done"' in html and 'class="node is-current"' in html and 'class="node is-locked"' in html
    assert "1 / 3" in html and 'href="/lessons/lesson-3/"' not in html
def test_streak_card_shows_zero_after_missed_day(...): ...
def test_profile_guest_panel(guest_client): ...            # "/signup/?next=/profile/" present
def test_profile_account_has_no_guest_panel(...): ...
def test_profile_performance_numbers(...): ...             # "15 XP", "Level 1", lessons completed 1
def test_profile_mastery_unit_progress(...): ...           # "1 / 3"
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_path_profile.py -v`.
- [ ] **Step 3: Implement**, with the French entries.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: learning path page and profile"`

---

### Task 15: The lesson player and end-to-end tests

**Files:**
- Create: `templates/learning/lesson.html`, `static/js/player/main.js`, `queue.js`, `board.js`, `ui.js`, `san.js`, `static/js/player/steps/explain.js`, `show_moves.js`, `find_move.js`, `choice.js`, `play_line.js`, `requirements-dev.txt`, `Dockerfile.e2e`, `e2e/conftest.py`, `e2e/test_player.py`, `e2e/fixtures/e2e_lesson.json`
- Modify: `learning/views.py`, `learning/urls.py`, `static/css/chessmind.css` (player styles), `docker-compose.yml` (`e2e` service), `README.md`, `locale/fr/LC_MESSAGES/django.po`
- Test: `tests/test_lesson_page.py`, `e2e/test_player.py`

**Interfaces:**
- Consumes: the lesson, attempt and finish endpoints; cm-chessboard (`Chessboard`, `Arrows`, `Markers`, `PromotionDialog`, `Accessibility` extensions) and chess.js from `static/vendor/`
- Produces:
  - `learning.views.lesson_page` at `/lessons/<slug>/` (name `lesson`):
    - Unknown or unpublished → 404. Locked → redirect to `/learn/` with a message.
    - A staff user with `?version=<pk>` gets preview mode on any status. For anyone else the parameter is ignored.
    - Renders the full-screen `lesson.html` with a JSON config block: `lessonUrl`, `attemptsUrl`, `finishUrl` (with `{id}`), `preview`, `versionId`, `isGuest`, `signupUrl` (`/signup/?next=/profile/`), `pathUrl`, `csrfToken`, `assets`, `lang`, `i18n`.
  - The player (ES modules, no jQuery needed):
    - `main.js` starts the attempt (sending the time zone) unless in preview, runs a `StepQueue` and builds the finish body in the Task 12 shape.
    - Finish retries 3 times (1 s, 3 s, 9 s). If all fail, it keeps the body in `localStorage["chessmind:pending:<attempt_id>"]` (inside try/catch) and resends it on the next player load.
    - It then shows the summary: XP earned (plus level-up), accuracy %, total time, streak, achievements, Continue → `/learn/`. Guests also get "Create an account to keep your progress". In preview: "Preview: nothing was saved."
  - `queue.js`: `StepQueue(steps)` with `next()`, `requeue(step)` (once per step), and `total`/`done` for the progress bar.
  - `board.js`: `createBoard(el, {orientation, assetsUrl})` returning `setFen(fen, animate)`, `play(uci)`, `waitForMove(fen) -> Promise<uci>` (legal moves only, through chess.js), `arrows(list)`, `clearArrows()`, `mark(squares, kind)`.
  - `ui.js`: progress bar, combo counter (first-try correct in a row), prompt, coach bubble, move chips, hint button, and a feedback bar `feedback({ok, title, text}) -> Promise` that resolves on Continue. Each outcome has an icon and a title as well as its colour, and the bar is `aria-live="polite"`.
  - `san.js`: `localSan(san, lang)` with the K→R, Q→D, R→T, B→F, N→C mapping.
  - Step modules `run(step, ctx) -> Promise<{tries, hints, ms}>`:
    - `explain`: show the text, then Continue.
    - `show_moves`: play each move with its caption, then Continue.
    - `find_move`: a right move gives an "Excellent!" bar with `correct`. An `also_good` move shows its note, then the board plays `accept[0]`. A wrong move gives the bar with the matching `wrong.feedback` or "Not quite". After two wrong tries, an arrow shows `accept[0]` and the player must play it. If the first try was wrong, the step is requeued. Hint shows `hint` and marks the from-square.
    - `choice`: the same rules with option buttons, each carrying `data-option="<index>"`. Options with `uci` are shown as SAN.
    - `play_line`: the app plays the other side after 400 ms; each player move is checked. An `also_accept` move shows "That also works. We'll follow the lesson's line." and the board plays the main move. A wrong move shakes the board and the player retries; after two wrong tries an arrow shows the move. `notes[i]` appears in the coach bubble. The step is requeued if any move was wrong.
  - `e2e` compose service: `build: {context: ., dockerfile: Dockerfile.e2e}` (`FROM mcr.microsoft.com/playwright/python:v1.49.0-noble`, then installs `requirements.txt` and `requirements-dev.txt`), `profiles: ["e2e"]`, `env_file: .env`, `environment: {DJANGO_ALLOW_ASYNC_UNSAFE: "true"}`, `volumes: [".:/app"]`, `depends_on: [db, redis]`, `command: pytest e2e -v`.

- [ ] **Step 1: Write the failing tests**

`tests/test_lesson_page.py`:

```python
def test_lesson_page_config(client, published_lesson): ...      # 200; config has preview false and the finish URL with {id}
def test_locked_lesson_redirects(client, locked_lesson): ...     # 302 "/learn/"
def test_staff_preview(staff_client, pending_version): ...       # ?version=pk -> preview true
def test_preview_param_ignored_for_learners(client, published_lesson, pending_version): ...
```

`e2e/test_player.py` (390×844 viewport; `e2e/fixtures/e2e_lesson.json` is published as the first path lesson. It has three steps: `explain`; `find_move` from the start position with `accept ["e2e4"]` and `wrong [{"uci": "e2e3", feedback "Too timid" / "Trop timide"}]`; `choice` with `answer: 1`. The coach text names `Nf3`.)

```python
def test_guest_finishes_lesson_and_keeps_xp_after_signup(page, live_server, e2e_lesson):
    page.goto(live_server.url + "/"); page.get_by_role("link", name="Start").click()
    page.locator('[data-level="new"]').click()
    page.get_by_role("button", name="Continue").click()
    page.locator('[data-square="e2"]').click(); page.locator('[data-square="e4"]').click()
    page.get_by_role("button", name="Continue").click()
    page.locator('[data-option="1"]').click(); page.get_by_role("button", name="Continue").click()
    expect(page.get_by_text("+15 XP")).to_be_visible()
    page.get_by_role("link", name="Create an account").click()
    page.fill('[name="email"]', "new@example.com"); page.fill('[name="password"]', "Chess-is-fun-42")
    page.get_by_role("button", name="Create account").click()
    expect(page.get_by_text("15 XP")).to_be_visible()      # profile header
def test_wrong_move_feedback_and_step_returns(page, live_server, e2e_lesson): ...   # "Too timid" visible; the find_move prompt shows twice; summary "50%" and "+10 XP"
def test_french_player_sees_french_notation(page_fr, live_server, e2e_lesson): ...  # coach text shows "Cf3"
```

- [ ] **Step 2: Run to verify failure** — `docker compose run --rm test pytest tests/test_lesson_page.py -v` and `docker compose --profile e2e run --rm e2e` → FAIL.
- [ ] **Step 3: Implement** the view, the template, the modules, the styles (board on top at full width on phones, prompt and chips under it, the feedback bar as a bottom sheet with a full-width Continue), the e2e service and the README section "End-to-end tests". Add the French entries.
- [ ] **Step 4: Run** `docker compose run --rm test pytest -v` and `docker compose --profile e2e run --rm e2e` → all PASS.
- [ ] **Step 5: Milestone check.** Import the seed (`import_lessons curriculum/seed/foundation.json`), validate and publish the three lessons in the studio. Then, on a phone-sized browser window: start as a guest, finish `piece-values`, sign up, and confirm the XP and the streak on the profile.
- [ ] **Step 6: Commit** — `git commit -m "feat: lesson player with end-to-end tests"`
