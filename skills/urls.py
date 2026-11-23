from django.urls import path

from . import views

urlpatterns = [path("profile/skills/<str:area>/", views.area_detail_page, name="skill_area")]
