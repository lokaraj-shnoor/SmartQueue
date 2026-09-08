from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.QueueLoginView.as_view(), name="login"),
    path("logout/", views.QueueLogoutView.as_view(), name="logout"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("password/forgot/", views.QueuePasswordResetView.as_view(), name="password_reset"),
    path(
        "password/sent/",
        views.QueuePasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.QueuePasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/done/",
        views.QueuePasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("google/start/", views.google_start, name="google_start"),
    path("google/callback/", views.google_callback, name="google_callback"),
]
