"""Fetch and normalise AI news from public RSS/Atom feeds.

Uses only the standard library (``urllib`` + ``xml.etree``) so the project
keeps its existing dependency list. Every feed is isolated: one bad feed
raises ``FeedError`` and never breaks the others.
"""

from __future__ import annotations

import concurrent.futures
import re
import socket
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Keep responses small and fail fast rather than hanging the request.
TIMEOUT = 8
MAX_BYTES = 4_000_000
USER_AGENT = "HermesNewsAgent/1.0 (+https://hermes-agent.nousresearch.com/)"

# name, url, and how to map the feed's XML into a normalised article
# Platform newsrooms come first so the dashboard "Source health" card
# (which shows the first 8) always surfaces per-model coverage.
# All URLs verified live on 2026-10-27.
FEEDS = [
    {
        "key": "openai_news",
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
    },
    {
        "key": "anthropic_news",
        "name": "Anthropic News",
        "url": (
            "https://news.google.com/rss/search?q=site%3Aanthropic.com"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "google_ai_blog",
        "name": "Google AI Blog",
        "url": "https://blog.google/technology/ai/rss/",
    },
    {
        "key": "deepmind_blog",
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
    },
    {
        "key": "meta_ai_news",
        "name": "Meta AI News",
        "url": (
            "https://news.google.com/rss/search?q=site%3Aai.meta.com"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "mistral_ai",
        "name": "Mistral AI",
        "url": "https://mistral.ai/rss.xml",
    },
    {
        "key": "deepseek_news",
        "name": "DeepSeek News",
        "url": (
            "https://news.google.com/rss/search?q=%22DeepSeek%22+when%3A30d"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "groq_news",
        "name": "Groq News",
        "url": (
            "https://news.google.com/rss/search?q=%22Groq%22+%28AI+OR+LPU+OR+inference%29+when%3A30d"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "huggingface_blog",
        "name": "Hugging Face",
        "url": "https://huggingface.co/blog/feed.xml",
    },
    # Tools, releases and free/local model coverage (verified 2026-10-27).
    {
        "key": "simonwillison",
        "name": "Simon Willison",
        "url": "https://simonwillison.net/atom/everything/",
    },
    {
        "key": "hackernews_show",
        "name": "Show HN — AI",
        "url": "https://hnrss.org/show?q=AI",
    },
    {
        "key": "reddit_localllama",
        "name": "r/LocalLLaMA",
        "url": "https://www.reddit.com/r/LocalLLaMA/.rss",
    },
    {
        "key": "ollama_blog",
        "name": "Ollama Blog",
        "url": "https://ollama.com/blog/rss.xml",
    },
    {
        "key": "verge_ai",
        "name": "The Verge — AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "key": "freebuff_blog",
        "name": "Freebuff Blog",
        "url": "https://freebuff.com/blog/rss.xml",
    },
    {
        "key": "opencode_releases",
        "name": "OpenCode Releases",
        "url": "https://github.com/sst/opencode/releases.atom",
        "title_prefix": "OpenCode ",
    },
    {
        "key": "google_free_models",
        "name": "Google News — Free Models",
        "url": (
            "https://news.google.com/rss/search?q=%28%22free+AI+model%22+OR+%22free+tier%22"
            "+OR+%22open+weights%22+OR+%22open-weight%22%29+when%3A14d"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "google_ai",
        "name": "Google News — AI",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en",
        "strip_title_suffix": True,
    },
    {
        "key": "techcrunch_ai",
        "name": "TechCrunch — AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "key": "venturebeat_ai",
        "name": "VentureBeat AI",
        "url": (
            "https://news.google.com/rss/search?q=site%3Aventurebeat.com+AI"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
        "strip_title_suffix": True,
    },
    {
        "key": "arxiv_cs_ai",
        "name": "arXiv cs.AI",
        "url": "https://export.arxiv.org/rss/cs.AI",
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

# URL schemes we allow on ingest. Everything else (javascript:, data:,
# vbscript:, file:, ftp:, relative URLs, ...) is rejected.
_ALLOWED_SCHEMES = ("http", "https")


class FeedError(Exception):
    """Raised when a single feed cannot be fetched or parsed."""


def normalise_url(value: str | None) -> str | None:
    """Return a cleaned absolute http(s) URL, or ``None`` when unsafe.

    Strips surrounding whitespace, requires an absolute URL and only allows
    the ``http`` and ``https`` schemes so ``javascript:``, ``data:``,
    ``vbscript:``, ``file:``, ``ftp:`` and relative URLs never reach the DB.
    """
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return None
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
        return None
    return cleaned


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


def _atom_link(entry: ET.Element) -> str | None:
    """Pick the best ``atom:link`` for an entry.

    Prefers ``rel="alternate"`` (or links with no rel at all) over
    ``rel="self"``, which points back at the feed rather than the article.
    Inspects every ``atom:link`` child instead of only the first one.
    """
    best: str | None = None
    for link in entry.findall("atom:link", NS):
        href = (link.get("href") or "").strip()
        if not href:
            continue
        rel = (link.get("rel") or "").strip().lower()
        if rel in ("", "alternate"):
            return href
        if best is None:
            best = href
    return best


def _is_echo_of(title: str, summary: str) -> bool:
    """True when *summary* is just *title* repeated, plus maybe a publisher.

    Google News emits ``<title>Headline - Publisher</title>`` but
    ``<description>Headline Publisher</description>`` — the separator is dropped
    by tag stripping — so a plain ``startswith`` test misses it.

    Only two shapes count as an echo:
    1. the normalised words are exactly the title's words, or
    2. the summary equals the title words plus at most 6 trailing publisher
       words AND the summary adds no sentence punctuation beyond the
       publisher tail.

    A meaningful sentence that merely *starts* with the title is not an echo.
    """
    def norm(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text).lower().split()

    a, b = norm(title), norm(summary)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(b) > len(a) and b[: len(a)] == a and len(b) - len(a) <= 6:
        # The extra words must look like a publisher tail, not a sentence:
        # no sentence punctuation inside the summary beyond the title itself.
        tail = summary[len(title):] if summary.lower().startswith(title.lower()) else None
        if tail is not None:
            body = summary[: len(title)]
            if not re.search(r"[.!?]", body):
                return True
        else:
            # Title was normalised differently (punctuation); fall back to
            # checking the whole summary for sentence punctuation.
            if not re.search(r"[.!?]", summary):
                return True
    return False


def _parse_date(value: str | None) -> datetime | None:
    """Best-effort RFC822 / ISO8601 date parsing, always returning aware UTC."""
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
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def fetch_feed(spec: dict) -> list[dict]:
    """Fetch one feed and return a list of normalised article dicts.

    Raises ``FeedError`` on any network or parse problem so the caller can
    record the failure per-feed instead of failing the whole refresh.
    """
    def _download() -> bytes:
        req = Request(spec["url"], headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(MAX_BYTES)

    try:
        raw = _download()
    except (socket.timeout, OSError, ValueError) as exc:
        raise FeedError(f"{spec['name']}: {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        # Some CDNs answer 200 with an empty or bot-check body when several
        # Google-hosted feeds are hit at once; back off, then retry once.
        time.sleep(0.6)
        try:
            root = ET.fromstring(_download())
        except (ET.ParseError, socket.timeout, OSError, ValueError) as exc:
            raise FeedError(f"{spec['name']}: malformed XML ({exc})") from exc

    # RSS 2.0 uses <item>, Atom uses <entry>
    entries = root.findall(".//item") or root.findall(".//atom:entry", NS)
    if not entries:
        raise FeedError(f"{spec['name']}: no items found")

    articles = []
    for entry in entries:
        title = _clean(_first(entry, "title", "atom:title"), limit=300)
        raw_title = title
        if spec.get("strip_title_suffix") and title:
            # Google News appends " - Publisher". Drop that tail only.
            head, sep, tail = title.rpartition(" - ")
            if sep and 0 < len(tail) <= 40:
                title = head.strip()
        if spec.get("title_prefix") and title:
            title = spec["title_prefix"] + title
        link = _atom_link(entry) or _first(entry, "link")
        if not title or not link:
            continue

        url = normalise_url(link)
        if not url:
            continue  # skip entries without a safe, absolute URL

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
        # Compare the pre-strip title too, so its publisher tail still matches.
        if summary and (
            _is_echo_of(title, summary)
            or (raw_title != title and _is_echo_of(raw_title, summary))
        ):
            summary = ""
        published = _parse_date(
            _first(entry, "pubDate", "atom:published", "atom:updated", "dc:date")
        )

        articles.append(
            {
                "source": spec["name"],
                "feed_key": spec["key"],
                "title": title,
                "url": url,
                "summary": summary,
                "published_at": published,
            }
        )

    if not articles:
        raise FeedError(f"{spec['name']}: items were empty after parsing")
    return articles


def fetch_all_feeds(per_feed_limit: int = 25) -> tuple[list[dict], list[dict]]:
    """Fetch every configured feed in parallel.

    Returns ``(articles, errors)`` where *errors* holds one dict per feed that
    failed, so the UI can report partial success instead of failing outright.
    Articles keep deterministic ordering by feed order.
    """
    errors: list[dict] = []
    results: list[list[dict] | None] = [None] * len(FEEDS)

    # Keep the burst small so Google-hosted feeds don't answer with empty
    # 200s, and so a refresh doesn't spike the host machine.
    workers = min(5, len(FEEDS))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_feed, spec) for spec in FEEDS]
        for idx, future in enumerate(futures):
            spec = FEEDS[idx]
            try:
                results[idx] = future.result()[:per_feed_limit]
            except FeedError as exc:
                errors.append(
                    {"key": spec["key"], "source": spec["name"], "error": str(exc)}
                )
            except Exception as exc:  # defensive: never lose a feed silently
                errors.append(
                    {"key": spec["key"], "source": spec["name"], "error": str(exc)}
                )

    articles: list[dict] = []
    for batch in results:
        if batch:
            articles.extend(batch)
    return articles, errors
