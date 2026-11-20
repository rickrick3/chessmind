import pytest
from google.genai import errors as genai_errors

from analysis.ai import (GeminiProvider, NoneProvider, ProviderError, QuotaExceeded, build_prompt, get_provider,
                         validate_text)
from analysis.phrases import template_text


def test_validate_rejects_invented_move(packet_blunder):
    assert not validate_text("Better was Qh5 winning.", packet_blunder)


def test_validate_accepts_packet_moves(packet_blunder):
    assert validate_text(f"Better was {packet_blunder.best_san}, then O-O.", packet_blunder)


def test_validate_ignores_square_names_and_check_marks(packet_blunder):
    assert validate_text("The queen on d5 is lost after Bxd5+.", packet_blunder)


def test_validate_rejects_empty(packet_blunder):
    assert not validate_text("  ", packet_blunder)


def test_template_text_always_validates(packet_blunder):
    assert validate_text(template_text(packet_blunder, "en", "full"), packet_blunder)
    assert validate_text(template_text(packet_blunder, "fr", "full"), packet_blunder)


def test_prompt_contains_facts_and_rules(packet_blunder):
    pr = build_prompt(packet_blunder, "fr")
    assert packet_blunder.best_san in pr
    assert "1300" in pr and "only the moves listed" in pr and "French" in pr


def test_gemini_429_raises_quota(mocker, packet_blunder):
    provider = GeminiProvider(model="m", api_key="k")
    mocker.patch.object(provider, "_generate",
                        side_effect=genai_errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}))
    with pytest.raises(QuotaExceeded):
        provider.explain(packet_blunder, "en")


def test_gemini_server_error_raises_provider_error(mocker, packet_blunder):
    provider = GeminiProvider(model="m", api_key="k")
    mocker.patch.object(provider, "_generate", side_effect=genai_errors.ServerError(503, {"error": {}}))
    with pytest.raises(ProviderError):
        provider.explain(packet_blunder, "en")


def test_gemini_returns_stripped_text(mocker, packet_blunder):
    provider = GeminiProvider(model="m", api_key="k")
    mocker.patch.object(provider, "_generate", return_value="  Be7 was safer.  ")
    assert provider.explain(packet_blunder, "en") == "Be7 was safer."


def test_none_provider_raises_quota(packet_blunder):
    with pytest.raises(QuotaExceeded):
        NoneProvider().explain(packet_blunder, "en")


def test_get_provider_follows_settings(settings):
    settings.AI_PROVIDER = "none"
    assert isinstance(get_provider(), NoneProvider)
    settings.AI_PROVIDER = "gemini"
    settings.GEMINI_API_KEY = "k"
    assert isinstance(get_provider(), GeminiProvider)


def test_gemini_without_key_behaves_like_none(settings):
    settings.AI_PROVIDER = "gemini"
    settings.GEMINI_API_KEY = ""
    assert isinstance(get_provider(), NoneProvider)
