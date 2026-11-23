"""The Lichess puzzle file: parsing one row, rating bands, and the import command."""
import csv
import shutil
import subprocess
from pathlib import Path

import pytest
from django.core.management import call_command

from puzzles.domain.lichess import band, parse_row
from puzzles.models import Puzzle, PuzzleAttempt
from tests.puzzle_data import MATE2

SAMPLE = Path(__file__).parent / "fixtures" / "puzzles" / "sample.csv"


def _rows() -> list[dict]:
    with SAMPLE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def csv_row(puzzle_id: str) -> dict:
    return dict(next(r for r in _rows() if r["PuzzleId"] == puzzle_id))


def write_csv(tmp_path, rows) -> Path:
    path = tmp_path / "puzzles.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(_rows()[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_parse_row_derives_side_and_start():
    row = parse_row(csv_row("pMate2"))
    assert row.side == "white" and row.start_fen == MATE2["start_fen"]
    assert row.moves == tuple(MATE2["moves"]) and row.themes == ("mate", "mateIn2", "middlegame", "short")
    assert row.opening_tags == ("Italian_Game", "Italian_Game_Classical_Variation")


@pytest.mark.parametrize("moves", ["c7c6 a1h8", "c7c6", "c7c6 a1a8 h8g8", ""])
def test_parse_row_rejects_illegal_single_and_odd(moves):
    assert parse_row({**csv_row("pAlt1"), "Moves": moves}) is None


def test_parse_row_rejects_bad_numbers_and_fen():
    assert parse_row({**csv_row("pAlt1"), "Rating": "abc"}) is None
    assert parse_row({**csv_row("pAlt1"), "FEN": "not a fen"}) is None


def test_band_limits():
    assert (band(399), band(400), band(2799), band(2800)) == (None, 400, 2700, None)


def test_import_filters(db):
    call_command("import_puzzles", str(SAMPLE))
    assert set(Puzzle.objects.values_list("lichess_id", flat=True)) == {"pMate2", "pAlt1", "pPromo"}
    p = Puzzle.objects.get(lichess_id="pMate2")
    assert (p.rating, p.side, p.is_active) == (1760, "white", True)
    assert p.moves == MATE2["moves"] and p.start_fen == MATE2["start_fen"]


@pytest.mark.skipif(shutil.which("zstd") is None, reason="the zstd tool is not installed in this image")
def test_import_reads_zst(db, tmp_path):
    path = tmp_path / "sample.csv.zst"
    subprocess.run(["zstd", "-q", "-o", str(path), str(SAMPLE)], check=True)
    call_command("import_puzzles", str(path))
    assert Puzzle.objects.count() == 3


def test_import_caps_each_band_deterministically(db, tmp_path):
    path = write_csv(tmp_path, [{**csv_row("pMate2"), "PuzzleId": f"m{i}", "Rating": "1750"} for i in range(10)])
    call_command("import_puzzles", str(path), "--per-band", "4")
    first = set(Puzzle.objects.filter(is_active=True).values_list("lichess_id", flat=True))
    call_command("import_puzzles", str(path), "--per-band", "4")
    assert len(first) == 4
    assert set(Puzzle.objects.filter(is_active=True).values_list("lichess_id", flat=True)) == first


def test_reimport_deactivates_missing_and_keeps_attempted(db, tmp_path, guest):
    call_command("import_puzzles", str(SAMPLE))
    PuzzleAttempt.objects.create(learner=guest, puzzle=Puzzle.objects.get(lichess_id="pAlt1"), mode="rated")
    path = write_csv(tmp_path, [csv_row("pMate2"), csv_row("pPromo")])
    call_command("import_puzzles", str(path))
    alt = Puzzle.objects.get(lichess_id="pAlt1")
    assert alt.is_active is False and Puzzle.objects.filter(is_active=True).count() == 2
