"""SEO layer: robots.txt and sitemap.xml served directly by the project.

Phase 0/1 quick wins. These views are intentionally dependency-light: they
only reverse named routes and read Article timestamps, so they keep working
regardless of view-level changes in apps.core / apps.news.
"""
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse

from apps.news.models import Article

SITE_NAME = "Hermes AI News Agent"

# Static pages: (route name, changefreq, priority)
_STATIC_PAGES = [
    ("landing", "daily", "1.0"),
    ("dashboard", "daily", "0.9"),
    ("news:news_list", "hourly", "0.9"),
]

_ARTICLE_LIMIT = 1000


def _absolute_uri(request, path):
    return request.build_absolute_uri(path)


def _safe_reverse(request, name, args=None):
    """Reverse a route; return None if the route is not mounted yet."""
    try:
        return _absolute_uri(request, reverse(name, args=args))
    except NoReverseMatch:
        return None


def _iso_date(dt):
    if dt is None:
        return None
    return dt.date().isoformat()


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /news/refresh/",
        "Disallow: /news/save/",
        "Disallow: /news/read/",
        "Disallow: /news/open/",
        "Disallow: /news/export/",
        "Disallow: /news/api/",
        "",
        "Sitemap: " + _absolute_uri(request, reverse("sitemap_xml")),
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    latest = (
        Article.objects.order_by("-fetched_at")
        .values_list("fetched_at", flat=True)
        .first()
    )
    latest_lastmod = _iso_date(latest)

    urls = []
    for name, changefreq, priority in _STATIC_PAGES:
        loc = _safe_reverse(request, name)
        if loc is None:
            continue
        entry = ["<url>", "<loc>%s</loc>" % escape(loc)]
        if latest_lastmod:
            entry.append("<lastmod>%s</lastmod>" % latest_lastmod)
        entry.append("<changefreq>%s</changefreq>" % changefreq)
        entry.append("<priority>%s</priority>" % priority)
        entry.append("</url>")
        urls.append("".join(entry))

    articles = Article.objects.order_by("-published_at", "-fetched_at")[:_ARTICLE_LIMIT]
    for article in articles:
        loc = _safe_reverse(request, "news:news_detail", args=[article.pk])
        if loc is None:
            continue
        lastmod = _iso_date(article.published_at or article.fetched_at)
        entry = ["<url>", "<loc>%s</loc>" % escape(loc)]
        if lastmod:
            entry.append("<lastmod>%s</lastmod>" % lastmod)
        entry.append("<changefreq>weekly</changefreq>")
        entry.append("<priority>0.5</priority>")
        entry.append("</url>")
        urls.append("".join(entry))

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml; charset=utf-8")
