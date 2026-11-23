from django.urls import path

from . import views

urlpatterns = [
    path("train/", views.train, name="train"),
    path("train/puzzles/", views.puzzles, name="puzzles"),
    path("train/puzzles/<str:lichess_id>/", views.replay, name="puzzle_replay"),
]
