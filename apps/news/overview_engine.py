"""Offline extractive overview for news search results.

The overview is intentionally extractive: every bullet is a verbatim slice of a
stored article title or summary. No facts are generated, no network calls are
made, and the result is cheap enough to build on each search request.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

MAX_QUERY_CHARS = 120
MAX_BULLET_CHARS = 240
MAX_SENTENCE_CHARS = 280
MIN_SENTENCE_CHARS = 40
MAX_TERMS = 12
MAX_TITLE_CHARS = 180
MAX_SOURCE_CHARS = 80

_STOPWORDS = {
    "am",
    "an",
    "as",
    "at",
    "be",
    "by",
    "do",
    "go",
    "he",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "no",
    "of",
    "on",
    "or",
    "so",
    "to",
    "up",
    "us",
    "we",
    "about",
    "after",
    "again",
    "also",
    "among",
    "and",
    "are",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "could",
    "did",
    "does",
    "doing",
    "during",
    "each",
    "few",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "into",
    "its",
    "itself",
    "just",
    "more",
    "most",
    "not",
    "now",
    "off",
    "once",
    "only",
    "other",
    "our",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "too",
    "under",
    "until",
    "very",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")
_DEDUPE_RE = re.compile(r"[a-z0-9]+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BOILERPLATE_RE = re.compile(
    r"(the post .{0,160} appeared first on |continue reading|read more|subscribe)",
    re.IGNORECASE,
)


def _clean(value, limit: int | None = None) -> str:
    """Collapse whitespace/control characters and optionally trim to a word."""
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = _CONTROL_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return text


def _safe_url(value) -> str:
    """Only return absolute http(s) URLs; reject javascript:, data:, etc."""
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate:
        return ""
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return candidate


def _article_id(article):
    value = getattr(article, "id", None)
    if value is None:
        value = getattr(article, "pk", None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _query_terms(query: str) -> tuple[str, list[str]]:
    display = _clean(query, MAX_QUERY_CHARS)
    terms: list[str] = []
    for word in _WORD_RE.findall(display.lower()):
        term = word.strip("'’-")[:40]
        if len(term) < 2 or term in _STOPWORDS or term in terms:
            continue
        terms.append(term)
        if len(terms) >= MAX_TERMS:
            break
    return display, terms


def _sentences(article) -> list[str]:
    summary = _clean(getattr(article, "summary", ""))
    if summary:
        parts = [_clean(part, MAX_SENTENCE_CHARS) for part in _SENTENCE_RE.split(summary)]
        usable = [
            part
            for part in parts
            if len(part) >= MIN_SENTENCE_CHARS and not _BOILERPLATE_RE.search(part)
        ]
        if usable:
            return usable
    title = _clean(getattr(article, "title", ""), MAX_SENTENCE_CHARS)
    return [title] if title else []


def _dedupe_key(text: str) -> str:
    words = _DEDUPE_RE.findall(text.lower())[:10]
    return " ".join(words)


def _term_hit(term: str, lowered: str, words: set[str]) -> bool:
    """Short terms must match a token, not a substring like 'ai' in 'said'."""
    if len(term) <= 3:
        return term in words or f"{term}s" in words
    return term in lowered


def _score(text: str, title: str, terms: list[str], position: int) -> float:
    lowered = text.lower()
    title_lowered = title.lower()
    text_words = set(_TOKEN_RE.findall(lowered))
    title_words = set(_TOKEN_RE.findall(title_lowered))
    term_hits = sum(1 for term in terms if _term_hit(term, lowered, text_words))
    title_hits = sum(1 for term in terms if _term_hit(term, title_lowered, title_words))
    score = term_hits * 6.0 + title_hits * 3.0
    if position == 0:
        score += 1.5
    if 60 <= len(text) <= 220:
        score += 0.75
    score += min(len(text), 200) / 400.0
    return score


def build_overview(
    query: str,
    articles,
    max_sources: int = 5,
    max_bullets: int = 4,
) -> dict | None:
    """Build a compact, cited overview from already-ranked articles.

    Returns ``None`` when there is no query, no article, or no usable text.
    """
    display, terms = _query_terms(query)
    if not display or not terms:
        return None

    try:
        rows = list(articles)
    except TypeError:
        return None
    if not rows:
        return None

    max_sources = max(1, min(int(max_sources), 10))
    max_bullets = min(max(1, min(int(max_bullets), 8)), max_sources)

    candidates: list[tuple[float, int, int, str, object, str, str, bool]] = []
    seen_keys: set[str] = set()

    for article_index, article in enumerate(rows):
        title = _clean(getattr(article, "title", ""), MAX_TITLE_CHARS)
        if not title:
            continue
        source = _clean(getattr(article, "source", ""), MAX_SOURCE_CHARS) or "Unknown source"
        url = _safe_url(getattr(article, "url", ""))
        summary_text = _clean(getattr(article, "summary", ""))
        for sentence_index, sentence in enumerate(_sentences(article)):
            bullet = _clean(sentence, MAX_BULLET_CHARS)
            if not bullet:
                continue
            key = _dedupe_key(bullet)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            score = _score(bullet, title, terms, sentence_index)
            from_summary = bool(summary_text and bullet in summary_text)
            if not from_summary:
                # Prefer real summary text; headlines are the fallback when a
                # publisher ships no usable description.
                score -= 4.0
            candidates.append(
                (
                    score,
                    article_index,
                    sentence_index,
                    bullet,
                    article,
                    source,
                    url,
                    from_summary,
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))

    selected: list[tuple] = []
    used_articles: set[int] = set()

    # First pass: one bullet per article so the overview is source-diverse.
    for candidate in candidates:
        article_index = candidate[1]
        if article_index in used_articles:
            continue
        selected.append(candidate)
        used_articles.add(article_index)
        if len(selected) >= max_bullets:
            break

    # Second pass: fill remaining slots, still capped by max_bullets.
    if len(selected) < max_bullets:
        selected_ids = {id(candidate) for candidate in selected}
        for candidate in candidates:
            if id(candidate) in selected_ids:
                continue
            selected.append(candidate)
            if len(selected) >= max_bullets:
                break

    # If two or more real summary excerpts exist, drop headline-only bullets:
    # a shorter, substantive overview beats padding with duplicate titles.
    summary_selected = [candidate for candidate in selected if candidate[7]]
    if len(summary_selected) >= 2:
        selected = summary_selected[:max_bullets]

    bullets = []
    sources = []
    source_keys: set[tuple[int, str]] = set()

    for (
        _score_value,
        article_index,
        _sentence_index,
        text,
        article,
        source,
        url,
        _from_summary,
    ) in selected:
        article_id = _article_id(article)
        bullets.append(
            {
                "text": text,
                "source": source,
                "url": url,
                "article_id": article_id,
            }
        )
        key = (article_index, url or text)
        if len(sources) < max_sources and key not in source_keys:
            source_keys.add(key)
            sources.append(
                {
                    "title": _clean(getattr(article, "title", ""), MAX_TITLE_CHARS),
                    "source": source,
                    "url": url,
                    "article_id": article_id,
                }
            )

    if not bullets or not sources:
        return None

    article_count = len(sources)
    publisher_count = len({source["source"] for source in sources})
    article_noun = "article" if article_count == 1 else "articles"
    publisher_noun = "source" if publisher_count == 1 else "sources"
    verb = "matches" if article_count == 1 else "match"
    lead = (
        f'{article_count} recent {article_noun} from {publisher_count} '
        f'{publisher_noun} {verb} "{display}".'
    )

    return {
        "query": display,
        "lead": lead,
        "bullets": bullets,
        "sources": sources,
        "source_count": article_count,
        "publisher_count": publisher_count,
        "mode": "local",
    }
