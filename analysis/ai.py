"""AI providers for key-moment explanations, and the check that keeps them honest."""
import re
from typing import Protocol

from django.conf import settings

# Moves that can't be confused with a square name: piece moves (English letters, plus French C/F/T/D so
# French notation is caught), pawn captures, promotions, castling. Bare squares like "d5" are ignored,
# because the text uses them to name squares ("the queen on d5").
MOVE_RE = re.compile(r"(?<![\w-])(?:O-O-O|O-O|[KQRBNCFTD][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8](?:=[QRBN])?"
                     r"|[a-h][18]=[QRBN])[+#]?(?![\w-])")
LANG_NAMES = {"fr": "French", "en": "English"}


class QuotaExceeded(Exception):
    """The provider's free quota is used up (or no AI is configured)."""


class ProviderError(Exception):
    """The provider failed for another reason (timeout, server error)."""


class Provider(Protocol):
    name: str

    def explain(self, p, lang: str) -> str: ...


def validate_text(text: str, p) -> bool:
    if not text or not text.strip():
        return False
    allowed = {m.rstrip("+#") for m in p.allowed_san()}
    return all(tok.rstrip("+#") in allowed for tok in MOVE_RE.findall(text))


def build_prompt(p, lang: str) -> str:
    opp = "black" if p.mover == "white" else "white"
    facts = [
        f"Move played by {p.mover}: {p.san} (move number {(p.ply + 1) // 2})",
        f"Grade: {p.grade}",
        f"{p.mover.capitalize()}'s winning chances: {p.wp_before:.0f}% before, {p.wp_after:.0f}% after",
        f"Best move instead: {p.best_san}" if p.best_san else "This was the engine's best move",
        f"Engine's best line from before the move: {' '.join(p.best_line_san)}",
        f"{opp.capitalize()}'s strongest replies now: {', '.join(p.replies_san)}",
        f"Gives check: {'yes' if p.is_check else 'no'}",
        f"Captures: {p.captured or 'nothing'}",
        f"{p.mover.capitalize()}'s pieces left undefended and attacked: {', '.join(p.hanging_after) or 'none'}",
        f"Enemy pieces the moved piece attacks at once: {', '.join(p.forks) or 'none'}",
        f"Material balance for {p.mover} (pawn=1): {p.material_diff:+d}",
    ]
    return (
        "You are a friendly chess coach. Your reader is rated about 1300 on Chess.com.\n"
        f"Write at most 5 short sentences in {LANG_NAMES.get(lang, 'English')}, plain words, no engine numbers "
        "other than the winning chances.\n"
        "Explain why this move was a problem, what the better move does and why, and what the opponent can now do.\n"
        "Mention only the moves listed below, written exactly as listed (English letters K Q R B N, even in French). "
        "Do not invent any other move or line.\n\n" + "\n".join(f"- {f}" for f in facts)
    )


class NoneProvider:
    name = "none"

    def explain(self, p, lang: str) -> str:
        raise QuotaExceeded("no AI provider configured")


class GeminiProvider:
    name = "gemini"

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self._client = None

    def _generate(self, prompt: str) -> str:
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=20_000))
        return self._client.models.generate_content(model=self.model, contents=prompt).text or ""

    def explain(self, p, lang: str) -> str:
        from google.genai import errors

        try:
            return self._generate(build_prompt(p, lang)).strip()
        except errors.ClientError as exc:
            if exc.code == 429:
                raise QuotaExceeded(str(exc)) from exc
            raise ProviderError(str(exc)) from exc
        except Exception as exc:  # server errors, timeouts, network
            raise ProviderError(str(exc)) from exc


def get_provider() -> Provider:
    if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return GeminiProvider(model=settings.GEMINI_MODEL, api_key=settings.GEMINI_API_KEY)
    return NoneProvider()
