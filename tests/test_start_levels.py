"""Start levels name units by their place in the course, whatever has been published so far."""
import pytest

from accounts.models import Learner
from learning.services import states_for

pytestmark = pytest.mark.django_db


def _course(lesson_factory, publish, valid_content, units):
    for unit, unit_order in units:
        for i in (1, 2):
            publish(lesson_factory(f"{unit[:3]}{i}", unit=unit, unit_order=unit_order, order=unit_order * 10 + i),
                    valid_content)


def test_club_is_not_sent_to_a_later_unit_while_material_is_unpublished(lesson_factory, publish, valid_content):
    _course(lesson_factory, publish, valid_content, [("basics", 1), ("first-endgames", 6)])
    states = states_for(Learner.objects.create(start_level="club"))
    assert states["bas1"] == "current" and states["fir1"] == "locked"


def test_rules_starts_at_basics_even_when_pieces_is_unpublished(lesson_factory, publish, valid_content):
    _course(lesson_factory, publish, valid_content, [("basics", 1), ("material", 2)])
    states = states_for(Learner.objects.create(start_level="rules"))
    assert states["bas1"] == "current" and states["mat1"] == "locked"
