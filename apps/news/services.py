"""Reusable refresh service shared by the web endpoint and the management command.

A DB-backed lock (``RefreshRun`` rows with ``status='running'``) prevents
concurrent refreshes; stale locks older than ``LOCK_STALE_MINUTES`` are
released automatically. The Django cache framework is deliberately not used.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .classification import apply_topics
from .feeds import fetch_all_feeds
from .model_watch import update_latest_models
from .models import Article, RefreshRun

LOCK_STALE_MINUTES = 10


class RefreshLockError(Exception):
    """Another refresh is already running (and is not stale)."""


def _close_stale_runs(now, extra_error: dict | None = None) -> int:
    """Close running runs older than the stale window. Returns count closed."""
    cutoff = now - timedelta(minutes=LOCK_STALE_MINUTES)
    stale = RefreshRun.objects.filter(status="running", started_at__lt=cutoff)
    count = 0
    for run in stale:
        run.status = "failed"
        run.finished_at = now
        errors = run.errors if isinstance(run.errors, list) else []
        errors.append(
            extra_error
            or {"key": "system", "source": "system", "error": "stale lock released"}
        )
        run.errors = errors
        run.save(update_fields=["status", "finished_at", "errors"])
        count += 1
    return count


def run_refresh(trigger: str = "web", per_feed_limit: int = 25) -> RefreshRun:
    """Fetch all feeds and upsert articles, recording a ``RefreshRun``.

    Raises ``RefreshLockError`` when a non-stale refresh is already running.
    Never raises for feed-level failures — the run's ``status``/``errors``
    carry the outcome so the caller decides the HTTP status.
    """
    now = timezone.now()
    with transaction.atomic():
        _close_stale_runs(now)
        if RefreshRun.objects.filter(status="running").exists():
            raise RefreshLockError("A refresh is already running.")
        run = RefreshRun.objects.create(trigger=trigger, status="running")

    errors: list[dict] = []
    created_count = 0
    updated_count = 0
    try:
        articles, errors = fetch_all_feeds(per_feed_limit=per_feed_limit)

        with transaction.atomic():
            for item in articles:
                defaults = {
                    "title": (item.get("title") or "")[:500],
                    "summary": item.get("summary") or "",
                    "source": (item.get("source") or "")[:120],
                    "feed_key": (item.get("feed_key") or "")[:60],
                    "published_at": item.get("published_at"),
                    "fetched_at": timezone.now(),
                }
                article, created = Article.objects.update_or_create(
                    url=(item.get("url") or "")[:1000],
                    defaults=defaults,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                try:
                    apply_topics(article)
                except Exception:
                    pass  # a classification bug must not fail the refresh

        # Keep the platform -> newest-model roster current. A detector bug
        # must never fail the refresh.
        try:
            update_latest_models()
        except Exception:
            pass

        run.finished_at = timezone.now()
        run.created_count = created_count
        run.updated_count = updated_count
        run.total_articles = Article.objects.count()
        run.errors = errors
        if not articles and errors:
            run.status = "failed"
        elif errors:
            run.status = "partial"
        else:
            run.status = "success"
        run.save()
        return run
    except Exception as exc:
        run.finished_at = timezone.now()
        run.status = "failed"
        run.created_count = created_count
        run.updated_count = updated_count
        run.total_articles = Article.objects.count()
        run.errors = errors + [
            {"key": "system", "source": "system", "error": str(exc)}
        ]
        run.save()
        raise


def latest_run() -> RefreshRun | None:
    """Most recent refresh run (``started_at`` descending)."""
    return RefreshRun.objects.first()


def can_refresh() -> bool:
    """False when a non-stale running refresh holds the lock."""
    now = timezone.now()
    cutoff = now - timedelta(minutes=LOCK_STALE_MINUTES)
    return not RefreshRun.objects.filter(
        status="running", started_at__gte=cutoff
    ).exists()
