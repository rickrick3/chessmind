"""Which lessons a learner can open, and which one comes next. Same input, same answer."""
from dataclasses import dataclass

REVISIT_BELOW = 0.7
# Unit orders of the Fundamentals path: 0 pieces, 1 basics, 2 material (curriculum/seed/*.json).
OPENED_UNITS = {"rules": {0, 1}, "club": {0, 1, 2}}  # start level -> unit orders open from the start
START_UNIT = {"rules": 1, "club": 2}  # start level -> the unit order its next lesson ("current") is taken from


@dataclass(frozen=True)
class LessonNode:
    slug: str
    track: str  # "path", "openings", "endgames", "tactics"
    unit_index: int  # the order of the lesson's unit in its course (Unit.order)
    position: int  # rank of the lesson in its course, from 0
    prerequisites: frozenset[str]


def lesson_states(nodes: list[LessonNode], completed: set[str], start_level: str) -> dict[str, str]:
    """Each lesson's state: "done", "current" (the next path lesson), "open" or "locked"."""
    opened = OPENED_UNITS.get(start_level, set())
    states: dict[str, str] = {}
    previous_done = True
    for n in sorted((n for n in nodes if n.track == "path"), key=lambda n: n.position):
        if n.slug in completed:
            states[n.slug] = "done"
        elif (previous_done or n.unit_index in opened) and n.prerequisites <= completed:
            states[n.slug] = "open"
        else:
            states[n.slug] = "locked"
        previous_done = n.slug in completed
    for n in nodes:
        if n.track != "path":
            states[n.slug] = "done" if n.slug in completed else "open" if n.prerequisites <= completed else "locked"
    path_open = [n for n in sorted(nodes, key=lambda n: n.position) if n.track == "path" and states[n.slug] == "open"]
    start_unit = START_UNIT.get(start_level, 0)
    first_open = next((n.slug for n in path_open if n.unit_index >= start_unit),
                      path_open[0].slug if path_open else None)
    if first_open is not None:
        states[first_open] = "current"
    return states


def next_up(states: dict[str, str], nodes: list[LessonNode], best_accuracy: dict[str, float]) -> str | None:
    """The current path lesson; else the weakest done lesson under REVISIT_BELOW; else None."""
    current = next((slug for slug, state in states.items() if state == "current"), None)
    if current is not None:
        return current
    order = {n.slug: n.position for n in nodes}
    weak = [(best_accuracy.get(slug, 0.0), order.get(slug, 0), slug) for slug, state in states.items()
            if state == "done" and best_accuracy.get(slug, 0.0) < REVISIT_BELOW]
    return min(weak)[2] if weak else None
