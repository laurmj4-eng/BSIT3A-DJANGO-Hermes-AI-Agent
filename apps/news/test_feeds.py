"""Tests for apps.news.feeds — no network, stdlib fixtures only."""

from datetime import datetime, timezone
from unittest.mock import patch
from urllib.request import URLError
import io
import types

from django.test import SimpleTestCase

from apps.news.feeds import (
    FEEDS,
    FeedError,
    _is_echo_of,
    _parse_date,
    fetch_all_feeds,
    fetch_feed,
    normalise_url,
)


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_urlopen(body: bytes):
    def _open(req, timeout=None):
        return _FakeResponse(body)

    return _open


class NormaliseUrlTests(SimpleTestCase):
    def test_accepts_https(self):
        self.assertEqual(normalise_url("  https://example.com/a  "), "https://example.com/a")

    def test_accepts_http(self):
        self.assertEqual(normalise_url("http://example.com/"), "http://example.com/")

    def test_rejects_javascript(self):
        self.assertIsNone(normalise_url("javascript:alert(1)"))

    def test_rejects_data(self):
        self.assertIsNone(normalise_url("data:text/html;base64,AAAA"))

    def test_rejects_relative(self):
        self.assertIsNone(normalise_url("/news/story"))

    def test_rejects_empty(self):
        self.assertIsNone(normalise_url(""))
        self.assertIsNone(normalise_url(None))

    def test_rejects_ftp_and_file(self):
        self.assertIsNone(normalise_url("ftp://example.com/x"))
        self.assertIsNone(normalise_url("file:///C:/x"))


class ParseDateTests(SimpleTestCase):
    def test_rfc822_utc(self):
        dt = _parse_date("Tue, 27 Oct 2026 10:30:00 +0000")
        self.assertEqual(dt, datetime(2026, 10, 27, 10, 30, tzinfo=timezone.utc))

    def test_iso_offset_converted_to_utc(self):
        dt = _parse_date("2026-10-27T12:30:00+02:00")
        self.assertEqual(dt, datetime(2026, 10, 27, 10, 30, tzinfo=timezone.utc))

    def test_none(self):
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date("not a date"))


RSS_XML = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>OpenAI ships new model</title>
    <link>https://example.com/story-1</link>
    <description>A meaningful summary about the new model.</description>
    <pubDate>Tue, 27 Oct 2026 10:30:00 +0000</pubDate>
  </item>
</channel></rss>"""

ATOM_XML = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>OpenAI ships new model</title>
    <link rel="self" href="https://example.com/feed/self"/>
    <link rel="alternate" href="https://example.com/story-2"/>
    <summary>A meaningful summary about the new model.</summary>
    <published>2026-10-27T12:30:00+02:00</published>
  </entry>
</feed>"""


class FetchFeedTests(SimpleTestCase):
    def test_rss_fixture(self):
        with patch("apps.news.feeds.urlopen", _fake_urlopen(RSS_XML)):
            articles = fetch_feed(FEEDS[0])
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["url"], "https://example.com/story-1")
        self.assertEqual(articles[0]["published_at"].hour, 10)

    def test_atom_prefers_alternate_link(self):
        with patch("apps.news.feeds.urlopen", _fake_urlopen(ATOM_XML)):
            articles = fetch_feed(FEEDS[0])
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["url"], "https://example.com/story-2")
        self.assertEqual(articles[0]["published_at"].hour, 10)

    def test_skips_entries_without_valid_url(self):
        body = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item><title>Bad</title><link>javascript:alert(1)</link></item>
          <item><title>Rel</title><link>/relative/only</link></item>
          <item><title>Good</title><link>https://example.com/ok</link></item>
        </channel></rss>"""
        with patch("apps.news.feeds.urlopen", _fake_urlopen(body)):
            articles = fetch_feed(FEEDS[0])
        self.assertEqual([a["url"] for a in articles], ["https://example.com/ok"])

    def test_strips_google_news_publisher_suffix(self):
        body = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item>
            <title>OpenAI ships new model - The Verge</title>
            <link>https://example.com/story-3</link>
          </item>
        </channel></rss>"""
        spec = {
            "key": "google_test",
            "name": "Google News - Test",
            "url": "https://news.google.com/rss/search?q=test",
            "strip_title_suffix": True,
        }
        with patch("apps.news.feeds.urlopen", _fake_urlopen(body)):
            articles = fetch_feed(spec)
        self.assertEqual(articles[0]["title"], "OpenAI ships new model")

    def test_keeps_publisher_suffix_without_flag(self):
        body = b"""<?xml version="1.0"?>
        <rss version="2.0"><channel>
          <item>
            <title>OpenAI ships new model - The Verge</title>
            <link>https://example.com/story-4</link>
          </item>
        </channel></rss>"""
        spec = {
            "key": "plain_test",
            "name": "Plain Test",
            "url": "https://example.com/feed.xml",
        }
        with patch("apps.news.feeds.urlopen", _fake_urlopen(body)):
            articles = fetch_feed(spec)
        self.assertEqual(articles[0]["title"], "OpenAI ships new model - The Verge")

    def test_network_error_raises_feed_error(self):
        def _boom(req, timeout=None):
            raise URLError("down")

        with patch("apps.news.feeds.urlopen", _boom):
            with self.assertRaises(FeedError):
                fetch_feed(FEEDS[0])


class IsEchoOfTests(SimpleTestCase):
    def test_exact_echo(self):
        self.assertTrue(_is_echo_of("Big AI news", "Big AI news"))

    def test_title_plus_publisher(self):
        self.assertTrue(_is_echo_of("Big AI news - The Post", "Big AI news The Post"))

    def test_meaningful_sentence_not_echo(self):
        summary = "Big AI news: regulators said Tuesday that new rules will apply to every vendor."
        self.assertFalse(_is_echo_of("Big AI news", summary))

    def test_long_continuation_not_echo(self):
        summary = "Big AI news and then a whole lot more detail follows here indeed."
        self.assertFalse(_is_echo_of("Big AI news", summary))


class FetchAllFeedsTests(SimpleTestCase):
    def test_isolates_failing_feed(self):
        def fake_fetch(spec):
            if spec["key"] == "arxiv_cs_ai":
                raise FeedError(f"{spec['name']}: boom")
            return [{"title": "t", "url": "https://x.example/" + spec["key"]}]

        with patch("apps.news.feeds.fetch_feed", fake_fetch):
            articles, errors = fetch_all_feeds()

        self.assertEqual(len(articles), len(FEEDS) - 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["key"], "arxiv_cs_ai")
        self.assertEqual(errors[0]["source"], "arXiv cs.AI")
        self.assertIn("boom", errors[0]["error"])

    def test_order_follows_feed_order(self):
        def fake_fetch(spec):
            return [{"title": spec["key"], "feed_key": spec["key"], "url": "https://x.example/" + spec["key"]}]

        with patch("apps.news.feeds.fetch_feed", fake_fetch):
            articles, errors = fetch_all_feeds()
        self.assertEqual([a["feed_key"] for a in articles], [s["key"] for s in FEEDS])
        self.assertEqual(errors, [])
