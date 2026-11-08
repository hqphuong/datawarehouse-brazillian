from django.urls import path

from . import views

urlpatterns = [
    path("routes", views.routes),
    path("scenario", views.scenario),
    path("promise", views.promise),
    path("actions", views.actions),
    path("brief", views.brief),
    path("attribution", views.attribution),
    path("promise-policy", views.promise_policy),
    path("sellers", views.sellers),
    path("portfolio", views.portfolio),
]
