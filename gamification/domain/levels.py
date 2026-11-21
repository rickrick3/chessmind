"""Levels show progress and unlock nothing. Level n starts at 25 * n * (n - 1) XP: 0, 50, 150, 300, 500..."""


def level_floor(level: int) -> int:
    return 25 * level * (level - 1)


def level_for(xp: int) -> int:
    level = 1
    while level_floor(level + 1) <= xp:
        level += 1
    return level
