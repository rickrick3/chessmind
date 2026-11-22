from django.utils import timezone

from players.models import Player

from .models import Learner
from .services import request_language


class LearnerMiddleware:
    """Sets request.learner: the account's learner, the session's guest, or None. Never creates a guest."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.learner = self._learner(request)
        if request.learner is not None:
            self._touch(request, request.learner)
        return self.get_response(request)

    def _learner(self, request) -> Learner | None:
        session = request.session
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            learner, _ = Learner.objects.get_or_create(user=user, defaults={"language": request_language(request)})
        else:
            learner = Learner.objects.filter(id=session.get("learner_id"), user__isnull=True).first()
            if learner is None and "learner_id" in session:
                del session["learner_id"]
        if "player_id" in session:  # session from the old Chess.com-username sign-in
            learner = self._adopt_legacy_player(request, learner, session.pop("player_id"))
        return learner

    @staticmethod
    def _adopt_legacy_player(request, learner, player_id) -> Learner | None:
        player = Player.objects.filter(id=player_id).first()
        if player is None:
            return learner
        if learner is None:
            learner = Learner.objects.create(player=player, language=player.language)
            request.session["learner_id"] = learner.id
        elif learner.player_id != player.id:
            learner.player = player
            learner.save(update_fields=["player"])
        return learner

    @staticmethod
    def _touch(request, learner: Learner) -> None:
        """Once a day: record the visit and re-send the session cookie, so an active guest's year starts again."""
        now = timezone.now()
        if learner.last_seen_at is None or learner.last_seen_at.date() < now.date():
            Learner.objects.filter(pk=learner.pk).update(last_seen_at=now)
            learner.last_seen_at = now
            request.session.modified = True
