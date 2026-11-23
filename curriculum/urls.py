from django.urls import path

from . import studio

urlpatterns = [
    path("", studio.lesson_list, name="studio_lessons"),
    path("versions/<int:pk>/", studio.version_page, name="studio_version"),
    path("versions/<int:pk>/content", studio.version_content, name="studio_version_content"),
    path("versions/<int:pk>/transition", studio.version_transition, name="studio_version_transition"),
    path("lessons/<slug:slug>/versions/new", studio.new_version, name="studio_new_version"),
]
