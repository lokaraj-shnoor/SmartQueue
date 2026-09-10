from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import TemplateView

from core import views as core_views

urlpatterns = [
    # Browsers ask for /favicon.ico at the root whatever the page links to.
    path("favicon.ico", core_views.favicon, name="favicon"),
    # A service worker only controls pages under its own path, so the one that
    # shows queue alerts has to be served from the root, not from /static/.
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="sw.js", content_type="application/javascript"
        ),
        name="service_worker",
    ),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("", include("core.urls")),
]
