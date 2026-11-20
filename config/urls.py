from django.urls import include, path

urlpatterns = [
    path("", include("players.urls")),
    path("", include("games.urls")),
    path("", include("analysis.urls")),
]
