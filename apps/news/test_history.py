"""Tests for Phase 2 F7 history + saved exports."""
import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.news.models import Article, ReaderProfile


class HistoryViewTests(TestCase):
    def setUp(self):
        self.article = Article.objects.create(
            title="History Story A",
            url="https://example.com/history-a",
            summary="First history story.",
            source="History Source",
            feed_key="history",
        )
        self.other = Article.objects.create(
            title="History Story B",
            url="https://example.com/history-b",
            summary="Second history story.",
            source="History Source",
            feed_key="history",
        )

    def test_anonymous_history_empty_200(self):
        client = Client()
        response = client.get(reverse("news:news_history"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["history_count"], 0)
        self.assertEqual(list(response.context["items"]), [])
        self.assertContains(response, "No reading history yet")
        self.assertContains(response, "css/news-feed.css")

    def test_open_records_history_and_page_shows_article(self):
        client = Client()
        response = client.get(reverse("news:news_open", args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)
        history = client.get(reverse("news:news_history"))
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, self.article.title)
        self.assertNotContains(history, self.other.title)
        self.assertEqual(history.context["history_count"], 1)

    def test_malformed_history_entries_ignored(self):
        client = Client()
        # Create profile via open, then overwrite history with malformed data.
        client.get(reverse("news:news_open", args=[self.other.pk]))
        profile = ReaderProfile.objects.get()
        profile.history = [
            {"id": "x", "at": "t"},
            {"id": 5},
            "junk",
            {"id": self.article.pk, "at": "2026-01-01T00:00:00+00:00"},
            {"id": 999999, "at": "2026-01-02T00:00:00+00:00"},
        ]
        profile.save(update_fields=["history", "updated_at"])
        response = client.get(reverse("news:news_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.title)
        self.assertNotContains(response, self.other.title)
        self.assertEqual(response.context["history_count"], 1)

    def test_history_entries_public_wrapper_sanitizes(self):
        from apps.news.profile import history_entries

        profile = ReaderProfile.objects.create()
        profile.history = [
            {"id": "x", "at": "t"},
            {"id": self.article.pk, "at": "2026-01-01T00:00:00+00:00"},
            "junk",
        ]
        profile.save()
        entries = history_entries(profile)
        self.assertEqual(entries, [{"id": self.article.pk, "at": "2026-01-01T00:00:00+00:00"}])
        self.assertEqual(history_entries(None), [])


class SavedExportTests(TestCase):
    def setUp(self):
        self.kept = Article.objects.create(
            title="Kept Saved Story",
            url="https://example.com/kept-saved",
            summary="Saved only story.",
            source="Saved Source",
            feed_key="saved",
        )
        self.dropped = Article.objects.create(
            title="Dropped Unsaved Story",
            url="https://example.com/dropped-unsaved",
            summary="Unsaved story.",
            source="Saved Source",
            feed_key="saved",
        )

    def _bookmark(self, client, article):
        response = client.post(reverse("news:news_toggle_save", args=[article.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["is_saved"])

    def test_saved_1_csv_export_only_bookmarked_rows(self):
        client = Client()
        self._bookmark(client, self.kept)
        response = client.get(reverse("news:news_export", args=["csv"]) + "?saved=1")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        self.assertIn(self.kept.title, body)
        self.assertNotIn(self.dropped.title, body)

    def test_saved_1_rss_only_bookmarked_link(self):
        client = Client()
        self._bookmark(client, self.kept)
        response = client.get(reverse("news:news_rss") + "?saved=1")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn(self.kept.url, body)
        self.assertNotIn(self.dropped.url, body)

    def test_saved_1_api_only_bookmarked_id(self):
        client = Client()
        self._bookmark(client, self.kept)
        response = client.get(reverse("news:news_api") + "?saved=1")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        ids = [r["id"] for r in data["results"]]
        self.assertEqual(ids, [self.kept.pk])

    def test_no_profile_saved_1_returns_empty_not_500(self):
        client = Client()
        # No bookmark/open, so no profile exists.
        csv_response = client.get(reverse("news:news_export", args=["csv"]) + "?saved=1")
        self.assertEqual(csv_response.status_code, 200)
        body = csv_response.content.decode("utf-8-sig")
        self.assertNotIn(self.kept.title, body)
        self.assertNotIn(self.dropped.title, body)
        self.assertEqual(len(body.strip().splitlines()), 1)  # header only

        rss_response = client.get(reverse("news:news_rss") + "?saved=1")
        self.assertEqual(rss_response.status_code, 200)
        self.assertNotIn(self.kept.url, rss_response.content.decode("utf-8"))

        api_response = client.get(reverse("news:news_api") + "?saved=1")
        self.assertEqual(api_response.status_code, 200)
        data = json.loads(api_response.content)
        self.assertEqual(data["results"], [])
        self.assertEqual(data["count"], 0)

        # Unread with no profile should not 500 either.
        unread_response = client.get(reverse("news:news_export", args=["csv"]) + "?unread=1")
        self.assertEqual(unread_response.status_code, 200)
