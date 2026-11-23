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


def test_stop_mate_accepts_every_good_defence():
    """The step asks the learner to stop Qxf7#. A move that stops it and the engine rates good must not be
    called wrong (the hint itself suggests defending f7 once more)."""
    import json
    from pathlib import Path

    import chess

    from curriculum.validation import grade

    seed = json.loads(Path("curriculum/seed/foundation.json").read_text(encoding="utf-8"))
    lessons = {lesson["slug"]: lesson for lesson in seed["courses"][0]["units"][0]["lessons"]}
    step = next(s for s in lessons["checks-captures-threats"]["content"]["steps"] if s["id"] == "stop-mate")
    board = chess.Board(step["fen"])

    def stops_mate(move):
        after = board.copy()
        after.push(move)
        for reply in list(after.legal_moves):
            after.push(reply)
            mate = after.is_checkmate()
            after.pop()
            if mate:
                return False
        return True

    accepted = set(step["accept"]) | {g["uci"] for g in step.get("also_good", [])}
    good_defences = {m.uci() for m in board.legal_moves if stops_mate(m) and grade(board, m.uci()) in ("best", "good")}
    assert good_defences and good_defences <= accepted, good_defences - accepted
