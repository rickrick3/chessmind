from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from . import services


@require_GET
def area_detail_page(request, area):
    learner = request.learner
    if learner is None:
        return redirect("/start/")
    try:
        detail = services.area_detail(learner, area)
    except KeyError:
        raise Http404 from None
    return render(request, "skills/area.html", {"detail": detail})
