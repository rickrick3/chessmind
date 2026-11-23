from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("studio/", include("curriculum.urls")),
    path("api/v1/", include("learning.urls_api")),
    path("api/v1/", include("puzzles.urls_api")),
    path("", include("accounts.urls")),
    path("", include("players.urls")),
    path("", include("games.urls")),
    path("", include("analysis.urls")),
    path("", include("puzzles.urls")),
    path("", include("skills.urls")),
    path("", include("learning.urls")),
]
