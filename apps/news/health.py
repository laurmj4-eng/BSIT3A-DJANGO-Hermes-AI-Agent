"""Health / source overview data for the Hermes AI News dashboard.

Provides :func:`sources_json` and :func:`refresh_log_json` so consumers can
read feed health, summary stats, and recent refresh runs without touching the
article list.
"""

from __future__ import annotations

from datetime import datetime, timezone

from django.db.models import Count, Max
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .feeds import FEEDS
from .models import Article, RefreshRun
from .services import latest_run


def _health_rows():
    """Aggregate Article counts and Max(fetched_at) by feed_key in one query.

    Returns a list of row dicts keyed to ``FEEDS`` plus any stored keys not in
    ``FEEDS``.  Each row has: ``{'key', 'name', 'url', 'total', 'last_article',
    'status', 'error'}``.
    """
    aggregated = (
        Article.objects.values("feed_key")
        .annotate(total=Count("id"), latest_fetched=Max("fetched_at"))
    )
    by_key = {item["feed_key"]: item for item in aggregated}

    latest = latest_run()
    errors_by_key = {}
    if latest and latest.errors:
        for error in latest.errors:
            if isinstance(error, dict) and error.get("key"):
                errors_by_key[error["key"]] = error["error"]

    specs = [
        {"key": feed["key"], "name": feed["name"], "url": feed["url"]}
        for feed in FEEDS
    ]
    configured = {spec["key"] for spec in specs}

    stored_names = (
        Article.objects.values_list("feed_key", "source")
        .distinct()
        .exclude(feed_key="")
    )
    for key, source in stored_names:
        if key not in configured:
            specs.append({"key": key, "name": source or key, "url": ""})
            configured.add(key)

    rows = []
    for spec in specs:
        info = by_key.get(spec["key"])
        total = info["total"] if info else 0
        error = errors_by_key.get(spec["key"])
        if error:
            status = "error"
        elif total > 0:
            status = "ok"
        else:
            status = "idle"
        rows.append(
            {
                "key": spec["key"],
                "name": spec["name"],
                "url": spec["url"],
                "total": total,
                "last_article": info["latest_fetched"] if info else None,
                "status": status,
                "error": error,
            }
        )

    # Sort: error first, then ok, then idle; name ascending within each group.
    order = {"error": 0, "ok": 1, "idle": 2}
    rows.sort(key=lambda row: (order[row["status"]], row["name"].lower()))
    return rows


def _summary(rows):
    """Return summary counts from *rows* as returned by ``_health_rows()``."""
    return {
        "total": len(rows),
        "ok": sum(1 for r in rows if r["status"] == "ok"),
        "error": sum(1 for r in rows if r["status"] == "error"),
        "idle": sum(1 for r in rows if r["status"] == "idle"),
    }


@require_GET
def sources_json(request):
    """Return JSON source health data for the dashboard."""
    rows = _health_rows()
    latest = latest_run()

    def _row_json(r):
        last = r["last_article"]
        iso = last.isoformat() if last else None
        return {
            "key": r["key"],
            "name": r["name"],
            "url": r["url"],
            "total": r["total"],
            "last_article": iso,
            "status": r["status"],
            "error": r["error"],
        }

    data = {
        "sources": [_row_json(r) for r in rows],
        "summary": _summary(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if latest is not None:
        data["latest_run"] = {
            "status": latest.status,
            "started_at": latest.started_at.isoformat(),
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
            "created_count": latest.created_count,
            "updated_count": latest.updated_count,
            "total_articles": latest.total_articles,
            "errors": latest.errors,
        }

    return JsonResponse(data)


@require_GET
def refresh_log_json(request):
    """Return the last 20 refresh runs as a JSON list."""
    runs = RefreshRun.objects.order_by("-started_at")[:20]
    data = []
    for run in runs:
        data.append(
            {
                "id": run.id,
                "status": run.status,
                "trigger": run.trigger,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "created_count": run.created_count,
                "updated_count": run.updated_count,
                "total_articles": run.total_articles,
                "duration_seconds": run.duration_seconds,
                "errors_count": len(run.errors) if isinstance(run.errors, list) else 0,
            }
        )
    return JsonResponse({"runs": data})