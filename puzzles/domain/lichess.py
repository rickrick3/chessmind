"""One row of the Lichess puzzle file (database.lichess.org, CC0). Pure: no database.

Columns: PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags, DailyDate.
FEN is the position before the opponent's move; the first move in Moves is the opponent's, the second starts the
solution, and the solution ends on the learner's move.
"""
from dataclasses import dataclass

import chess

LOWEST_BAND, TOP = 400, 2800  # bands of 100 points from 400 to 2,799


@dataclass(frozen=True)
class PuzzleRow:
    lichess_id: str
    fen: str
    moves: tuple[str, ...]
    rating: int
    rating_deviation: int
    popularity: int
    plays: int
    themes: tuple[str, ...]
    opening_tags: tuple[str, ...]
    game_url: str
    side: str
    start_fen: str


def band(rating: int) -> int | None:
    return rating // 100 * 100 if LOWEST_BAND <= rating < TOP else None


def derive(fen: str, moves: list[str]) -> tuple[str, str]:
    """(the learner's side, the position after the opponent's first move)."""
    board = chess.Board(fen)
    board.push_uci(moves[0])
    return ("white" if board.turn == chess.WHITE else "black"), board.fen()


def _legal_line(fen: str, moves: list[str]) -> bool:
    board = chess.Board(fen)
    if not board.is_valid():
        return False
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return False
        board.push(move)
    return True


def parse_row(row: dict[str, str]) -> PuzzleRow | None:
    """The row as a PuzzleRow, or None when anything about it is unusable."""
    try:
        moves = (row.get("Moves") or "").split()
        if len(moves) < 2 or len(moves) % 2:
            return None
        fen = row["FEN"].strip()
        if not _legal_line(fen, moves):
            return None
        side, start_fen = derive(fen, moves)
        return PuzzleRow(
            lichess_id=row["PuzzleId"].strip(), fen=fen, moves=tuple(moves), rating=int(row["Rating"]),
            rating_deviation=int(row["RatingDeviation"]), popularity=int(row["Popularity"]),
            plays=int(row["NbPlays"]), themes=tuple((row.get("Themes") or "").split()),
            opening_tags=tuple((row.get("OpeningTags") or "").split()), game_url=(row.get("GameUrl") or "").strip(),
            side=side, start_fen=start_fen)
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
