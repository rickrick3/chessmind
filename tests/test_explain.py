import pytest

from analysis.ai import QuotaExceeded
from analysis.explain import get_explanation
from analysis.models import MoveExplanation, PositionAnalysis
from analysis.tasks import upgrade_pending_explanations

pytestmark = pytest.mark.django_db


class FakeProvider:
    name = "fake"

    def __init__(self, text="Be7 keeps the queen safe; Nc3 now wins time.", quota_after=None):
        self.text, self.calls, self.quota_after = text, 0, quota_after

    def explain(self, p, lang):
        self.calls += 1
        if self.quota_after is not None and self.calls > self.quota_after:
            raise QuotaExceeded()
        return self.text


@pytest.fixture
def pos():
    return PositionAnalysis.objects.create(fen="startfen w - -", depth=8, lines=[], cp=0)


def use(mocker, provider):
    mocker.patch("analysis.explain.get_provider", return_value=provider)
    return provider


def test_ordinary_move_uses_template_no_ai(pos, packet_good, mocker):
    fake = use(mocker, FakeProvider())
    e = get_explanation(pos, "g1f3", packet_good, "en")
    assert e.source == "template" and e.depth == "short" and fake.calls == 0


def test_key_moment_uses_ai(pos, packet_blunder, mocker):
    use(mocker, FakeProvider())
    e = get_explanation(pos, "d8d5", packet_blunder, "en")
    assert e.source == "ai" and e.depth == "full" and e.model == "fake" and not e.needs_ai


def test_cached_second_call_free(pos, packet_blunder, mocker):
    fake = use(mocker, FakeProvider())
    get_explanation(pos, "d8d5", packet_blunder, "en")
    get_explanation(pos, "d8d5", packet_blunder, "en")
    assert fake.calls == 1


def test_invalid_ai_text_retries_once_then_template(pos, packet_blunder, mocker):
    fake = use(mocker, FakeProvider(text="Qh5 wins everything."))
    e = get_explanation(pos, "d8d5", packet_blunder, "en")
    assert fake.calls == 2 and e.source == "template" and e.needs_ai


def test_quota_exceeded_falls_back(pos, packet_blunder, mocker):
    use(mocker, FakeProvider(quota_after=0))
    e = get_explanation(pos, "d8d5", packet_blunder, "en")
    assert e.source == "template" and e.needs_ai and "Be7" in e.text


def test_provider_error_falls_back(pos, packet_blunder, mocker):
    from analysis.ai import ProviderError

    class Broken(FakeProvider):
        def explain(self, p, lang):
            raise ProviderError("timeout")

    use(mocker, Broken())
    e = get_explanation(pos, "d8d5", packet_blunder, "en")
    assert e.source == "template" and e.needs_ai


def test_languages_cached_separately(pos, packet_blunder, mocker):
    use(mocker, FakeProvider())
    get_explanation(pos, "d8d5", packet_blunder, "en")
    get_explanation(pos, "d8d5", packet_blunder, "fr")
    assert MoveExplanation.objects.count() == 2


def test_upgrade_stops_at_quota(pos, packet_blunder, mocker):
    use(mocker, FakeProvider(quota_after=0))
    get_explanation(pos, "d8d5", packet_blunder, "en")
    get_explanation(pos, "d8d5", packet_blunder, "fr")
    assert MoveExplanation.objects.filter(needs_ai=True).count() == 2
    use(mocker, FakeProvider(quota_after=1))
    upgrade_pending_explanations()
    assert MoveExplanation.objects.filter(needs_ai=True).count() == 1
    assert MoveExplanation.objects.filter(source="ai").count() == 1
