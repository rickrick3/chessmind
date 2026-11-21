from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("start/", views.start, name="start"),
    path("learn/", views.path, name="path"),
    path("profile/", views.profile, name="profile"),
]
