"""Plain-language explanations built only from a FactPacket. Free, instant, used when the AI is not."""

PIECES_FR = {"pawn": "pion", "knight": "cavalier", "bishop": "fou", "rook": "tour", "queen": "dame", "king": "roi"}
FEMININE_FR = {"tour", "dame"}

T = {
    "en": {
        "side": {"white": "White", "black": "Black"},
        "grade": {"best": "the best move", "good": "a good move", "inaccuracy": "an inaccuracy",
                  "mistake": "a mistake", "blunder": "a blunder"},
        "is": "{san} ({side}) is {grade}.",
        "check": "It gives check.",
        "capture": "It captures {piece}.",
        "fork": "The piece now attacks {targets} at the same time.",
        "chances": "{side}'s winning chances go from {before}% to {after}%.",
        "hanging": "It leaves {pieces} undefended.",
        "better": "Better was {best} (line: {line}).",
        "replies": "{opp} can now answer with {replies}.",
        "and": " and ", "or": " or ",
        "piece": lambda p: f"the {p}" if " on " in p else f"a {p}",
    },
    "fr": {
        "side": {"white": "les Blancs", "black": "les Noirs"},
        "grade": {"best": "le meilleur coup", "good": "un bon coup", "inaccuracy": "une imprécision",
                  "mistake": "une erreur", "blunder": "une gaffe"},
        "is": "{san} ({side}) est {grade}.",
        "check": "Il donne échec.",
        "capture": "Il prend {piece}.",
        "fork": "La pièce attaque maintenant {targets} en même temps.",
        "chances": "Les chances de gain pour {side} passent de {before} % à {after} %.",
        "hanging": "Il laisse {pieces} sans défense.",
        "better": "Mieux valait {best} (suite : {line}).",
        "replies": "{opp} peuvent maintenant répondre {replies}.",
        "and": " et ", "or": " ou ",
        "piece": lambda p: _piece_fr(p),
    },
}


def _piece_fr(text: str) -> str:
    """'queen on d5' -> 'la dame en d5'; 'rook' -> 'une tour'."""
    name, _, square = text.partition(" on ")
    name = PIECES_FR.get(name, name)
    fem = name in FEMININE_FR
    if square:
        return f"{'la' if fem else 'le'} {name} en {square}"
    return f"{'une' if fem else 'un'} {name}"


def _join(items: list[str], sep: str) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + sep + items[-1]


def template_text(p, lang: str, depth: str) -> str:
    t = T["fr" if lang == "fr" else "en"]
    side = t["side"][p.mover]
    opp = t["side"]["black" if p.mover == "white" else "white"]
    out = [t["is"].format(san=p.san, side=side, grade=t["grade"][p.grade])]
    if p.is_check:
        out.append(t["check"])
    if p.captured:
        out.append(t["capture"].format(piece=t["piece"](p.captured)))
    if p.forks:
        out.append(t["fork"].format(targets=_join([t["piece"](f) for f in p.forks], t["and"])))
    if depth == "full":
        out.append(t["chances"].format(side=side, before=round(p.wp_before), after=round(p.wp_after)))
        if p.hanging_after:
            out.append(t["hanging"].format(pieces=_join([t["piece"](h) for h in p.hanging_after], t["and"])))
        if p.best_san:
            out.append(t["better"].format(best=p.best_san, line=" ".join(p.best_line_san)))
        if p.replies_san:
            out.append(t["replies"].format(opp=opp[0].upper() + opp[1:], replies=_join(p.replies_san, t["or"])))
    return " ".join(out)
