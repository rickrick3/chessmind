"""Explanations, cache first: templates for ordinary moves, AI (checked) for key moments."""
from dataclasses import asdict

from django.db import IntegrityError, transaction

from .ai import ProviderError, QuotaExceeded, get_provider, validate_text
from .models import MoveExplanation
from .phrases import template_text


def ai_text(provider, p, lang: str) -> str | None:
    """Ask once, retry once if the text mentions a move that isn't in the facts. None = use the template."""
    for _attempt in range(2):
        text = provider.explain(p, lang)
        if validate_text(text, p):
            return text
    return None


def get_explanation(position, move_uci: str, p, lang: str) -> MoveExplanation:
    depth = "full" if p.key_moment else "short"
    key = {"position": position, "move_uci": move_uci, "language": lang, "depth": depth}
    hit = MoveExplanation.objects.filter(**key).first()
    if hit:
        return hit
    fields = {"text": template_text(p, lang, depth), "source": "template", "model": "", "needs_ai": False,
              "facts": asdict(p)}
    if depth == "full":
        provider = get_provider()
        try:
            text = ai_text(provider, p, lang)
        except (QuotaExceeded, ProviderError):
            text = None
        if text:
            fields.update(text=text, source="ai", model=provider.name)
        else:
            fields["needs_ai"] = True
    try:
        with transaction.atomic():
            return MoveExplanation.objects.create(**key, **fields)
    except IntegrityError:  # another worker stored it first
        return MoveExplanation.objects.get(**key)
