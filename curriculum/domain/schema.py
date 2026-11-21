"""The lesson document (schema 1): checks that need no engine, and the learner-language view of it.

Every text is {"fr": str, "en": str}, written with English SAN in both languages.
"""
import re
from dataclasses import dataclass
from typing import Literal

import chess

from analysis.ai import MOVE_RE

from .san import frenchify

LANGS = ("fr", "en")
STEP_TYPES = ("explain", "show_moves", "find_move", "choice", "play_line")
ID_RE = re.compile(r"^[a-z0-9_-]{1,20}$")
MAX_TEXT = 280
MIN_STEPS, MAX_STEPS = 6, 15
SQUARE_RE = re.compile(r"^[a-h][1-8]$")
# "+1.3", "-0,8", "45 cp": engine scores have no place in a lesson. "1-0" and "move 12" are fine.
ENGINE_NUMBER_RE = re.compile(r"(?<![\w.,])[+-]\d+(?:[.,]\d+)?(?!\w)|\b\d+\s*(?:cp|centipawns?|centipions?)\b",
                              re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    check: str
    level: Literal["fail", "warn"]
    detail: str
    step_id: str | None = None


def has_failures(issues: list[Issue]) -> bool:
    return any(i.level == "fail" for i in issues)


# --- chess helpers ------------------------------------------------------------

def board_of(fen) -> chess.Board | None:
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError):
        return None
    return board if board.is_valid() else None


def legal_move(board: chess.Board, uci) -> chess.Move | None:
    try:
        move = chess.Move.from_uci(uci)
    except (ValueError, TypeError):
        return None
    return move if move in board.legal_moves else None


def player_move_indexes(step: dict) -> list[int]:
    """Indexes into a play_line's moves that the learner plays (the step's side)."""
    board = chess.Board(step["fen"])
    side = chess.WHITE if step["side"] == "white" else chess.BLACK
    return [i for i in range(len(step["moves"])) if (board.turn if i % 2 == 0 else not board.turn) == side]


def allowed_san(step: dict) -> set[str]:
    """SAN of every legal move the step contains, each in its own position."""
    board = board_of(step.get("fen"))
    if board is None:
        return set()
    out: set[str] = set()

    def add(b: chess.Board, uci) -> chess.Move | None:
        move = legal_move(b, uci)
        if move is not None:
            out.add(b.san(move))
        return move

    kind = step.get("type")
    if kind == "find_move":
        ucis = list(step.get("accept") or []) + [g.get("uci") for g in _dicts(step.get("also_good"))] \
            + [w.get("uci") for w in _dicts(step.get("wrong"))]
        for uci in ucis:
            add(board, uci)
    elif kind == "choice":
        for option in _dicts(step.get("options")):
            if "uci" in option:
                add(board, option["uci"])
    elif kind == "show_moves":
        b = board.copy()
        for item in _dicts(step.get("moves")):
            move = add(b, item.get("uci"))
            if move is None:
                break
            b.push(move)
    elif kind == "play_line":
        b, alts = board.copy(), step.get("also_accept") or {}
        for i, uci in enumerate(step.get("moves") or []):
            for alt in (alts.get(str(i)) or []) if isinstance(alts, dict) else []:
                add(b, alt)
            move = add(b, uci)
            if move is None:
                break
            b.push(move)
    elif kind == "explain":
        for arrow in step.get("arrows") or []:
            if isinstance(arrow, list) and len(arrow) == 2 and all(isinstance(a, str) for a in arrow):
                add(board, arrow[0] + arrow[1])
    return out


