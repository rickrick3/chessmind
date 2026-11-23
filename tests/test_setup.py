import chess.engine


def test_settings_values(settings):
    assert settings.LIMIT_REVIEWS_PER_WEEK == 5
    assert settings.LIMIT_EXPLAINS_PER_WEEK == 20
    assert [c for c, _ in settings.LANGUAGES] == ["fr", "en"]
    assert settings.AI_PROVIDER in ("gemini", "none")


def test_foundation_settings(settings):
    assert settings.SESSION_COOKIE_AGE == 365 * 24 * 3600
    assert settings.LOGIN_URL == "/login/"
    assert settings.CELERY_TASK_ROUTES["curriculum.tasks.*"] == {"queue": "content"}
    assert {"django.contrib.admin", "accounts", "curriculum", "learning", "gamification"} <= set(settings.INSTALLED_APPS)
    assert "django.contrib.auth.middleware.AuthenticationMiddleware" in settings.MIDDLEWARE


def test_admin_asks_for_login(client, db):
    r = client.get("/admin/")
    assert r.status_code == 302 and r.url.startswith("/admin/login/")


def test_stockfish_binary_runs(settings):
    eng = chess.engine.SimpleEngine.popen_uci(settings.ENGINE_PATH)
    assert "Stockfish" in eng.id["name"]
    eng.quit()
