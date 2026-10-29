"""Harvest a shareable preview image from an article page.

The feeds this project ingests (Google News mirrors, openai.com) ship no
thumbnails, so the dashboard stores each story's Open Graph image on
``Article.image_url`` once and reuses it. Standard library only: the project
has no HTTP client dependency and a single GET does not justify one.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)
MAX_HTML_BYTES = 512 * 1024

# First match wins, so og:image beats the twitter fallback.
_IMAGE_META_KEYS = (
    'og:image',
    'og:image:url',
    'og:image:secure_url',
    'twitter:image',
    'twitter:image:src',
)

_META_RE = re.compile(r'<meta\b[^>]*>', re.IGNORECASE)
_LINK_RE = re.compile(r'<link\b[^>]*>', re.IGNORECASE)
_ATTR_RE = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))"""
)


def _attributes(tag):
    """Map attribute name -> value for one start tag, order independent."""
    attrs = {}
    for match in _ATTR_RE.finditer(tag):
        name = match.group(1).lower()
        value = match.group(2) or match.group(3) or match.group(4) or ''
        attrs[name] = value
    return attrs


def _absolute(value, base_url):
    """Resolve a candidate to an http(s) URL, or '' when unusable."""
    value = value.strip()
    if not value:
        return ''
    if value.startswith('//'):
        scheme = urlparse(base_url).scheme or 'https'
        return '{0}:{1}'.format(scheme, value)
    if value.startswith(('http://', 'https://')):
        return value
    if base_url:
        resolved = urljoin(base_url, value)
        if resolved.startswith(('http://', 'https://')):
            return resolved
    return ''


def extract_og_image(html, base_url=''):
    """Return the best preview image URL found in ``html``, or ''."""
    if not html:
        return ''
    for tag in _META_RE.findall(html):
        attrs = _attributes(tag)
        key = (attrs.get('property') or attrs.get('name') or '').strip().lower()
        if key not in _IMAGE_META_KEYS:
            continue
        image = _absolute(unescape(attrs.get('content', '')), base_url)
        if image:
            return image
    for tag in _LINK_RE.findall(html):
        attrs = _attributes(tag)
        if (attrs.get('rel') or '').strip().lower() != 'image_src':
            continue
        image = _absolute(unescape(attrs.get('href', '')), base_url)
        if image:
            return image
    return ''


def fetch_og_image(url, timeout=8.0):
    """Follow ``url`` (redirects included) and return ``(image_url, final_url)``.

    Never raises: transport errors, timeouts and non-HTML bodies degrade to an
    empty image so a backfill can keep walking the queue.
    """
    if not url:
        return '', ''
    final_url = url
    try:
        request = Request(
            url,
            headers={
                'User-Agent': BROWSER_UA,
                'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            },
        )
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl() or url
            content_type = (response.headers.get('Content-Type') or '').lower()
            if content_type and 'html' not in content_type:
                return '', final_url
            raw = response.read(MAX_HTML_BYTES)
            charset = response.headers.get_content_charset() or 'utf-8'
        return extract_og_image(raw.decode(charset, errors='replace'), final_url), final_url
    except Exception:
        return '', final_url
