"""Automatic latest-model detection from cached news articles."""

from __future__ import annotations

import re
from typing import Any

from django.utils import timezone

# Official feed keys per model publisher (derived from feeds.py).
MODEL_RULES: dict[str, dict[str, Any]] = {
    "gpt": {
        "label": "GPT-{v}",
        "pattern": re.compile(r"\bGPT[-\s]?(?P<v>\d+(?:\.\d+)?)\b", re.IGNORECASE),
        "feeds": ("openai_news",),
    },
    "claude": {
        "label": "Claude {v}",
        "pattern": re.compile(
            r"\bClaude\s+(?:(?P<tier>Opus|Sonnet|Haiku)\s+)?(?P<v>\d+(?:\.\d+)?)\b",
            re.IGNORECASE,
        ),
        "feeds": ("anthropic_news",),
    },
    "gemini": {
        "label": "Gemini {v}",
        "pattern": re.compile(r"\bGemini\s+(?P<v>\d+(?:\.\d+)?)\b", re.IGNORECASE),
        "feeds": ("google_ai_blog", "deepmind_blog"),
    },
    "llama": {
        "label": "Llama {v}",
        "pattern": re.compile(r"\bLlama\s+(?P<v>\d+(?:\.\d+)?)\b", re.IGNORECASE),
        "feeds": ("meta_ai_news",),
    },
    "mistral": {
        "label": "Mistral Large {v}",
        "pattern": re.compile(
            r"\bMistral\s+Large\s+(?P<v>\d+(?:\.\d+)?)\b", re.IGNORECASE
        ),
        "feeds": ("mistral_ai",),
    },
    "deepseek": {
        "label": "DeepSeek V{v}",
        "pattern": re.compile(
            r"\bDeepSeek[-\s]?V(?P<v>\d+(?:\.\d+)?)\b", re.IGNORECASE
        ),
        "feeds": ("deepseek_news",),
    },
}


def parse_version(text: str) -> tuple[int, ...]:
    """Return a comparable tuple of ints from a version string."""
    if text is None:
        return ()
    value = str(text).strip()
    if not value:
        return ()
    try:
        return tuple(int(part) for part in value.split("."))
    except (ValueError, TypeError):
        return ()


def detect_in_text(text: str) -> dict[str, dict[str, str]]:
    """Detect the highest version of each model mentioned in *text*."""
    result: dict[str, dict[str, str]] = {}
    if not text:
        return result
    for key, rule in MODEL_RULES.items():
        best: tuple[tuple[int, ...], str, str] | None = None
        for match in rule["pattern"].finditer(text):
            version_str = match.group("v")
            version_tuple = parse_version(version_str)
            tier = match.groupdict().get("tier")
            if key == "claude" and tier:
                label = f"Claude {tier} {version_str}"
            else:
                label = rule["label"].format(v=version_str)
            if best is None or version_tuple > best[0]:
                best = (version_tuple, version_str, label)
        if best is not None:
            result[key] = {"label": best[2], "version": best[1]}
    return result


def scan_articles(queryset: Any = None, limit: int = 400) -> dict[str, dict[str, str]]:
    """Scan recent articles and return the best detected model per key."""
    from .models import Article

    if queryset is None:
        qs = Article.objects.all()
    else:
        qs = queryset
    try:
        articles = list(qs.order_by("-published_at", "-fetched_at")[:limit])
    except Exception:
        articles = list(qs)[:limit]

    # Whether each key appears in at least one title (global decision).
    title_has: dict[str, bool] = {key: False for key in MODEL_RULES}
    for article in articles:
        found = detect_in_text(getattr(article, "title", "") or "")
        for key in found:
            title_has[key] = True

    best: dict[str, dict[str, Any]] = {key: None for key in MODEL_RULES}  # type: ignore[assignment]
    for article in articles:
        for key, rule in MODEL_RULES.items():
            if title_has[key]:
                text = getattr(article, "title", "") or ""
            else:
                text = getattr(article, "summary", "") or ""
            found = detect_in_text(text)
            if key not in found:
                continue
            info = found[key]
            version_tuple = parse_version(info["version"])
            official = getattr(article, "feed_key", "") in rule["feeds"]
            candidate = {
                "version_tuple": version_tuple,
                "version": info["version"],
                "label": info["label"],
                "article": article,
                "official": official,
            }
            current = best[key]
            if current is None:
                best[key] = candidate
            elif version_tuple > current["version_tuple"]:
                best[key] = candidate
            elif version_tuple == current["version_tuple"] and official and not current["official"]:
                best[key] = candidate

    result: dict[str, dict[str, str]] = {}
    for key, candidate in best.items():
        if not candidate:
            continue
        article = candidate["article"]
        result[key] = {
            "label": candidate["label"],
            "version": candidate["version"],
            "source_title": getattr(article, "title", "") or "",
            "source_url": getattr(article, "url", "") or "",
        }
    return result


def update_latest_models(queryset: Any = None) -> dict[str, str]:
    """Create or update stored PlatformModel rows when a higher version is found."""
    result: dict[str, str] = {}
    try:
        detected = scan_articles(queryset=queryset)
    except Exception:
        return result
    try:
        from .models import PlatformModel
    except Exception:
        return result
    from django.utils import timezone as _tz

    for key, info in detected.items():
        try:
            detected_tuple = parse_version(info["version"])
            existing = PlatformModel.objects.filter(key=key).first()
            if existing is None:
                PlatformModel.objects.create(
                    key=key,
                    label=info["label"],
                    version=info["version"],
                    source_title=info["source_title"],
                    source_url=info["source_url"],
                    detected_at=_tz.now(),
                )
                result[key] = info["label"]
            else:
                if parse_version(existing.version) < detected_tuple:
                    existing.label = info["label"]
                    existing.version = info["version"]
                    existing.source_title = info["source_title"]
                    existing.source_url = info["source_url"]
                    existing.detected_at = _tz.now()
                    existing.save()
                    result[key] = info["label"]
        except Exception:
            continue
    return result


def current_models() -> dict[str, dict[str, Any]]:
    """Return stored models in one query; safe on pre-migration deploys."""
    try:
        from .models import PlatformModel
    except Exception:
        return {}
    try:
        from django.db import OperationalError, ProgrammingError
    except Exception:
        return {}
    try:
        rows = PlatformModel.objects.all()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[row.key] = {
                "label": row.label,
                "version": row.version,
                "source_title": row.source_title,
                "source_url": row.source_url,
                "detected_at": row.detected_at,
            }
        return result
    except (OperationalError, ProgrammingError):
        return {}