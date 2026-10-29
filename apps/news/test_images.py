"""Tests for apps.news.images (extract_og_image / fetch_og_image)."""

import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.news.image_proxy import ImageProxyError, _sniff_type, _validate_url
from apps.news.images import extract_og_image, fetch_og_image
from apps.news.models import Article


class ExtractOgImageTests(TestCase):
    def test_standard_og_image_property(self):
        html = '<html><head><meta property="og:image" content="https://cdn/x.jpg"></head></html>'
        self.assertEqual(extract_og_image(html), 'https://cdn/x.jpg')

    def test_reversed_attribute_order(self):
        html = '<meta content="https://cdn/x.jpg" property="og:image">'
        self.assertEqual(extract_og_image(html), 'https://cdn/x.jpg')

    def test_name_attribute_variant(self):
        html = '<meta name="og:image" content="https://cdn/x.jpg">'
        self.assertEqual(extract_og_image(html), 'https://cdn/x.jpg')

    def test_twitter_image_fallback_when_no_og(self):
        html = '<meta name="twitter:image" content="https://cdn/tw.jpg">'
        self.assertEqual(extract_og_image(html), 'https://cdn/tw.jpg')

    def test_empty_og_image_then_valid_twitter_wins(self):
        html = (
            '<meta property="og:image" content="">'
            '<meta name="twitter:image" content="https://cdn/tw.jpg">'
        )
        self.assertEqual(extract_og_image(html), 'https://cdn/tw.jpg')

    def test_relative_url_resolved_against_base(self):
        html = '<meta property="og:image" content="/img/hero.jpg">'
        self.assertEqual(
            extract_og_image(html, base_url='https://example.com/story'),
            'https://example.com/img/hero.jpg',
        )

    def test_protocol_relative_url_gets_https_scheme(self):
        html = '<meta property="og:image" content="//cdn.example.com/x.jpg">'
        self.assertEqual(
            extract_og_image(html, base_url='https://example.com/story'),
            'https://cdn.example.com/x.jpg',
        )

    def test_html_entity_ampersand_unescaped(self):
        html = '<meta property="og:image" content="https://cdn/x.jpg?a=1&amp;b=2">'
        self.assertEqual(extract_og_image(html), 'https://cdn/x.jpg?a=1&b=2')

    def test_no_image_tags_returns_empty(self):
        html = '<html><head><title>Story</title></head><body><p>hi</p></body></html>'
        self.assertEqual(extract_og_image(html), '')

    def test_link_rel_image_src_fallback(self):
        html = '<link rel="image_src" href="https://cdn/src.jpg">'
        self.assertEqual(extract_og_image(html), 'https://cdn/src.jpg')

    def test_data_uri_in_og_image_rejected(self):
        html = '<meta property="og:image" content="data:image/png;base64,AAAA">'
        self.assertEqual(extract_og_image(html), '')


class FetchOgImageTests(TestCase):
    def test_unroutable_port_returns_empty_tuple_without_raising(self):
        image_url, final_url = fetch_og_image('http://127.0.0.1:9/', timeout=0.5)
        self.assertEqual(image_url, '')
        self.assertEqual(final_url, 'http://127.0.0.1:9/')


class ImageProxyTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.image_url = 'https://93.184.216.34/thumb.png'
        Article.objects.create(
            title='Proxy test story',
            url='https://example.com/story',
            source='Example',
            feed_key='test',
            image_url=self.image_url,
        )

    def test_rejects_private_host(self):
        with self.assertRaises(ImageProxyError):
            _validate_url('http://127.0.0.1/a.png')

    def test_rejects_link_local_host(self):
        with self.assertRaises(ImageProxyError):
            _validate_url('http://169.254.169.254/latest/meta-data/')

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ImageProxyError):
            _validate_url('file:///etc/passwd')

    def test_rejects_credentials(self):
        with self.assertRaises(ImageProxyError):
            _validate_url('https://user:pass@example.com/a.png')

    def test_rejects_mismatched_magic_bytes(self):
        with self.assertRaises(ImageProxyError):
            _sniff_type(b'<html>not an image</html>', 'image/png')

    def test_mislabeled_jpeg_is_served_as_jpeg(self):
        jpeg = b'\xff\xd8\xff\xdb' + b'\x00' * 32
        self.assertEqual(_sniff_type(jpeg, 'image/webp'), 'image/jpeg')

    def test_proxies_and_caches_image(self):
        png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
        with patch(
            'apps.news.views.fetch_remote_image', return_value=(png, 'image/png')
        ) as fetch:
            first = self.client.get(reverse('news:image_proxy'), {'u': self.image_url})
            second = self.client.get(reverse('news:image_proxy'), {'u': self.image_url})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first['Content-Type'], 'image/png')
        self.assertEqual(first.content, png)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(fetch.call_count, 1)

    def test_rejects_url_not_owned_by_article(self):
        response = self.client.get(
            reverse('news:image_proxy'), {'u': 'https://example.com/other.png'}
        )
        self.assertEqual(response.status_code, 404)

    def test_private_article_url_is_blocked(self):
        blocked = 'http://169.254.169.254/latest/meta-data/'
        Article.objects.create(
            title='SSRF probe',
            url='https://example.com/ssrf',
            source='Example',
            feed_key='test',
            image_url=blocked,
        )
        response = self.client.get(reverse('news:image_proxy'), {'u': blocked})
        self.assertEqual(response.status_code, 403)
