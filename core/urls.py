from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("board/", views.board, name="board"),
]
