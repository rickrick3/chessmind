"""Where to look for the next puzzle. Pure."""


def target(rating: float, difficulty: str, offsets: dict[str, int]) -> int:
    """The puzzle rating to aim for: the learner's rating moved by the difficulty's offset."""
    if difficulty not in offsets:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    return round(rating) + offsets[difficulty]
