"""Tests for Phase 2 F5 saved searches."""

from django.test import Client, TestCase
from django.urls import reverse

from apps.news.models import ReaderProfile


class SavedSearchViewTests(TestCase):
    def test_save_creates_a_chip(self):
        client = Client()
        response = client.post(reverse("news:search_save"), {"name": "My search", "query": "q=test"})
        self.assertEqual(response.status_code, 302)
        profile = ReaderProfile.objects.get()
        self.assertEqual(profile.saved_searches, [{"name": "My search", "query": "q=test"}])

    def test_duplicate_query_updates_name_and_does_not_duplicate(self):
        client = Client()
        client.post(reverse("news:search_save"), {"name": "First", "query": "q=ai"})
        client.post(reverse("news:search_save"), {"name": "Second", "query": "q=ai"})
        profile = ReaderProfile.objects.get()
        self.assertEqual(len(profile.saved_searches), 1)
        self.assertEqual(profile.saved_searches[0]["name"], "Second")
        self.assertEqual(profile.saved_searches[0]["query"], "q=ai")

    def test_invalid_blank_name_query_rejected_without_creating(self):
        client = Client()
        response = client.post(reverse("news:search_save"), {"name": "", "query": "q=test"})
        self.assertEqual(response.status_code, 302)
        client.post(reverse("news:search_save"), {"name": "Name", "query": ""})
        client.post(reverse("news:search_save"), {"name": "   ", "query": "   "})
        profile = ReaderProfile.objects.get()
        self.assertEqual(profile.saved_searches, [])

    def test_delete_removes(self):
        client = Client()
        client.post(reverse("news:search_save"), {"name": "To Delete", "query": "q=rust"})
        profile = ReaderProfile.objects.get()
        self.assertEqual(len(profile.saved_searches), 1)
        response = client.post(reverse("news:search_delete", args=[0]), {"next": reverse("news:news_list")})
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.saved_searches, [])

    def test_chips_render_on_feed(self):
        client = Client()
        client.post(reverse("news:search_save"), {"name": "Visible Chip", "query": "q=chip"})
        feed = client.get(reverse("news:news_list"))
        self.assertEqual(feed.status_code, 200)
        self.assertContains(feed, "Visible Chip")

    def test_anonymous_no_profile_get_feed_does_not_500(self):
        client = Client()
        response = client.get(reverse("news:news_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["saved_searches"]), [])

    def test_delete_rejects_external_next_url(self):
        client = Client()
        client.post(reverse("news:search_save"), {"name": "Guard", "query": "q=guard"})
        response = client.post(
            reverse("news:search_delete", args=[0]),
            {"next": "https://evil.example/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("news:news_list"))

    def test_feed_has_no_nested_forms(self):
        from html.parser import HTMLParser

        class FormDepthParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.depth = 0
                self.max_depth = 0

            def handle_starttag(self, tag, attrs):
                if tag == "form":
                    self.depth += 1
                    self.max_depth = max(self.max_depth, self.depth)

            def handle_endtag(self, tag):
                if tag == "form":
                    self.depth -= 1

        client = Client()
        client.post(reverse("news:search_save"), {"name": "Nested", "query": "q=nested"})
        feed = client.get(reverse("news:news_list") + "?q=nested")
        parser = FormDepthParser()
        parser.feed(feed.content.decode("utf-8"))
        self.assertLessEqual(parser.max_depth, 1)
        self.assertEqual(parser.depth, 0)
