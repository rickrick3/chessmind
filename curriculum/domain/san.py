"""French move notation. Lesson text is written with English piece letters; French readers see French ones."""
from analysis.ai import MOVE_RE

FRENCH_PIECES = {"K": "R", "Q": "D", "R": "T", "B": "F", "N": "C"}


def _to_french(token: str) -> str:
    if token.startswith("O-O"):
        return token
    head = FRENCH_PIECES.get(token[0], token[0])
    body = token[1:]
    if "=" in body:
        before, after = body.split("=", 1)
        body = f"{before}={FRENCH_PIECES.get(after[:1], after[:1])}{after[1:]}"
    return head + body


def frenchify(text: str) -> str:
    """Rewrite every move token (K Q R B N, promotions) in French letters (R D T F C). Other words are untouched."""
    return MOVE_RE.sub(lambda m: _to_french(m.group(0)), text)
