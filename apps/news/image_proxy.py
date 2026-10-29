"""Same-origin thumbnail proxy for article preview images.

Many publishers send ``Cross-Origin-Resource-Policy: same-origin`` on their
Open Graph images, so a browser refuses to render them from our page even
though the URL is public.  Fetching the bytes server-side and serving them
from our own origin sidesteps that without weakening browser isolation.

Security model:
* only URLs already stored on an :class:`~apps.news.models.Article` are
  accepted (the view enforces this before calling in here);
* scheme, port, credentials, DNS results and redirects are validated, and
  private / loopback / link-local / reserved addresses are rejected;
* only raster image types with matching magic bytes are accepted;
* responses are capped at 5 MiB and cached on disk for seven days.

Standard library only: the project deliberately has no HTTP client
dependency.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {None, 80, 443}
ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class ImageProxyError(Exception):
    """A safe, user-facing proxy failure with an HTTP status."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def _validate_url(url):
    """Reject anything that could reach a private network or a weird port."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ImageProxyError("unsupported scheme", 400)
    if not parsed.hostname:
        raise ImageProxyError("missing host", 400)
    if parsed.username or parsed.password:
        raise ImageProxyError("credentials are not allowed", 400)

    try:
        port = parsed.port
    except ValueError:
        raise ImageProxyError("invalid port", 400)
    if port not in ALLOWED_PORTS:
        raise ImageProxyError("port is not allowed", 403)

    default_port = 443 if parsed.scheme == "https" else 80
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname, port or default_port, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ImageProxyError("host cannot be resolved", 502)

    if not addresses:
        raise ImageProxyError("host cannot be resolved", 502)

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ImageProxyError("host is not public", 403)
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _detect_type(data):
    """Identify an allowed raster type from its magic bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return "image/avif"
    return None


def _sniff_type(data, header_type=None):
    """Return the type proven by the bytes.

    Some CDNs mislabel images (a JPEG body served as ``image/webp``), so the
    declared header is advisory only; the magic bytes decide what we serve.
    Anything that is not a known raster image is rejected.
    """
    detected = _detect_type(data)
    if detected is None:
        raise ImageProxyError("unsupported content type", 415)
    return detected


def fetch_remote_image(url, timeout=8.0):
    """Fetch a remote image, validating every URL and byte along the way."""
    _validate_url(url)
    parsed = urlparse(url)
    request = Request(
        url,
        headers={
            "User-Agent": BROWSER_UA,
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif",
            "Accept-Encoding": "identity",
            "Referer": "{0}://{1}/".format(parsed.scheme, parsed.netloc),
        },
    )
    opener = build_opener(_SafeRedirectHandler())

    try:
        with opener.open(request, timeout=timeout) as response:
            _validate_url(response.geturl() or url)
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > MAX_IMAGE_BYTES:
                raise ImageProxyError("image is too large", 413)
            data = response.read(MAX_IMAGE_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
    except ImageProxyError:
        raise
    except HTTPError as exc:
        raise ImageProxyError("upstream returned {0}".format(exc.code), 502)
    except (URLError, socket.timeout, TimeoutError):
        raise ImageProxyError("upstream timed out", 504)
    except OSError:
        raise ImageProxyError("upstream request failed", 502)

    if len(data) > MAX_IMAGE_BYTES:
        raise ImageProxyError("image is too large", 413)
    return data, _sniff_type(data, content_type)


def _cache_paths(cache_dir, url):
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return (
        os.path.join(cache_dir, key + ".bin"),
        os.path.join(cache_dir, key + ".ct"),
    )


def read_cache(cache_dir, url):
    """Return ``(bytes, content_type)`` from a fresh cache entry, or None."""
    data_path, type_path = _cache_paths(cache_dir, url)
    try:
        if time.time() - os.path.getmtime(data_path) > CACHE_TTL_SECONDS:
            return None
        with open(data_path, "rb") as handle:
            data = handle.read(MAX_IMAGE_BYTES + 1)
        with open(type_path, "r", encoding="ascii") as handle:
            content_type = handle.read().strip()
    except (OSError, ValueError):
        return None

    if len(data) > MAX_IMAGE_BYTES or content_type not in ALLOWED_TYPES:
        return None
    if _detect_type(data) != content_type:
        return None
    return data, content_type


def write_cache(cache_dir, url, data, content_type):
    """Atomically persist an image and its type sidecar."""
    os.makedirs(cache_dir, exist_ok=True)
    data_path, type_path = _cache_paths(cache_dir, url)
    handle, temp_path = tempfile.mkstemp(dir=cache_dir, prefix=".tmp-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temp_path, data_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    with open(type_path, "w", encoding="ascii") as stream:
        stream.write(content_type)
