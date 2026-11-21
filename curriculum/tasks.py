from dataclasses import asdict

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .domain.schema import check_structure, has_failures
from .domain.workflow import DRAFT, PENDING_REVIEW, VALIDATING
from .models import LessonVersion
from .services import transition
from .validation import engine_issues


@shared_task
def validate_version(version_id: int) -> str:
    """Check a version in 'validating': structure first, then the engine. Moves it on and returns its status."""
    version = LessonVersion.objects.get(pk=version_id)
    if version.status != VALIDATING:
        return version.status
    try:
        issues = check_structure(version.content)
        if not has_failures(issues):
            issues += engine_issues(version.content)
        error = ""
    except Exception as exc:  # noqa: BLE001 — an engine failure must not leave the version stuck in validating
        issues, error = [], f"validation crashed: {exc}"[:500]
    version.validation_report = {"issues": [asdict(i) for i in issues], "checked_at": timezone.now().isoformat(),
                                 "engine_depth": settings.ENGINE_DEPTH}
    version.error = error
    version.save(update_fields=["validation_report", "error"])
    if error or has_failures(issues):
        transition(version, DRAFT, None, note="validation failed")
    else:
        transition(version, PENDING_REVIEW, None)
    return version.status
