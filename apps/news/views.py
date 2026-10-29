"""Views for the public AI news feed.

Filtering, pagination and the session-backed bookmark/read state all live
here. Refresh work is delegated to :mod:`apps.news.services` so the web
endpoint and the management command share one code path.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.feedgenerator import Rss201rev2Feed
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .exporters import article_rows, csv_bytes, xlsx_bytes
from .feeds import FEEDS
from .image_proxy import (
    ImageProxyError,
    fetch_remote_image,
    read_cache,
    write_cache,
)
from .models import Article, Topic
from .services import RefreshLockError, latest_run, run_refresh

PER_PAGE = 20
SAVED_SESSION_KEY = "saved_articles"
READ_SESSION_KEY = "read_articles"
MAX_SESSION_IDS = 500
MAX_EXPORT_ROWS = 5000
MAX_SEARCH_TERMS = 6
API_DEFAULT_LIMIT = 30
API_MAX_LIMIT = 100
RSS_ITEM_LIMIT = 50
SUGGEST_RESULT_LIMIT = 8
SUGGEST_TOPIC_LIMIT = 5
REFRESH_COOLDOWN_SECONDS = 60


def refresh_cooldown_remaining() -> int:
    """Seconds left before another refresh is allowed (0 when allowed)."""
    last = latest_run()
    if last and last.status in {"success", "partial"}:
        remaining = REFRESH_COOLDOWN_SECONDS - int(
            (timezone.now() - last.started_at).total_seconds()
        )
        if remaining > 0:
            return remaining
    return 0


SORT_CHOICES = [
    ("newest", "Newest"),
    ("oldest", "Oldest"),
    ("title", "Title A-Z"),
]

NEWEST_ORDER = (F("published_at").desc(nulls_last=True), "-fetched_at")
OLDEST_ORDER = (F("published_at").asc(nulls_last=True), "fetched_at")


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _clean_ids(values) -> list[int]:
    """Ints only, de-duplicated, keeping at most the last MAX_SESSION_IDS."""
    cleaned: list[int] = []
    seen: set[int] = set()
    for value in values or []:
        try:
            pk = int(value)
        except (TypeError, ValueError):
            continue
        if pk in seen:
            continue
        seen.add(pk)
        cleaned.append(pk)
    return cleaned[-MAX_SESSION_IDS:]


def _session_ids(request, key) -> set[int]:
    return set(_clean_ids(request.session.get(key, [])))


def saved_article_ids(request) -> set[int]:
    """Article IDs bookmarked in this browser session (no account needed)."""
    return _session_ids(request, SAVED_SESSION_KEY)


def read_article_ids(request) -> set[int]:
    """Article IDs already opened in this browser session."""
    return _session_ids(request, READ_SESSION_KEY)


def _toggle_session_id(request, key, pk) -> bool:
    """Toggle *pk* in a session ID list. Returns the new "on" state."""
    values = _clean_ids(request.session.get(key, []))
    if pk in values:
        values = [value for value in values if value != pk]
        is_on = False
    else:
        values.append(pk)
        is_on = True
    request.session[key] = values[-MAX_SESSION_IDS:]
    return is_on


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _apply_filters(request, qs, include_session: bool = True):
    """Apply request filters and return ``(queryset, context)``.

    ``include_session=False`` skips the session-backed ``saved``/``unread``
    filters (used by exports and the RSS/API endpoints).
    """
    params = request.GET
    query = (params.get("q") or "").strip()
    source = (params.get("source") or "").strip()
    topic = (params.get("topic") or "").strip()
    date_from_raw = (params.get("from") or "").strip()
    date_to_raw = (params.get("to") or "").strip()
    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None
    sort = (params.get("sort") or "").strip() or "newest"
    saved_filter = params.get("saved") == "1"
    unread_filter = params.get("unread") == "1"

    if query:
        for term in query.split()[:MAX_SEARCH_TERMS]:
            qs = qs.filter(
                Q(title__icontains=term)
                | Q(summary__icontains=term)
                | Q(source__icontains=term)
            )

    if source:
        qs = qs.filter(feed_key=source)

    topic_obj = None
    if topic:
        topic_obj = Topic.objects.filter(slug=topic).first()
        if topic_obj is None:
            # Unknown slug is an empty result, never a 404.
            qs = qs.none()
        else:
            qs = qs.filter(topics__slug=topic)

    if date_from:
        qs = qs.filter(published_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(published_at__date__lte=date_to)

    if sort == "oldest":
        qs = qs.order_by(*OLDEST_ORDER)
    elif sort == "title":
        qs = qs.order_by("title", "-published_at")
    else:
        sort = "newest"
        qs = qs.order_by(*NEWEST_ORDER)

    if include_session and saved_filter:
        qs = qs.filter(pk__in=saved_article_ids(request))
    if include_session and unread_filter:
        qs = qs.exclude(pk__in=read_article_ids(request))

    qs = qs.prefetch_related("topics")

    active_filter_count = sum(
        1
        for value in (
            query,
            source,
            topic,
            date_from,
            date_to,
            saved_filter if include_session else False,
            unread_filter if include_session else False,
        )
        if value
    )

    ctx = {
        "query": query,
        "source": source,
        "topic": topic,
        "topic_obj": topic_obj,
        # Raw strings so the template can echo them back into <input> values.
        "date_from": date_from_raw if date_from else "",
        "date_to": date_to_raw if date_to else "",
        "sort": sort,
        "saved_filter": saved_filter,
        "unread_filter": unread_filter,
        "has_filters": active_filter_count > 0,
        "active_filter_count": active_filter_count,
    }
    return qs, ctx


def _elided_page_range(page) -> list[int | None]:
    """Page numbers with ``None`` standing in for the elision gap."""
    numbers = page.paginator.get_elided_page_range(page.number)
    return [number if isinstance(number, int) else None for number in numbers]


def _source_options() -> tuple[list[dict], list[tuple[str, str]]]:
    """Merge configured feeds with sources already stored in the DB."""
    options: dict[str, dict] = {}
    for feed in FEEDS:
        options[feed["key"]] = {
            "key": feed["key"],
            "name": feed["name"],
            "total": 0,
        }

    totals = dict(
        Article.objects.values_list("feed_key")
        .annotate(total=Count("id"))
        .order_by()
    )
    stored_names: dict[str, str] = {}
    for key, name in Article.objects.values_list("feed_key", "source").distinct():
        stored_names.setdefault(key, name)

    for key, name in stored_names.items():
        if key not in options:
            options[key] = {
                "key": key,
                "name": name or key,
                "total": totals.get(key, 0),
            }

    for key, option in options.items():
        option["total"] = totals.get(key, 0)

    extras = sorted(
        (option for option in options.values() if option["key"] not in {f["key"] for f in FEEDS}),
        key=lambda option: option["name"].lower(),
    )
    source_options = [
        options[feed["key"]] for feed in FEEDS
    ] + extras
    source_choices = [(option["key"], option["name"]) for option in source_options]
    return source_options, source_choices


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def news_page(request):
    """Render the AI news feed with search, filters and pagination.

    ensure_csrf_cookie guarantees the csrftoken cookie exists so the
    bookmark/refresh fetches can send X-CSRFToken (the page has no POST form
    that would otherwise trigger Django to set it).
    """
    articles, filter_ctx = _apply_filters(request, Article.objects.all())

    paginator = Paginator(articles, PER_PAGE)
    page = paginator.get_page(request.GET.get("page", 1))

    saved_ids = saved_article_ids(request)
    read_ids = read_article_ids(request)
    for article in page.object_list:
        article.is_saved = article.pk in saved_ids
        article.is_read = article.pk in read_ids

    source_options, source_choices = _source_options()

    topic_choices = list(
        Topic.objects.annotate(total=Count("articles")).order_by("-total", "name")
    )

    latest_fetch = Article.objects.order_by("-fetched_at").values_list(
        "fetched_at", flat=True
    ).first()

    # Keep active filters when paging, and build the toggle URLs.
    params = request.GET.copy()
    params.pop("page", None)
    filter_query = params.urlencode()

    saved_params = request.GET.copy()
    saved_params.pop("page", None)
    if filter_ctx["saved_filter"]:
        saved_params.pop("saved", None)
    else:
        saved_params["saved"] = "1"

    unread_params = request.GET.copy()
    unread_params.pop("page", None)
    if filter_ctx["unread_filter"]:
        unread_params.pop("unread", None)
    else:
        unread_params["unread"] = "1"

    context = {
        "articles": page,
        "page_range": _elided_page_range(page),
        "source_options": source_options,
        "source_choices": source_choices,
        "topic_choices": topic_choices,
        "sort_choices": SORT_CHOICES,
        "total": paginator.count,
        "last_updated": latest_fetch,
        "feed_count": len(FEEDS),
        "saved_total": len(saved_ids),
        "read_total": len(read_ids),
        "filter_query": filter_query,
        "saved_toggle_query": saved_params.urlencode(),
        "unread_toggle_query": unread_params.urlencode(),
        "refresh_cooldown_seconds": REFRESH_COOLDOWN_SECONDS,
        "refresh_cooldown_remaining": refresh_cooldown_remaining(),
    }
    context.update(filter_ctx)
    return render(request, "news/feed.html", context)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@require_POST
def news_refresh(request):
    """Run a feed refresh and report its outcome as JSON."""
    remaining = refresh_cooldown_remaining()
    if remaining > 0:
        response = JsonResponse(
            {
                "error": f"Refresh is cooling down. Try again in {remaining}s.",
                "retry_after": remaining,
            },
            status=429,
        )
        response["Retry-After"] = str(remaining)
        return response

    try:
        run = run_refresh(trigger="web")
    except RefreshLockError as exc:
        return JsonResponse({"error": str(exc)}, status=409)

    payload = {
        "status": run.status,
        "created": run.created_count,
        "updated": run.updated_count,
        "errors": run.errors or [],
        "total": run.total_articles,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }

    if run.status == "failed" and run.created_count + run.updated_count == 0:
        return JsonResponse(
            {
                "error": "No articles could be fetched. All feeds failed.",
                "errors": payload["errors"],
                "created": 0,
                "updated": 0,
            },
            status=502,
        )

    return JsonResponse(payload)


# ---------------------------------------------------------------------------
# Session-backed actions
# ---------------------------------------------------------------------------

@require_POST
def news_toggle_save(request, pk):
    """Bookmark / un-bookmark an article for this browser session."""
    article = get_object_or_404(Article, pk=pk)
    is_saved = _toggle_session_id(request, SAVED_SESSION_KEY, article.pk)
    return JsonResponse({
        "status": "ok",
        "is_saved": is_saved,
        "saved_total": len(saved_article_ids(request)),
    })


@require_POST
def news_toggle_read(request, pk):
    """Toggle the read state of an article for this browser session."""
    article = get_object_or_404(Article, pk=pk)
    is_read = _toggle_session_id(request, READ_SESSION_KEY, article.pk)
    return JsonResponse({
        "status": "ok",
        "is_read": is_read,
        "read_total": len(read_article_ids(request)),
    })


@require_GET
def news_open(request, pk):
    """Count a click-through, mark the article read and redirect to it."""
    article = get_object_or_404(Article, pk=pk)

    # The stored URL is ingest-validated, but re-check before redirecting:
    # only http(s) targets are allowed so javascript:/data: links can't run.
    allowed_hosts = {urlparse(article.url).netloc}
    if not url_has_allowed_host_and_scheme(article.url, allowed_hosts=allowed_hosts):
        return HttpResponseBadRequest("Unsafe link")

    Article.objects.filter(pk=article.pk).update(
        view_count=F("view_count") + 1,
        last_viewed_at=timezone.now(),
    )

    read_ids = read_article_ids(request)
    if article.pk not in read_ids:
        read_ids.add(article.pk)
        request.session[READ_SESSION_KEY] = _clean_ids(sorted(read_ids))

    return redirect(article.url)


@require_GET
def news_image_proxy(request):
    """Serve a stored article thumbnail from our own origin.

    The URL must already belong to an article, so this is not a general
    purpose proxy.  ``image_proxy`` validates the destination and the bytes;
    successful responses are cached on disk for a week.
    """
    url = request.GET.get("u", "").strip()
    if not url:
        return HttpResponseBadRequest("Missing image URL")
    if not Article.objects.filter(image_url=url).exists():
        return HttpResponse(status=404)

    cache_dir = Path(settings.MEDIA_ROOT) / "image-cache"
    cached = read_cache(cache_dir, url)
    if cached:
        data, content_type = cached
    else:
        try:
            data, content_type = fetch_remote_image(url)
        except ImageProxyError as exc:
            return HttpResponse(status=exc.status)
        try:
            write_cache(cache_dir, url, data, content_type)
        except OSError:
            pass

    response = HttpResponse(data, content_type=content_type)
    response["Cache-Control"] = "public, max-age=604800, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@require_GET
def news_export(request, fmt):
    """Download the filtered article list as CSV or XLSX (capped)."""
    if fmt not in ("csv", "xlsx"):
        raise Http404("Unsupported export format")

    articles, _ = _apply_filters(
        request, Article.objects.all(), include_session=False
    )
    rows = article_rows(articles[:MAX_EXPORT_ROWS])

    stamp = timezone.localdate().strftime("%Y%m%d")
    filename = f"hermes-ai-news-{stamp}.{fmt}"

    if fmt == "csv":
        response = HttpResponse(csv_bytes(rows), content_type="text/csv; charset=utf-8")
    else:
        response = HttpResponse(
            xlsx_bytes(rows),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# RSS / JSON API
# ---------------------------------------------------------------------------

@require_GET
def news_rss(request):
    """RSS 2.0 feed with the 50 newest articles matching the filters."""
    articles, _ = _apply_filters(
        request, Article.objects.all(), include_session=False
    )
    articles = articles.order_by(*NEWEST_ORDER)[:RSS_ITEM_LIMIT]

    link = request.build_absolute_uri(reverse("news:news_list"))
    feed = Rss201rev2Feed(
        title="Hermes AI News",
        link=link,
        description="Latest AI news collected by Hermes.",
    )
    for article in articles:
        feed.add_item(
            title=article.title,
            link=article.url,
            description=article.summary,
            pubdate=article.published_at or article.fetched_at,
            unique_id=article.url,
            categories=[topic.name for topic in article.topics.all()],
        )
    return HttpResponse(
        feed.writeString("utf-8"),
        content_type="application/rss+xml; charset=utf-8",
    )


@require_GET
def news_api(request):
    """JSON list of recent articles for lightweight clients."""
    try:
        limit = int(request.GET.get("limit", API_DEFAULT_LIMIT))
    except (TypeError, ValueError):
        limit = API_DEFAULT_LIMIT
    limit = max(1, min(limit, API_MAX_LIMIT))

    params = request.GET.copy()
    for key in ("from", "to", "saved", "unread", "page"):
        params.pop(key, None)
    # Only q/source/topic are supported by the API; dates are UI-only.
    from types import SimpleNamespace

    articles, _ = _apply_filters(
        SimpleNamespace(GET=params),
        Article.objects.all(),
        include_session=False,
    )
    articles = articles.only(
        "id",
        "title",
        "url",
        "source",
        "feed_key",
        "summary",
        "published_at",
        "fetched_at",
        "view_count",
    )[:limit]

    results = [
        {
            "id": article.pk,
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "feed_key": article.feed_key,
            "summary": article.summary,
            "published_at": (
                article.published_at.isoformat() if article.published_at else None
            ),
            "fetched_at": article.fetched_at.isoformat(),
            "topics": [
                {
                    "slug": topic.slug,
                    "name": topic.name,
                    "color": topic.color,
                }
                for topic in article.topics.all()
            ],
            "view_count": article.view_count,
        }
        for article in articles
    ]
    return JsonResponse({"count": len(results), "results": results})


@require_GET
def news_suggest(request):
    """Tiny type-ahead endpoint for the search box."""
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": [], "topics": []})

    articles = (
        Article.objects.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        )
        .only("id", "title", "source", "published_at")
        .order_by(*NEWEST_ORDER)[:SUGGEST_RESULT_LIMIT]
    )
    results = [
        {
            "id": article.pk,
            "title": article.title,
            "source": article.source,
            "published_at": (
                article.published_at.isoformat() if article.published_at else None
            ),
        }
        for article in articles
    ]

    topics = (
        Topic.objects.filter(
            Q(name__icontains=query)
            | Q(slug__icontains=query)
            | Q(keywords__icontains=query)
        )
        .order_by("name")[:SUGGEST_TOPIC_LIMIT]
    )
    topic_results = [
        {"slug": topic.slug, "name": topic.name, "color": topic.color}
        for topic in topics
    ]

    return JsonResponse({"results": results, "topics": topic_results})
