import pytest

from analysis.facts import FactPacket


def pytest_sessionfinish(session, exitstatus):
    from analysis.engine import close_engine

    close_engine()


def _packet(**kw):
    base = dict(ply=5, mover="white", san="Nf3", grade="good", key_moment=False, wp_before=55.0, wp_after=53.0,
                best_san="d4", best_line_san=["d4", "exd4", "Nxd4"], replies_san=["Nc6", "d6", "Nf6"],
                is_check=False, captured=None, hanging_after=[], forks=[], material_diff=0)
    base.update(kw)
    return FactPacket(**base)


@pytest.fixture(autouse=True)
def _clear_cache():
    """The test cache is in-process: clear it so one test's login failures can't block another's login."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rf_with_session(rf):
    """Build a request that has a session, a LANGUAGE_CODE and no learner yet, as the middleware leaves it."""
    from django.contrib.sessions.middleware import SessionMiddleware
    from django.utils.translation import get_language_from_request

    def build(path="/", **headers):
        req = rf.get(path, **headers)
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()
        req.LANGUAGE_CODE = get_language_from_request(req)
        req.learner = None
        return req

    return build


@pytest.fixture
def guest(db):
    from accounts.models import Learner

    return Learner.objects.create()


@pytest.fixture
def guest_client(client, guest):
    """A test client whose session holds a guest learner. Returns (client, guest)."""
    s = client.session
    s["learner_id"] = guest.id
    s.save()
    return client, guest


@pytest.fixture
def account(db, django_user_model):
    """User farel@example.com / Chess-is-fun-42 with a learner."""
    from accounts.models import Learner

    user = django_user_model.objects.create_user("farel@example.com", "farel@example.com", "Chess-is-fun-42")
    Learner.objects.create(user=user, display_name="Farel")
    return user


@pytest.fixture
def packet_good():
    return _packet()


@pytest.fixture
def packet_blunder():
    return _packet(ply=12, mover="black", san="Qd5", grade="blunder", key_moment=True, wp_before=50.0,
                   wp_after=12.0, best_san="Be7", best_line_san=["Be7", "O-O", "O-O"],
                   replies_san=["Nc3", "Bxd5", "c4"], hanging_after=["queen on d5"], material_diff=0)


@pytest.fixture
def packet_hanging_queen(packet_blunder):
    return packet_blunder
