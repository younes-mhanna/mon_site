from django.urls import path
from analysis import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/preview/", views.preview, name="preview"),
    path("api/analyze/", views.analyze, name="analyze"),
]
