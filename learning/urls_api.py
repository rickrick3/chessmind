from django.urls import path

from . import api

urlpatterns = [
    path("me", api.me, name="api_me"),
    path("me/start-level", api.start_level, name="api_start_level"),
    path("me/settings", api.me_settings, name="api_settings"),
    path("lessons/<slug:slug>", api.lesson, name="api_lesson"),
    path("lessons/<slug:slug>/attempts", api.attempts, name="api_attempts"),
    path("attempts/<uuid:attempt_id>/finish", api.finish, name="api_finish"),
]
