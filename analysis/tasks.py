from celery import shared_task

from . import explain
from .ai import ProviderError, QuotaExceeded
from .facts import FactPacket
from .models import MoveExplanation


@shared_task
def upgrade_pending_explanations() -> int:
    """Replace template stand-ins with AI text, oldest first, until the quota runs out. Returns how many."""
    provider = explain.get_provider()
    done = 0
    for e in MoveExplanation.objects.filter(needs_ai=True).order_by("created_at", "id"):
        p = FactPacket(**e.facts)
        try:
            text = explain.ai_text(provider, p, e.language)
        except QuotaExceeded:
            break
        except ProviderError:
            continue
        if text:
            e.text, e.source, e.model, e.needs_ai = text, "ai", provider.name, False
            e.save(update_fields=["text", "source", "model", "needs_ai"])
            done += 1
    return done
