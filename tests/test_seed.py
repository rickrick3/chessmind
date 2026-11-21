"""The three hand-made foundation lessons must pass validation (real Stockfish, depth 8)."""
import pytest
from django.core.management import call_command

from curriculum.models import Lesson, LessonVersion
from curriculum.services import request_validation

pytestmark = pytest.mark.django_db


def test_seed_lessons_pass_validation(staff, django_capture_on_commit_callbacks):
    call_command("import_lessons", "curriculum/seed/foundation.json")
    for v in LessonVersion.objects.all():
        with django_capture_on_commit_callbacks(execute=True):
            request_validation(v, staff)
    versions = list(LessonVersion.objects.all())
    fails = {v.lesson.slug: [i for i in v.validation_report["issues"] if i["level"] == "fail"] for v in versions}
    assert {v.status for v in versions} == {"pending_review"}, fails
    types = {s["type"] for v in versions for s in v.content["steps"]}
    assert types == {"explain", "show_moves", "find_move", "choice", "play_line"}
    assert list(Lesson.objects.order_by("order").values_list("slug", flat=True)) == [
        "piece-values", "checks-captures-threats", "mate-in-one"]
