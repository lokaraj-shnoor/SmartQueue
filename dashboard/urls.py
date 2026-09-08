from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("admin/", views.admin_home, name="admin_home"),
    path("admin/services/", views.service_list, name="service_list"),
    path("admin/services/<int:pk>/edit/", views.service_edit, name="service_edit"),
    path("admin/services/<int:pk>/toggle/", views.service_toggle, name="service_toggle"),
    path("admin/services/<int:pk>/delete/", views.service_delete, name="service_delete"),
    path("admin/counters/", views.counter_list, name="counter_list"),
    path("admin/counters/<int:pk>/edit/", views.counter_edit, name="counter_edit"),
    path("admin/counters/<int:pk>/status/", views.counter_status, name="counter_status"),
    path("admin/counters/<int:pk>/delete/", views.counter_delete, name="counter_delete"),
    path("admin/queue-settings/", views.queue_settings, name="queue_settings"),
    path("admin/team/", views.team_list, name="team_list"),
    path("admin/history/", views.history, name="history"),
    path("admin/team/<int:pk>/toggle/", views.team_toggle, name="team_toggle"),
    path("staff/", views.staff_home, name="staff_home"),
    path("staff/counter/<int:pk>/call/", views.call_next, name="call_next"),
    path("staff/counter/<int:pk>/shift/", views.counter_shift, name="counter_shift"),
    path("staff/entry/<int:pk>/recall/", views.entry_recall, name="entry_recall"),
    path("staff/entry/<int:pk>/start/", views.entry_start, name="entry_start"),
    path("staff/entry/<int:pk>/finish/", views.entry_finish, name="entry_finish"),
    path("staff/entry/<int:pk>/skip/", views.entry_skip, name="entry_skip"),
    path("staff/entry/<int:pk>/requeue/", views.entry_requeue, name="entry_requeue"),
    path("me/", views.visitor_home, name="visitor_home"),
    path("me/take/<int:pk>/", views.token_take, name="token_take"),
    path("me/token/<int:pk>/", views.token_detail, name="token_detail"),
    path("me/token/<int:pk>/cancel/", views.token_cancel, name="token_cancel"),
]
