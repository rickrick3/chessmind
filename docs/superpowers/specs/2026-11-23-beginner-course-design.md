# ChessMind · Beginner course (Fundamentals path): Design

**Date:** 2026-11-23 · **Status:** approved by Farel on 2026-11-23 (short design)

## Why

ChessMind has three lessons. Farel expects a full chess course. The content pipeline (Gemini drafts at scale) is a
later project; this one gives learners a real course now: Claude writes the lessons, they pass the existing checks,
and Farel reviews and publishes each one in the studio, as he decided for AI-written lessons.

## Approaches

- **A. Claude writes a first full beginner course now — chosen by Farel.** About 30 lessons in the existing format,
  imported as drafts, validated by the schema check and Stockfish, reviewed and published by Farel.
- B. Build the Gemini content pipeline first — scales to hundreds of lessons but delays any new lesson.

## What gets built

Six new units in the existing `fundamentals` course (track `path`), around the existing unit `basics`:

| # | Unit (slug) | Lessons |
|---|---|---|
| 1 | How the pieces move (`pieces`) | Rook and bishop · Queen and king · Knight · Pawn (promotion, en passant) · Check, castling, checkmate and stalemate |
| 2 | The basics (`basics`, existing) | Piece values · Checks, captures, threats · Mate in one |
| 3 | Winning material (`material`) | Free pieces (counting attackers and defenders) · Forks · Pins · Skewers · Discovered attacks |
| 4 | Staying safe (`safety`) | What does my opponent threaten? · Saving a piece · Three ways out of check · Back-rank safety · Trading when you're ahead |
| 5 | Checkmate patterns (`mates`) | Ladder mate with two rooks · Supported queen mate · King and queen against king · King and rook against king · Mate in two |
| 6 | Opening principles (`opening-principles`) | Take the centre · Develop your pieces · Castle early · Don't bring the queen out too early · Your first opening: the Italian Game |
| 7 | First endgames (`first-endgames`) | The square rule · An active king · The opposition · King and pawn against king · Cutting off the king with a rook |

**Each lesson:** about 5 minutes, 6 to 10 steps mixing explain, show_moves, find_move, choice and play_line; French
and English (English SAN in both); skill tags from the skills vocabulary (area keys and Lichess themes) so lessons
feed the skill profile; passes `check_structure` with no failure and the Stockfish checks with no failure.

**Start levels:** "New to chess" starts at unit 1. "Knows the rules" starts at unit 2, with unit 1 open for review.
"Club player" starts at unit 3, with units 1 and 2 open. The next lesson ("current") for a level is the first open,
unfinished path lesson from its start unit on.

## Constraints

- Existing lesson schema (`curriculum/domain/schema.py`), texts ≤ 280 characters, no engine numbers, no move in a
  text that the lesson doesn't contain.
- Lessons reach learners only after Farel publishes them in `/studio/`. Nothing is auto-published.
- The three existing lessons keep their slugs (learner progress is keyed by slug).

## Left to the builder

The exact positions, steps and wording of each lesson; lesson order within a unit; difficulty values (1–2 for units
1–4, 2–3 for units 5–7).
