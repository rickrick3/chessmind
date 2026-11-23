"""Create lesson evidence for lesson attempts finished before the skill profile existed. Safe to run again."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Learner
from learning.models import LessonAttempt
from skills.services import recompute, record_lesson_evidence


class Command(BaseCommand):
    help = "Backfill skill evidence from earlier lesson attempts (the first finished attempt of each lesson)."

    def handle(self, *args, **options):
        created = 0
        now = timezone.now()
        learners = Learner.objects.filter(attempts__finished_at__isnull=False).distinct()
        for learner in learners:
            with transaction.atomic():
                firsts: dict[int, LessonAttempt] = {}
                for attempt in (LessonAttempt.objects.filter(learner=learner, finished_at__isnull=False)
                                .select_related("lesson").order_by("finished_at")):
                    firsts.setdefault(attempt.lesson_id, attempt)
                for attempt in firsts.values():
                    created += record_lesson_evidence(attempt, list(attempt.steps.all()),
                                                      learner.local_date(attempt.finished_at))
                recompute(learner, now)
        self.stdout.write(self.style.SUCCESS(f"Evidence rows created: {created}"))
