from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("players.urls")),
    path("", include("games.urls")),
    path("", include("analysis.urls")),
]
