from django.urls import path

from . import health

urlpatterns = [
    path("", health.sources_page, name="sources_page"),
    path("json/", health.sources_json, name="sources_json"),
    path("runs/", health.refresh_log_json, name="sources_runs"),
]