from django.urls import path

from . import views

urlpatterns = [
    path("games/<int:game_id>/review/", views.start_review_view, name="start_review"),
    path("reviews/<int:review_id>/", views.review_page, name="review_page"),
    path("reviews/<int:review_id>/status.json", views.review_status, name="review_status"),
]
