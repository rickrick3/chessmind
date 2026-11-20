import chess.engine


def test_settings_values(settings):
    assert settings.LIMIT_REVIEWS_PER_WEEK == 5
    assert settings.LIMIT_EXPLAINS_PER_WEEK == 20
    assert [c for c, _ in settings.LANGUAGES] == ["fr", "en"]
    assert settings.AI_PROVIDER in ("gemini", "none")


def test_stockfish_binary_runs(settings):
    eng = chess.engine.SimpleEngine.popen_uci(settings.ENGINE_PATH)
    assert "Stockfish" in eng.id["name"]
    eng.quit()
