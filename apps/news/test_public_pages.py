"""Public page contract tests: landing, dashboard, detail, sitemap, robots.

These tests pin the Phase 0/1 public surface. They intentionally assert real
content and URL wiring, not just status codes.
"""

from django.test import TestCase
from django.urls import reverse

from apps.news.models import Article, Topic


def make_article(**overrides):
    data = {
        "title": "Test Story About AI",
        "url": "https://example.com/story",
        "summary": "A test summary about artificial intelligence.",
        "source": "Test Source",
        "feed_key": "test",
    }
    data.update(overrides)
    return Article.objects.create(**data)


class PublicPageTests(TestCase):
    def setUp(self):
        self.topic = Topic.objects.create(slug="test-topic", name="Test Topic")
        self.article = make_article()
        self.article.topics.add(self.topic)
        self.detail_url = reverse("news:news_detail", args=[self.article.pk])

    def test_landing_returns_200_with_purpose_and_latest_story(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "20+ sources")
        self.assertContains(response, self.article.title)
        self.assertContains(response, self.detail_url)

    def test_landing_has_seo_and_rss_autodiscovery(self):
        response = self.client.get(reverse("landing"))
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, "AI news in one dashboard")
        self.assertContains(response, 'rel="canonical"')
        self.assertContains(response, 'type="application/rss+xml"')
        self.assertContains(response, 'href="http://testserver/news/rss/"')

    def test_custom_404_page_is_standalone(self):
        from django.test.utils import override_settings

        with override_settings(DEBUG=False):
            response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)
        self.assertNotContains(response, "theme/", status_code=404)

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_home_redirects_to_dashboard(self):
        response = self.client.get("/home/")
        self.assertRedirects(response, reverse("dashboard"))

    def test_article_detail_returns_200_with_article_content(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertContains(response, self.article.summary)
        self.assertContains(response, self.article.source)
        self.assertContains(response, reverse("news:news_open", args=[self.article.pk]))
        self.assertContains(response, 'application/ld+json')

    def test_article_detail_returns_404_for_unknown_pk(self):
        response = self.client.get(reverse("news:news_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_sitemap_is_xml_and_includes_article_detail_url(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("xml", response["Content-Type"].lower())
        body = response.content.decode("utf-8")
        self.assertIn(self.detail_url, body)
        self.assertIn(reverse("news:news_list"), body)
        self.assertNotIn("/news/rss/", body)

    def test_robots_txt_points_at_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"].lower())
        body = response.content.decode("utf-8")
        self.assertIn("Sitemap:", body)
        self.assertIn("/sitemap.xml", body)
        self.assertIn("Disallow: /news/open/", body)

    def test_feed_links_to_detail_page(self):
        response = self.client.get(reverse("news:news_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.detail_url)

    def test_dashboard_links_to_detail_page(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.detail_url)
        self.assertNotContains(response, self.article.url)

    def test_open_endpoint_redirects_to_external_article_url(self):
        response = self.client.get(reverse("news:news_open", args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.article.url)


class EmptyDatabaseTests(TestCase):
    """Every public page must render with zero articles and zero topics."""

    def test_landing_renders_empty_state(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No stories yet")

    def test_feed_renders_empty_state(self):
        response = self.client.get(reverse("news:news_list"))
        self.assertEqual(response.status_code, 200)

    def test_sitemap_renders_without_articles(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"].lower())
