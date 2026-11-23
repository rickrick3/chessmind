from django.utils import timezone

from .services import summary


def header(request):
    """XP, level and streak for the page header, when there is a learner."""
    learner = getattr(request, "learner", None)
    return {"header": summary(learner, timezone.now())} if learner is not None else {}
