"""Bounded harvesting of article preview images.

The refresh command and the backfill command share this module.  It exists so
a cron run can enrich a small queue (default: 12 rows) without turning a feed
refresh into an unbounded crawl, and so the web refresh can leave the queue
untouched.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from concurrent.futures import as_completed

from django.db.models import Q

from .image_proxy import _validate_url
from .images import MAX_IMAGE_URL_LENGTH, fetch_og_image
from .models import Article

logger = logging.getLogger(__name__)

DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = 8.0
DEFAULT_DEADLINE = 30.0


def candidate_queryset(limit: int = 12, existing: bool = False):
    """Newest image-less articles, or every article when ``existing``."""
    queryset = Article.objects.order_by("-published_at", "-fetched_at")
    if not existing:
        queryset = queryset.filter(Q(image_url="") | Q(image_url__isnull=True))
    if limit and limit > 0:
        queryset = queryset[:limit]
    return queryset


def _fetch_one(article: Article, timeout: float):
    try:
        _validate_url(article.url)
    except Exception:
        return None
    try:
        image_url, final_url = fetch_og_image(article.url, timeout=timeout)
    except Exception:
        return None
    if not image_url or len(image_url) > MAX_IMAGE_URL_LENGTH:
        return None
    return (article.pk, image_url, final_url)


def harvest_images(
    articles,
    max_images: int = 12,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
    deadline: float = DEFAULT_DEADLINE,
):
    """Fetch images for up to ``max_images`` rows; return ``(pk, image, final)``.

    The wall-clock deadline bounds the whole batch.  A slow publisher cannot
    hold a cron run open past it; pending futures are cancelled and running
    threads are left to finish their own per-request timeout.
    """
    rows = [article for article in articles if article.url][:max_images]
    if not rows:
        return []

    hits = []
    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(rows))))
    futures = {pool.submit(_fetch_one, article, timeout): article for article in rows}
    try:
        for future in as_completed(futures, timeout=deadline if deadline and deadline > 0 else None):
            try:
                result = future.result()
            except Exception:
                continue
            if result:
                hits.append(result)
    except FuturesTimeout:
        logger.info("image harvest hit its %.0fs deadline", deadline)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return hits


def save_hits(hits, existing: bool = False) -> int:
    """Persist harvested images with a conditional write.

    By default a row that gained an image while the fetch was in flight is
    left alone; ``existing=True`` is the explicit backfill refresh path.
    """
    saved = 0
    for article_id, image_url, _final_url in hits:
        queryset = Article.objects.filter(pk=article_id)
        if not existing:
            queryset = queryset.filter(Q(image_url="") | Q(image_url__isnull=True))
        saved += queryset.update(image_url=image_url[:MAX_IMAGE_URL_LENGTH])
    return saved


def harvest_and_save(
    limit: int = 12,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
    deadline: float = DEFAULT_DEADLINE,
    existing: bool = False,
):
    """Harvest and persist; returns ``(scanned, found, saved)``."""
    rows = list(candidate_queryset(limit=limit, existing=existing))
    hits = harvest_images(
        rows,
        max_images=limit or len(rows),
        workers=workers,
        timeout=timeout,
        deadline=deadline,
    )
    return len(rows), len(hits), save_hits(hits, existing=existing)
