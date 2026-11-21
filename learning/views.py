from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .models import LessonProgress


@require_GET
def landing(request):
    learner = request.learner
    if learner is not None and (not learner.is_guest or LessonProgress.objects.filter(learner=learner).exists()):
        return redirect("/learn/")
    return render(request, "learning/landing.html")


@require_GET
def start(request):
    return render(request, "learning/start.html")
