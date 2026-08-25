from django.urls import path

from . import views

urlpatterns = [
    path("take-token/", views.take_token, name="take_token"),
    path("live/", views.live_queue, name="live_queue"),
    path("history/", views.queue_history, name="queue_history"),
    path("staff/call-next/", views.call_next, name="call_next"),
    path("staff/token/<int:token_id>/<str:action>/", views.change_token_status, name="change_token_status"),
]
