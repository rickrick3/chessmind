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
