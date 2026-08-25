from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("staff/", views.staff_dashboard, name="staff_dashboard"),
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
]
