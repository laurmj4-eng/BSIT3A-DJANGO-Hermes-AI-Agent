"""Harvest a shareable preview image from an article page.

The feeds this project ingests (Google News mirrors, openai.com) ship no
thumbnails, so the dashboard stores each story's Open Graph image on
``Article.image_url`` once and reuses it. Standard library only: the project
has no HTTP client dependency and a single GET does not justify one.

Google News RSS URLs are JavaScript interstitials with no ``og:image``.  They
are resolved to the publisher article first through Google's public
``batchexecute`` endpoint, then the publisher page is harvested.  Hacker News
item URLs are resolved to the submitted story URL the same way.

Every outbound request is validated with the image proxy's SSRF checks and
redirect handler; the fetched page size is capped.
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, build_opener

from .image_proxy import _SafeRedirectHandler, _validate_url

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)
MAX_HTML_BYTES = 512 * 1024
GN_MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_IMAGE_URL_LENGTH = 500

GN_BATCH_URL = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'
GN_ARTICLE_RE = re.compile(r'/articles/([^?/#]+)')
GN_SIG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
GN_TS_RE = re.compile(r'data-n-a-ts="(\d+)"')
GN_RESULT_RE = re.compile(r'\[\\?"garturlres\\?",\\?"(.*?)\\?"')
HN_STORY_RE = re.compile(r'<span class="titleline"><a href="([^"]+)"')
HN_LEGACY_RE = re.compile(r'class="storylink" href="([^"]+)"')

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
_IMG_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
_ATTR_RE = re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))"""
)

# Content images that are chrome, not editorial photography.
_IMAGE_NOISE = (
    'logo', 'icon', 'avatar', 'sprite', 'pixel', 'favicon', 'badge',
    'spinner', 'placeholder', 'tracking', 'gravatar', 'emoji',
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
    return extract_content_image(html, base_url)


def extract_content_image(html, base_url=''):
    """Return the first plausible editorial image in the page body.

    Some publishers (notably personal blogs) publish no Open Graph image even
    though the article contains photography.  Skip chrome assets and images
    declared smaller than a content thumbnail.
    """
    for tag in _IMG_RE.findall(html):
        attrs = _attributes(tag)
        src = (attrs.get('src') or attrs.get('data-src') or '').strip()
        lowered = src.lower()
        if not src or lowered.startswith(('data:', 'javascript:')):
            continue
        if any(noise in lowered for noise in _IMAGE_NOISE):
            continue
        alt = (attrs.get('alt') or '').lower()
        if any(noise in alt for noise in ('logo', 'icon', 'avatar')):
            continue
        width = attrs.get('width', '')
        height = attrs.get('height', '')
        if width.isdigit() and int(width) < 320:
            continue
        if height.isdigit() and int(height) < 200:
            continue
        image = _absolute(unescape(src), base_url)
        if image:
            return image
    return ''


def _safe_open(url, timeout, data=None, max_bytes=MAX_HTML_BYTES, accept=None):
    """Open a public URL with proxy-grade SSRF and redirect checks.

    Returns ``(body, final_url, content_type, charset)``.  Raises
    :class:`apps.news.image_proxy.ImageProxyError` for unsafe destinations and
    transport errors for upstream failures.
    """
    _validate_url(url)
    payload = None
    headers = {
        'User-Agent': BROWSER_UA,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': accept or 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    }
    if data is not None:
        payload = urlencode(data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        headers['Accept'] = accept or '*/*'

    request = Request(url, data=payload, headers=headers)
    opener = build_opener(_SafeRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl() or url
        _validate_url(final_url)
        content_type = (response.headers.get('Content-Type') or '').lower()
        charset = response.headers.get_content_charset() or 'utf-8'
        return response.read(max_bytes), final_url, content_type, charset


def resolve_google_news(url, timeout=8.0):
    """Resolve a Google News RSS article URL to the publisher URL, or ''."""
    match = GN_ARTICLE_RE.search(url or '')
    if not match:
        return ''
    article_id = match.group(1)
    try:
        body, _final, _ctype, charset = _safe_open(
            'https://news.google.com/rss/articles/{0}'.format(article_id),
            timeout,
            max_bytes=GN_MAX_HTML_BYTES,
        )
        html = body.decode(charset, errors='replace')
        signature = GN_SIG_RE.search(html)
        timestamp = GN_TS_RE.search(html)
        if not (signature and timestamp):
            return ''
        inner = json.dumps([
            'garturlreq',
            [['X', 'X', ['X', 'X'], None, None, 1, 1, 'US:en', None, 1, None, None, None, None, None, 0, 1],
             'X', 'X', 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
            article_id, int(timestamp.group(1)), signature.group(1),
        ])
        payload = {'f.req': json.dumps([[['Fbv4je', inner]]])}
        body, _final, _ctype, charset = _safe_open(
            GN_BATCH_URL,
            timeout,
            data=payload,
            max_bytes=GN_MAX_HTML_BYTES,
        )
        found = GN_RESULT_RE.search(body.decode(charset, errors='replace'))
        if not found:
            return ''
        resolved = unescape(found.group(1)).replace('\\/', '/')
        if not resolved.startswith(('http://', 'https://')):
            return ''
        _validate_url(resolved)
        return resolved
    except Exception:
        return ''


def resolve_hacker_news(url, timeout=8.0):
    """Resolve an HN item URL to the submitted story URL, or ''."""
    try:
        body, _final, _ctype, charset = _safe_open(url, timeout)
        html = body.decode(charset, errors='replace')
        match = HN_STORY_RE.search(html) or HN_LEGACY_RE.search(html)
        if not match:
            return ''
        story = unescape(match.group(1))
        if not story.startswith(('http://', 'https://')):
            return ''
        _validate_url(story)
        return story
    except Exception:
        return ''


def fetch_og_image(url, timeout=8.0):
    """Follow ``url`` (redirects included) and return ``(image_url, final_url)``.

    Google News and Hacker News indirection is resolved to the publisher page
    before harvesting.  Never raises: transport errors, timeouts and non-HTML
    bodies degrade to an empty image so a backfill can keep walking the queue.
    """
    if not url:
        return '', ''
    page_url = url
    max_bytes = MAX_HTML_BYTES
    try:
        lowered = url.lower()
        if 'news.google.com/rss/articles/' in lowered:
            page_url = resolve_google_news(url, timeout=timeout) or url
            max_bytes = GN_MAX_HTML_BYTES
        elif 'news.ycombinator.com/item' in lowered:
            page_url = resolve_hacker_news(url, timeout=timeout) or url
        try:
            body, final_url, content_type, charset = _safe_open(
                page_url, timeout, max_bytes=max_bytes
            )
        except (HTTPError, URLError, OSError, ValueError):
            return '', page_url
        if content_type and 'html' not in content_type and 'xml' not in content_type:
            return '', final_url
        html = body.decode(charset, errors='replace')
        image = extract_og_image(html, final_url)
        if image:
            _validate_url(image)
        return image, final_url
    except Exception:
        return '', page_url
