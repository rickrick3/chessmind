from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Learner


@shared_task
def delete_idle_guests() -> int:
    """Delete guests not seen for GUEST_IDLE_DAYS. Returns how many learners were deleted."""
    cutoff = timezone.now() - timedelta(days=settings.GUEST_IDLE_DAYS)
    _total, per_model = Learner.objects.filter(user__isnull=True, last_seen_at__lt=cutoff).delete()
    return per_model.get("accounts.Learner", 0)
