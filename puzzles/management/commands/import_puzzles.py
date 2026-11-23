"""Import a sample of the Lichess puzzle database: a fixed number of good puzzles per 100-point rating band.

    python manage.py import_puzzles lichess_db_puzzle.csv.zst [--per-band 2000]

A .zst file is read through the `zstd` command-line tool. Puzzles left out of a new import are deactivated, never
deleted, so attempts that point at them stay valid. The same file and seed always give the same sample.
"""
import contextlib
import csv
import io
import random
import shutil
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from puzzles.domain.lichess import LOWEST_BAND, TOP, band, parse_row
from puzzles.models import Puzzle

UPDATE_FIELDS = ["fen", "moves", "rating", "rating_deviation", "popularity", "plays", "themes", "opening_tags",
                 "game_url", "side", "start_fen", "is_active", "imported_at"]


@contextlib.contextmanager
def _open_text(path: Path):
    if path.suffix != ".zst":
        with path.open(encoding="utf-8", newline="") as f:
            yield f
        return
    if shutil.which("zstd") is None:
        raise CommandError("Reading a .zst file needs the zstd tool. Install it, or decompress the file first "
                           "(zstd -d lichess_db_puzzle.csv.zst) and import the .csv.")
    proc = subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE)
    try:
        yield io.TextIOWrapper(proc.stdout, encoding="utf-8", newline="")
    finally:
        proc.stdout.close()
        if proc.wait() != 0:
            raise CommandError(f"zstd could not read {path}")


class Command(BaseCommand):
    help = "Import a rating-balanced sample of the Lichess puzzle database (CSV or .csv.zst)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--per-band", type=int, default=2000)
        parser.add_argument("--min-popularity", type=int, default=80)
        parser.add_argument("--min-plays", type=int, default=300)
        parser.add_argument("--max-rd", type=int, default=90)
        parser.add_argument("--seed", type=int, default=1)

    def handle(self, *args, path, per_band, min_popularity, min_plays, max_rd, seed, **options):
        source = Path(path)
        if not source.exists():
            raise CommandError(f"No file at {source}")
        rng = random.Random(seed)
        chosen: dict[int, list] = {}
        seen: dict[int, int] = {}
        with _open_text(source) as f:
            for raw in csv.DictReader(f):
                try:
                    if (int(raw["Popularity"]) < min_popularity or int(raw["NbPlays"]) < min_plays
                            or int(raw["RatingDeviation"]) > max_rd):
                        continue
                    b = band(int(raw["Rating"]))
                except (KeyError, ValueError, TypeError):
                    continue
                if b is None:
                    continue
                row = parse_row(raw)
                if row is None:
                    continue
                # Reservoir sampling per band: every eligible puzzle of the band has the same chance.
                seen[b] = seen.get(b, 0) + 1
                sample = chosen.setdefault(b, [])
                if len(sample) < per_band:
                    sample.append(row)
                else:
                    j = rng.randrange(seen[b])
                    if j < per_band:
                        sample[j] = row

        now = timezone.now()
        puzzles = [Puzzle(lichess_id=r.lichess_id, fen=r.fen, moves=list(r.moves), rating=r.rating,
                          rating_deviation=r.rating_deviation, popularity=r.popularity, plays=r.plays,
                          themes=list(r.themes), opening_tags=list(r.opening_tags), game_url=r.game_url,
                          side=r.side, start_fen=r.start_fen, is_active=True, imported_at=now)
                   for b in sorted(chosen) for r in chosen[b]]
        with transaction.atomic():
            Puzzle.objects.update(is_active=False)
            Puzzle.objects.bulk_create(puzzles, update_conflicts=True, unique_fields=["lichess_id"],
                                       update_fields=UPDATE_FIELDS, batch_size=1000)

        for b in range(LOWEST_BAND, TOP, 100):
            count = len(chosen.get(b, []))
            line = f"{b}: {count}"
            self.stdout.write(self.style.WARNING(line + f" (fewer than {per_band})") if count < per_band else line)
        inactive = Puzzle.objects.filter(is_active=False).count()
        self.stdout.write(self.style.SUCCESS(f"Imported {len(puzzles)} puzzles; {inactive} inactive."))
