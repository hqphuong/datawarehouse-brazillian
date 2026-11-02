from django.urls import path

from . import views

urlpatterns = [
    path("routes", views.routes),
    path("scenario", views.scenario),
    path("promise", views.promise),
    path("actions", views.actions),
]
