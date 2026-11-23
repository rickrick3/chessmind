"""The skill vocabulary: areas, Lichess themes, old lesson tags. Pure, no database."""
import pytest

from skills.domain.areas import (
    ALL_THEMES, AREAS, MOTIF_THEMES, NOT_DIAGNOSED, canonical_tags, diagnosable, lesson_step_areas, puzzle_areas,
    unknown_tags,
)
from skills.labels import AREA_LABELS, THEME_LABELS, area_label, theme_label


def test_theme_sets_partition_the_lichess_list():
    assert len(ALL_THEMES) == 73 and not (MOTIF_THEMES & NOT_DIAGNOSED)
    assert diagnosable("fork") and not diagnosable("middlegame")


def test_every_puzzle_feeds_tactics():
    assert puzzle_areas(["mate", "mateIn2", "middlegame", "short"]) == {"tactics"}
    assert puzzle_areas(["long", "defensiveMove", "rookEndgame"]) == {"tactics", "calculation", "defense", "endgames"}


def test_aliases_and_unknown_tags():
    assert canonical_tags(["defence", "back-rank", "cct", "queen", "nonsense", "defence"]) == [
        "defense", "backRankMate", "tactics"]
    assert unknown_tags(["defence", "nonsense", "fork"]) == ["nonsense"]


@pytest.mark.parametrize("tags,kind,areas", [
    (["fork"], "concept", {"tactics"}), (["intermezzo"], "concept", {"tactics", "calculation"}),
    (["queen"], "tactic", {"tactics"}), ([], "concept", set()), (["openings"], "concept", {"openings"}),
    (["threats"], "concept", {"defense"}), ([], "endgame", {"endgames"}), (["endgame"], "concept", {"endgames"}),
])
def test_lesson_step_areas(tags, kind, areas):
    assert lesson_step_areas(tags, kind) == areas


def test_labels_cover_everything():
    assert set(THEME_LABELS) == ALL_THEMES and set(AREA_LABELS) == set(AREAS)
    assert theme_label("mateIn2") == "Mate in 2" and area_label("defense") == "Defence"
    assert theme_label("nope") == "nope"
