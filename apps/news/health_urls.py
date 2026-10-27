from django.urls import path

from . import health

urlpatterns = [
    path("json/", health.sources_json, name="sources_json"),
    path("runs/", health.refresh_log_json, name="sources_runs"),
]