def _dicts(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


# --- the check ----------------------------------------------------------------

class _Checker:
    def __init__(self):
        self.issues: list[Issue] = []

    def add(self, check, level, detail, step_id=None):
        self.issues.append(Issue(check, level, detail, step_id))

    def text(self, value, field, step_id, allowed: set[str], required=True):
        if value is None:
            if required:
                self.add("schema", "fail", f"missing {field}", step_id)
            return
        if not isinstance(value, dict):
            self.add("schema", "fail", f"{field} must be {{fr, en}}", step_id)
            return
        allowed_plain = {a.rstrip("+#") for a in allowed}
        for lang in LANGS:
            t = value.get(lang)
            if not isinstance(t, str) or not t.strip():
                self.add("language", "fail", f"{field}: no {lang} text", step_id)
                continue
            if len(t) > MAX_TEXT:
                self.add("text_too_long", "warn", f"{field}.{lang}: {len(t)} characters", step_id)
            numbers = ENGINE_NUMBER_RE.search(t)
            if numbers:
                self.add("engine_numbers", "fail", f"{field}.{lang}: {numbers.group(0)}", step_id)
            unknown = sorted({tok.rstrip("+#") for tok in MOVE_RE.findall(t)} - allowed_plain)
            if unknown:
                self.add("unknown_move_in_text", "fail", f"{field}.{lang}: {', '.join(unknown)}", step_id)

    def moves_legal(self, board: chess.Board, ucis, field, step_id) -> bool:
        if not isinstance(ucis, list):
            self.add("schema", "fail", f"{field} must be a list", step_id)
            return False
        ok = True
        for uci in ucis:
            if legal_move(board, uci) is None:
                self.add("illegal_move", "fail", f"{field}: {uci}", step_id)
                ok = False
        return ok


def check_structure(content) -> list[Issue]:
    c = _Checker()
    if not isinstance(content, dict) or content.get("schema") != 1 or not isinstance(content.get("meta"), dict) \
            or not isinstance(content.get("steps"), list) or not content["steps"]:
        c.add("schema", "fail", "not a lesson document (schema 1 with meta and steps)")
        return c.issues
    steps = content["steps"]
    if not MIN_STEPS <= len(steps) <= MAX_STEPS:
        c.add("step_count", "warn", f"{len(steps)} steps (expected {MIN_STEPS} to {MAX_STEPS})")

    usable, seen = [], set()
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            c.add("schema", "fail", f"step {i + 1} is not an object")
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            c.add("schema", "fail", f"step {i + 1}: id must match {ID_RE.pattern}")
            continue
        if sid in seen:
            c.add("duplicate_id", "fail", f"step {i + 1} reuses id {sid}", sid)
        seen.add(sid)
        if s.get("type") not in STEP_TYPES:
            c.add("schema", "fail", f"unknown type {s.get('type')!r}", sid)
            continue
        board = board_of(s.get("fen"))
        if board is None:
            c.add("illegal_position", "fail", f"fen {s.get('fen')!r}", sid)
            continue
        usable.append((s, board))

    lesson_allowed = set().union(*(allowed_san(s) for s, _ in usable)) if usable else set()
    _check_meta(c, content["meta"], lesson_allowed)
    _check_completion(c, content.get("completion"))
    for s, board in usable:
        _check_common(c, s)
        CHECKS[s["type"]](c, s, board, lesson_allowed if s["type"] == "explain" else allowed_san(s))
    return c.issues


def _check_meta(c: _Checker, meta: dict, allowed: set[str]) -> None:
    c.text(meta.get("title"), "meta.title", None, allowed)
    c.text(meta.get("description"), "meta.description", None, allowed)
    objectives = meta.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        c.add("schema", "fail", "meta.objectives needs at least one objective")
    else:
        for n, obj in enumerate(objectives):
            c.text(obj, f"meta.objectives[{n}]", None, allowed)
    if not _int_between(meta.get("difficulty"), 1, 5):
        c.add("schema", "fail", "meta.difficulty must be 1 to 5")
    if not _int_between(meta.get("estimated_minutes"), 1, 15):
        c.add("schema", "fail", "meta.estimated_minutes must be 1 to 15")
    if meta.get("orientation") not in ("white", "black"):
        c.add("schema", "fail", "meta.orientation must be white or black")


def _check_completion(c: _Checker, completion) -> None:
    if completion is None:
        return
    value = completion.get("min_accuracy", 0) if isinstance(completion, dict) else None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
        c.add("schema", "fail", "completion.min_accuracy must be between 0 and 1")


def _check_common(c: _Checker, s: dict) -> None:
    sid = s["id"]
    for arrow in s.get("arrows") or []:
        if not (isinstance(arrow, list) and len(arrow) == 2 and all(isinstance(a, str) and SQUARE_RE.match(a)
                                                                    for a in arrow)):
            c.add("schema", "fail", f"bad arrow {arrow!r}", sid)
    for square in s.get("highlights") or []:
        if not (isinstance(square, str) and SQUARE_RE.match(square)):
            c.add("schema", "fail", f"bad highlight {square!r}", sid)
    skills = s.get("skills", [])
    if not isinstance(skills, list) or not all(isinstance(k, str) for k in skills):
        c.add("schema", "fail", "skills must be a list of strings", sid)


def _check_explain(c, s, board, allowed):
    c.text(s.get("text"), "text", s["id"], allowed)


def _check_show_moves(c, s, board, allowed):
    sid = s["id"]
    c.text(s.get("text"), "text", sid, allowed, required=False)
    moves = s.get("moves")
    if not isinstance(moves, list) or not moves:
        c.add("schema", "fail", "moves needs at least one move", sid)
        return
    b = board.copy()
    for n, item in enumerate(moves):
        if not isinstance(item, dict):
            c.add("schema", "fail", f"moves[{n}] must be {{uci, caption}}", sid)
            return
        move = legal_move(b, item.get("uci"))
        if move is None:
            c.add("illegal_move", "fail", f"moves[{n}]: {item.get('uci')}", sid)
            return
        c.text(item.get("caption"), f"moves[{n}].caption", sid, allowed)
        b.push(move)


def _check_find_move(c, s, board, allowed):
    sid = s["id"]
    for field in ("prompt", "correct", "hint"):
        c.text(s.get(field), field, sid, allowed)
    accept = s.get("accept")
    if not isinstance(accept, list) or not accept:
        c.add("schema", "fail", "missing accept", sid)
    else:
        c.moves_legal(board, accept, "accept", sid)
    for field, text_field in (("also_good", "note"), ("wrong", "feedback")):
        items = s.get(field, [])
        if not isinstance(items, list):
            c.add("schema", "fail", f"{field} must be a list", sid)
            continue
        for n, item in enumerate(items):
            if not isinstance(item, dict):
                c.add("schema", "fail", f"{field}[{n}] must be an object", sid)
                continue
            c.moves_legal(board, [item.get("uci")], f"{field}[{n}]", sid)
            c.text(item.get(text_field), f"{field}[{n}].{text_field}", sid, allowed)


def _check_choice(c, s, board, allowed):
    sid = s["id"]
    for field in ("question", "explanation", "hint"):
        c.text(s.get(field), field, sid, allowed)
    options = s.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 4:
        c.add("schema", "fail", "options needs 2 to 4 options", sid)
        return
    for n, option in enumerate(options):
        if isinstance(option, dict) and "text" in option:
            c.text(option["text"], f"options[{n}].text", sid, allowed)
        elif isinstance(option, dict) and "uci" in option:
            c.moves_legal(board, [option["uci"]], f"options[{n}]", sid)
        else:
            c.add("schema", "fail", f"options[{n}] needs text or uci", sid)
    answer = s.get("answer")
    if not _int_between(answer, 0, len(options) - 1):
        c.add("schema", "fail", f"answer must be an option index (0 to {len(options) - 1})", sid)


def _check_play_line(c, s, board, allowed):
    sid = s["id"]
    for field in ("prompt", "hint"):
        c.text(s.get(field), field, sid, allowed)
    if s.get("side") not in ("white", "black"):
        c.add("schema", "fail", "side must be white or black", sid)
        return
    moves = s.get("moves")
    if not isinstance(moves, list) or len(moves) < 2:
        c.add("schema", "fail", "moves needs at least two moves", sid)
        return
    alts = s.get("also_accept", {})
    notes = s.get("notes", {})
    if not isinstance(alts, dict) or not isinstance(notes, dict):
        c.add("schema", "fail", "also_accept and notes must be objects keyed by move index", sid)
        return
    players = set(player_move_indexes(s))
    b = board.copy()
    for i, uci in enumerate(moves):
        for alt in alts.get(str(i), []) if isinstance(alts.get(str(i), []), list) else [None]:
            if legal_move(b, alt) is None:
                c.add("illegal_move", "fail", f"also_accept[{i}]: {alt}", sid)
        move = legal_move(b, uci)
        if move is None:
            c.add("illegal_move", "fail", f"moves[{i}]: {uci}", sid)
            return
        b.push(move)
    for key in alts:
        if not key.isdigit() or int(key) not in players:
            c.add("schema", "fail", f"also_accept key {key} is not one of the learner's moves", sid)
    for key, note in notes.items():
        if not key.isdigit() or int(key) >= len(moves):
            c.add("schema", "fail", f"notes key {key} is not a move index", sid)
        c.text(note, f"notes[{key}]", sid, allowed)
    srs = s.get("srs")
    if srs is not None and not (isinstance(srs, dict) and isinstance(srs.get("line_key"), str) and srs["line_key"]):
        c.add("schema", "fail", "srs needs a line_key", sid)


CHECKS = {"explain": _check_explain, "show_moves": _check_show_moves, "find_move": _check_find_move,
          "choice": _check_choice, "play_line": _check_play_line}


def _int_between(value, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


# --- learner view -----------------------------------------------------------------

def _is_text(value) -> bool:
    return isinstance(value, dict) and set(value) == set(LANGS) and all(isinstance(v, str) for v in value.values())


def localize(content: dict, lang: str) -> dict:
    """A copy of the document with every {fr, en} text replaced by the learner's language (French notation in fr)."""
    def walk(value):
        if _is_text(value):
            return frenchify(value["fr"]) if lang == "fr" else value["en"]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    return walk(content)
