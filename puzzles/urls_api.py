from django.urls import path

from . import api

urlpatterns = [
    path("puzzles/next", api.next_puzzle, name="api_puzzle_next"),
    path("puzzle-attempts/<uuid:attempt_id>/finish", api.finish, name="api_puzzle_finish"),
    path("puzzles/<str:lichess_id>/report", api.report, name="api_puzzle_report"),
]
