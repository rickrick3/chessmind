import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import Course, Lesson, Unit
from curriculum.services import new_version


class Command(BaseCommand):
    help = "Import courses, units and lessons from a JSON file. Upserts by slug; new content becomes a new draft."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, path, **options):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"cannot read {path}: {exc}") from exc
        created = updated = drafts = 0
        with transaction.atomic():
            prerequisites = []
            for c in data.get("courses", []):
                course, _ = Course.objects.update_or_create(slug=c["slug"], defaults={
                    "track": c["track"], "order": c.get("order", 0), "title": c["title"],
                    "description": c.get("description", {})})
                for u in c.get("units", []):
                    unit, _ = Unit.objects.update_or_create(course=course, slug=u["slug"], defaults={
                        "order": u.get("order", 0), "title": u["title"], "description": u.get("description", {})})
                    for item in u.get("lessons", []):
                        lesson, was_created = Lesson.objects.update_or_create(slug=item["slug"], defaults={
                            "unit": unit, "order": item.get("order", 0), "kind": item["kind"],
                            "difficulty": item.get("difficulty", 1), "side": item.get("side", "both"),
                            "eco": item.get("eco", "")})
                        created += was_created
                        updated += not was_created
                        latest = lesson.versions.order_by("-number").first()
                        if latest is None or latest.content != item["content"]:
                            new_version(lesson, None, content=item["content"])
                            drafts += 1
                        prerequisites.append((lesson, item.get("prerequisites", [])))
            for lesson, slugs in prerequisites:
                lesson.prerequisites.set(Lesson.objects.filter(slug__in=slugs))
        self.stdout.write(f"lessons: {created} created, {updated} updated; drafts: {drafts}")
