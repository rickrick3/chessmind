"""Publication states of a lesson version, and which moves between them are allowed."""

DRAFT = "draft"
GENERATING = "generating"
VALIDATING = "validating"
PENDING_REVIEW = "pending_review"
APPROVED = "approved"
PUBLISHED = "published"
REJECTED = "rejected"
ARCHIVED = "archived"

STATUSES = (DRAFT, GENERATING, VALIDATING, PENDING_REVIEW, APPROVED, PUBLISHED, REJECTED, ARCHIVED)

ALLOWED = {
    DRAFT: {GENERATING, VALIDATING},
    GENERATING: {VALIDATING, DRAFT},
    VALIDATING: {PENDING_REVIEW, DRAFT},
    PENDING_REVIEW: {VALIDATING, APPROVED, REJECTED},
    APPROVED: {PUBLISHED},
    PUBLISHED: {ARCHIVED},
    REJECTED: set(),
    ARCHIVED: set(),
}

# Content can only change while a version is a draft or waiting for review.
EDITABLE = frozenset({DRAFT, PENDING_REVIEW})


class IllegalTransition(Exception):
    """The workflow does not allow this change of status."""


def check_transition(current: str, target: str) -> None:
    if target not in ALLOWED.get(current, set()):
        raise IllegalTransition(f"{current} -> {target}")
