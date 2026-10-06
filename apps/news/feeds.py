"""Fetch and normalise AI news from public RSS/Atom feeds.

Uses only the standard library (``urllib`` + ``xml.etree``) so the project
keeps its existing dependency list. Every feed is isolated: one bad feed
raises ``FeedError`` and never breaks the others.
"""

from __future__ import annotations

import re
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.request import Request, urlopen

# Keep responses small and fail fast rather than hanging the request.
TIMEOUT = 8
MAX_BYTES = 4_000_000
USER_AGENT = "HermesNewsAgent/1.0 (+https://hermes-agent.nousresearch.com/)"

# name, url, and how to map the feed's XML into a normalised article
FEEDS = [
    {
        "key": "google_ai",
        "name": "Google News — AI",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "key": "techcrunch_ai",
        "name": "TechCrunch — AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "key": "venturebeat_ai",
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
    },
    {
        "key": "arxiv_cs_ai",
        "name": "arXiv cs.AI",
        "url": "http://export.arxiv.org/rss/cs.AI",
    },
    {
        "key": "mit_news_ai",
        "name": "MIT News — AI",
        "url": "https://news.mit.edu/rss/topic/artificial-intelligence2",
    },
]

# XML namespaces we care about when normalising
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_TAG_RE = re.compile(r"<[^>]+>")


class FeedError(Exception):
    """Raised when a single feed cannot be fetched or parsed."""


def _clean(text: str | None, limit: int = 400) -> str:
    """Strip HTML tags/entities from a feed summary and clamp its length."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."
    return text


def _first(entry: ET.Element, *paths: str) -> str | None:
    """Return the first non-empty text value found at any of the given paths."""
    for path in paths:
        node = entry.find(path, NS)
        if node is not None:
            # <link> in Atom carries the URL as an attribute, not as text
            href = node.get("href")
            if href:
                return href.strip()
            if node.text and node.text.strip():
                return node.text.strip()
    return None


def _is_echo_of(title: str, summary: str) -> bool:
    """True when *summary* is just *title* repeated, plus maybe a publisher.

    Google News emits ``<title>Headline - Publisher</title>`` but
    ``<description>Headline Publisher</description>`` — the separator is dropped
    by tag stripping — so a plain ``startswith`` test misses it. Compare with
    punctuation removed and allow a short trailing publisher name.
    """
    def norm(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text).lower().split()

    a, b = norm(title), norm(summary)
    if not a or not b:
        return False
    if a == b or b[:len(a)] == a:
        return True
    # Headline + publisher name, e.g. "... - The Washington Post"
    return len(b) > len(a) and b[:len(a)] == a and len(b) - len(a) <= 6


def _parse_date(value: str | None) -> datetime | None:
    """Best-effort RFC822 / ISO8601 date parsing."""
    if not value:
        return None
    from email.utils import parsedate_to_datetime

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_feed(spec: dict) -> list[dict]:
    """Fetch one feed and return a list of normalised article dicts.

    Raises ``FeedError`` on any network or parse problem so the caller can
    record the failure per-feed instead of failing the whole refresh.
    """
    try:
        req = Request(spec["url"], headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES)
    except (socket.timeout, OSError, ValueError) as exc:
        raise FeedError(f"{spec['name']}: {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FeedError(f"{spec['name']}: malformed XML ({exc})") from exc

    # RSS 2.0 uses <item>, Atom uses <entry>
    entries = root.findall(".//item") or root.findall(".//atom:entry", NS)
    if not entries:
        raise FeedError(f"{spec['name']}: no items found")

    articles = []
    for entry in entries:
        title = _clean(_first(entry, "title", "atom:title"), limit=300)
        link = _first(entry, "link", "atom:link")
        if not title or not link:
            continue

        summary = _clean(
            _first(
                entry,
                "description",
                "atom:summary",
                "content:encoded",
            )
        )

        # Google News repeats the headline in <description>, which makes the
        # card read twice. Feeds append the publisher name after the headline
        # and strip the separator, so normalise both sides before comparing.
        if summary and _is_echo_of(title, summary):
            summary = ""
        published = _parse_date(
            _first(entry, "pubDate", "atom:published", "atom:updated", "dc:date")
        )

        articles.append(
            {
                "source": spec["name"],
                "feed_key": spec["key"],
                "title": title,
                "url": link,
                "summary": summary,
                "published_at": published,
            }
        )

    if not articles:
        raise FeedError(f"{spec['name']}: items were empty after parsing")
    return articles


def fetch_all_feeds(per_feed_limit: int = 25) -> tuple[list[dict], list[dict]]:
    """Fetch every configured feed.

    Returns ``(articles, errors)`` where *errors* holds one dict per feed that
    failed, so the UI can report partial success instead of failing outright.
    """
    articles: list[dict] = []
    errors: list[dict] = []

    for spec in FEEDS:
        try:
            articles.extend(fetch_feed(spec)[:per_feed_limit])
        except FeedError as exc:
            errors.append({"source": spec["name"], "error": str(exc)})

    return articles, errors