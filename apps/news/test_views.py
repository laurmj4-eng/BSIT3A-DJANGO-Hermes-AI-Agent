"""Tests for the news feed views, exporters and JSON/RSS endpoints.

No network access: refreshes are mocked and articles are created directly.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.news.feeds import FEEDS
from apps.news.models import Article, RefreshRun, Topic
from apps.news.services import RefreshLockError

LEGACY_CONTEXT_KEYS = {
    "articles",
    "query",
    "source",
    "source_choices",
    "total",
    "last_updated",
    "feed_count",
    "saved_total",
    "saved_filter",
    "filter_query",
    "saved_toggle_query",
}


def make_article(**overrides):
    """Create an Article with sane defaults; returns the instance."""
    data = {
        "title": "AI article",
        "url": f"https://example.com/{uuid.uuid4().hex}",
        "summary": "A short summary.",
        "source": "Test Feed",
        "feed_key": "test",
        "published_at": timezone.now(),
    }
    data.update(overrides)
    fetched_at = data.pop("fetched_at", None)
    article = Article.objects.create(**data)
    if fetched_at is not None:
        Article.objects.filter(pk=article.pk).update(fetched_at=fetched_at)
        article.refresh_from_db()
    return article


def make_topic(slug="ai", name="AI", **overrides):
    return Topic.objects.create(
        slug=slug, name=name, color="#6366f1", keywords="ai,ml", **overrides
    )


def page_articles(response):
    return list(response.context["articles"].object_list)


class NewsPageTests(TestCase):
    def test_page_renders_with_legacy_context(self):
        topic = make_topic()
        article = make_article(title="Claude ships an update", source="Feed A", feed_key="feed_a")
        article.topics.add(topic)

        response = self.client.get(reverse("news:news_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/feed.html")
        for key in LEGACY_CONTEXT_KEYS:
            self.assertIn(key, response.context, key)
        self.assertEqual(response.context["total"], 1)
        self.assertEqual(response.context["feed_count"], len(FEEDS))
        self.assertEqual(response.context["articles"].number, 1)

        # source_options are dicts, source_choices stay (key, name) tuples.
        options = response.context["source_options"]
        self.assertTrue(all(set(option) == {"key", "name", "total"} for option in options))
        self.assertIn(("feed_a", "Feed A"), response.context["source_choices"])
        self.assertTrue(
            all(isinstance(choice, tuple) and len(choice) == 2
                for choice in response.context["source_choices"])
        )

        topic_choices = response.context["topic_choices"]
        self.assertEqual([choice.slug for choice in topic_choices], ["ai"])
        self.assertEqual(topic_choices[0].total, 1)
        self.assertEqual(
            response.context["sort_choices"],
            [("newest", "Newest"), ("oldest", "Oldest"), ("title", "Title A-Z")],
        )
        self.assertEqual(response.context["page_range"], [1])

        # Session key is created for the page's CSRF cookie.
        self.assertIn("csrftoken", response.cookies)

    def test_search_terms_are_anded_across_fields(self):
        target = make_article(title="Claude beats GPT in benchmark")
        make_article(title="Claude only")
        make_article(title="GPT only")

        response = self.client.get(reverse("news:news_list"), {"q": "claude GPT"})

        self.assertEqual([a.pk for a in page_articles(response)], [target.pk])
        self.assertEqual(response.context["active_filter_count"], 1)

    def test_search_matches_source(self):
        target = make_article(source="UniqueWire")
        make_article(source="Other")

        response = self.client.get(reverse("news:news_list"), {"q": "uniquewire"})

        self.assertEqual([a.pk for a in page_articles(response)], [target.pk])

    def test_source_filter(self):
        target = make_article(feed_key="feed_a")
        make_article(feed_key="feed_b")

        response = self.client.get(reverse("news:news_list"), {"source": "feed_a"})

        self.assertEqual([a.pk for a in page_articles(response)], [target.pk])
        self.assertEqual(response.context["source"], "feed_a")

    def test_topic_filter_and_unknown_slug(self):
        topic = make_topic(slug="robotics", name="Robotics")
        tagged = make_article(title="Robot news")
        tagged.topics.add(topic)
        make_article(title="Other news")

        response = self.client.get(reverse("news:news_list"), {"topic": "robotics"})
        self.assertEqual([a.pk for a in page_articles(response)], [tagged.pk])
        self.assertEqual(response.context["topic_obj"].slug, "robotics")

        unknown = self.client.get(reverse("news:news_list"), {"topic": "nope"})
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(page_articles(unknown), [])
        self.assertIsNone(unknown.context["topic_obj"])

    def test_date_range_filters_and_invalid_dates_ignored(self):
        now = timezone.now()
        old = make_article(published_at=now - timedelta(days=10))
        recent = make_article(published_at=now - timedelta(days=1))

        params = {
            "from": (now - timedelta(days=5)).date().isoformat(),
            "to": now.date().isoformat(),
        }
        response = self.client.get(reverse("news:news_list"), params)
        self.assertEqual([a.pk for a in page_articles(response)], [recent.pk])
        self.assertEqual(response.context["date_from"], params["from"])

        invalid = self.client.get(
            reverse("news:news_list"), {"from": "not-a-date", "to": "31-12-2024"}
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(len(page_articles(invalid)), 2)
        self.assertEqual(invalid.context["date_from"], "")

    def test_sort_oldest_and_newest(self):
        now = timezone.now()
        old = make_article(title="Old", published_at=now - timedelta(days=5))
        new = make_article(title="New", published_at=now)

        newest = self.client.get(reverse("news:news_list"))
        self.assertEqual([a.pk for a in page_articles(newest)], [new.pk, old.pk])

        oldest = self.client.get(reverse("news:news_list"), {"sort": "oldest"})
        self.assertEqual([a.pk for a in page_articles(oldest)], [old.pk, new.pk])

        title = self.client.get(reverse("news:news_list"), {"sort": "title"})
        self.assertEqual([a.pk for a in page_articles(title)], [new.pk, old.pk])

        unknown = self.client.get(reverse("news:news_list"), {"sort": "bogus"})
        self.assertEqual(unknown.context["sort"], "newest")

    def test_saved_filter_uses_session(self):
        saved = make_article(title="Saved")
        make_article(title="Not saved")

        session = self.client.session
        session["saved_articles"] = [saved.pk]
        session.save()

        response = self.client.get(reverse("news:news_list"), {"saved": "1"})

        self.assertEqual([a.pk for a in page_articles(response)], [saved.pk])
        self.assertTrue(response.context["saved_filter"])
        self.assertEqual(response.context["saved_total"], 1)
        self.assertTrue(page_articles(response)[0].is_saved)
        # The toggle URL removes the active flag rather than re-adding it.
        self.assertNotIn("saved=1", response.context["saved_toggle_query"])

    def test_unread_filter_uses_session(self):
        read = make_article(title="Read")
        unread = make_article(title="Unread")

        session = self.client.session
        session["read_articles"] = [read.pk]
        session.save()

        response = self.client.get(reverse("news:news_list"), {"unread": "1"})

        self.assertEqual([a.pk for a in page_articles(response)], [unread.pk])
        self.assertTrue(response.context["unread_filter"])
        self.assertEqual(response.context["read_total"], 1)

    def test_page_range_elided_and_active_filter_count(self):
        now = timezone.now()
        Article.objects.bulk_create([
            Article(
                title=f"Story {index}",
                url=f"https://example.com/bulk/{index}",
                source="Bulk",
                feed_key="bulk",
                published_at=now - timedelta(minutes=index),
            )
            for index in range(400)
        ])

        response = self.client.get(
            reverse("news:news_list"),
            {"page": 5, "q": "story", "source": "bulk", "topic": "missing"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_filter_count"], 3)

        paged = self.client.get(reverse("news:news_list"), {"page": 5})
        page_range = paged.context["page_range"]
        self.assertIn(1, page_range)
        self.assertIn(None, page_range)
        self.assertEqual(paged.context["articles"].number, 5)

        plain = self.client.get(reverse("news:news_list"))
        self.assertFalse(plain.context["has_filters"])
        self.assertEqual(plain.context["active_filter_count"], 0)
        self.assertEqual(plain.context["filter_query"], "")


class NewsRefreshTests(TestCase):
    def _run(self, **kwargs):
        defaults = {
            "status": "success",
            "created_count": 2,
            "updated_count": 1,
            "total_articles": 3,
            "errors": [],
            "finished_at": timezone.now(),
        }
        defaults.update(kwargs)
        return RefreshRun(**defaults)

    def test_refresh_success_payload(self):
        run = self._run()
        with patch("apps.news.views.run_refresh", return_value=run) as mocked:
            response = self.client.post(reverse("news:news_refresh"))

        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once_with(trigger="web")
        data = response.json()
        self.assertEqual(
            set(data),
            {"status", "created", "updated", "errors", "total", "finished_at"},
        )
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["created"], 2)
        self.assertEqual(data["updated"], 1)
        self.assertEqual(data["total"], 3)
        self.assertIsNotNone(data["finished_at"])

    def test_refresh_all_feeds_failed_returns_502(self):
        run = self._run(
            status="failed",
            created_count=0,
            updated_count=0,
            errors=[{"key": "a", "source": "A", "error": "down"}],
        )
        with patch("apps.news.views.run_refresh", return_value=run):
            response = self.client.post(reverse("news:news_refresh"))

        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertEqual(data["error"], "No articles could be fetched. All feeds failed.")
        self.assertEqual(data["errors"][0]["key"], "a")
        self.assertEqual(data["created"], 0)

    def test_refresh_lock_returns_409(self):
        with patch(
            "apps.news.views.run_refresh",
            side_effect=RefreshLockError("A refresh is already running."),
        ):
            response = self.client.post(reverse("news:news_refresh"))

        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.json())

    def test_refresh_requires_post(self):
        response = self.client.get(reverse("news:news_refresh"))
        self.assertEqual(response.status_code, 405)

    def test_refresh_cooldown_returns_429(self):
        run = RefreshRun.objects.create(status="success", finished_at=timezone.now())
        RefreshRun.objects.filter(pk=run.pk).update(started_at=timezone.now())

        with patch("apps.news.views.run_refresh") as mocked:
            response = self.client.post(reverse("news:news_refresh"))

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertGreater(response.json()["retry_after"], 0)
        mocked.assert_not_called()

    def test_refresh_allowed_after_cooldown(self):
        run = RefreshRun.objects.create(status="success", finished_at=timezone.now())
        RefreshRun.objects.filter(pk=run.pk).update(
            started_at=timezone.now() - timedelta(seconds=61)
        )

        with patch("apps.news.views.run_refresh", return_value=self._run()) as mocked:
            response = self.client.post(reverse("news:news_refresh"))

        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once_with(trigger="web")


class ToggleTests(TestCase):
    def test_save_toggle_twice(self):
        article = make_article()
        url = reverse("news:news_toggle_save", args=[article.pk])

        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["is_saved"])
        self.assertEqual(first.json()["saved_total"], 1)
        self.assertEqual(self.client.session["saved_articles"], [article.pk])

        second = self.client.post(url)
        self.assertFalse(second.json()["is_saved"])
        self.assertEqual(second.json()["saved_total"], 0)
        self.assertEqual(self.client.session["saved_articles"], [])

    def test_read_toggle_and_unread_filter(self):
        article = make_article()
        url = reverse("news:news_toggle_read", args=[article.pk])

        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"status": "ok", "is_read": True, "read_total": 1})
        self.assertEqual(self.client.session["read_articles"], [article.pk])

        second = self.client.post(url)
        self.assertFalse(second.json()["is_read"])
        self.assertEqual(second.json()["read_total"], 0)

    def test_unknown_article_returns_404(self):
        response = self.client.post(reverse("news:news_toggle_save", args=[999999]))
        self.assertEqual(response.status_code, 404)


class NewsOpenTests(TestCase):
    def test_open_increments_view_and_marks_read(self):
        article = make_article(url="https://example.com/story")

        response = self.client.get(reverse("news:news_open", args=[article.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/story")
        article.refresh_from_db()
        self.assertEqual(article.view_count, 1)
        self.assertIsNotNone(article.last_viewed_at)
        self.assertEqual(self.client.session["read_articles"], [article.pk])

    def test_open_unsafe_url_returns_400(self):
        article = make_article(url="javascript:alert(1)")

        response = self.client.get(reverse("news:news_open", args=[article.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b"Unsafe link")
        article.refresh_from_db()
        self.assertEqual(article.view_count, 0)


class ExportTests(TestCase):
    def test_csv_export(self):
        make_article(title="AI & <robots>", summary="  Spaced \n\n summary  ")

        response = self.client.get(reverse("news:news_export", args=["csv"]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("hermes-ai-news-", response["Content-Disposition"])
        self.assertTrue(response["Content-Disposition"].endswith('.csv"'))
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        text = response.content.decode("utf-8-sig")
        first_line = text.splitlines()[0]
        self.assertEqual(first_line, "Title,Source,Published,Topics,URL,Summary")
        self.assertIn("AI & <robots>", text)
        self.assertIn("Spaced summary", text)

    def test_csv_export_applies_filters_but_ignores_session_filters(self):
        make_article(title="Claude wins")
        make_article(title="Other story")

        session = self.client.session
        session["saved_articles"] = []
        session.save()

        response = self.client.get(
            reverse("news:news_export", args=["csv"]),
            {"q": "claude", "saved": "1"},
        )

        text = response.content.decode("utf-8-sig")
        self.assertIn("Claude wins", text)
        self.assertNotIn("Other story", text)

    def test_xlsx_export(self):
        make_article(title="Workbook row")

        response = self.client.get(reverse("news:news_export", args=["xlsx"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertGreater(len(response.content), 500)
        self.assertIn(".xlsx", response["Content-Disposition"])

    def test_bad_export_format_returns_404(self):
        response = self.client.get(reverse("news:news_export", args=["pdf"]))
        self.assertEqual(response.status_code, 404)


class FeedAndApiTests(TestCase):
    def test_rss_feed(self):
        article = make_article(title="RSS headline", url="https://example.com/rss")

        response = self.client.get(reverse("news:news_rss"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/rss+xml", response["Content-Type"])
        body = response.content.decode("utf-8")
        self.assertIn("Hermes AI News", body)
        self.assertIn("RSS headline", body)
        self.assertIn(article.url, body)

    def test_api_shape_and_limit(self):
        now = timezone.now()
        for index in range(3):
            make_article(
                title=f"API story {index}",
                url=f"https://example.com/api/{index}",
                published_at=now - timedelta(minutes=index),
            )

        response = self.client.get(reverse("news:news_api"), {"limit": 2})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)
        item = data["results"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "title",
                "url",
                "source",
                "feed_key",
                "summary",
                "published_at",
                "fetched_at",
                "topics",
                "view_count",
            },
        )
        self.assertEqual(item["title"], "API story 0")
        self.assertEqual(item["topics"], [])
        self.assertIsNotNone(item["fetched_at"])

    def test_api_ignores_invalid_limit(self):
        make_article()
        response = self.client.get(reverse("news:news_api"), {"limit": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_api_filters_by_query(self):
        make_article(title="Claude release")
        make_article(title="Gemini release")

        response = self.client.get(reverse("news:news_api"), {"q": "claude"})

        self.assertEqual([item["title"] for item in response.json()["results"]], ["Claude release"])

    def test_suggest_requires_two_characters(self):
        make_article(title="Claude news")

        short = self.client.get(reverse("news:news_suggest"), {"q": "c"})
        self.assertEqual(short.status_code, 200)
        self.assertEqual(short.json(), {"results": [], "topics": []})

    def test_suggest_returns_matches(self):
        article = make_article(title="Claude news", source="Feed A")
        make_topic(slug="claude", name="Claude")

        response = self.client.get(reverse("news:news_suggest"), {"q": "cl"})

        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["results"][0]["id"], article.pk)
        self.assertEqual(
            set(data["results"][0]), {"id", "title", "source", "published_at"}
        )
        self.assertEqual(data["topics"][0]["slug"], "claude")
        self.assertEqual(set(data["topics"][0]), {"slug", "name", "color"})


class QuerystringTagTests(TestCase):
    def test_merges_and_drops_page(self):
        from urllib.parse import parse_qs

        from django.test import RequestFactory

        from apps.news.templatetags.news_extras import querystring

        request = RequestFactory().get("/news/?q=ai&page=2&saved=1")
        result = querystring({"request": request}, source="feed_a", saved=None)

        self.assertEqual(parse_qs(result), {"q": ["ai"], "source": ["feed_a"]})

    def test_safe_without_request(self):
        from apps.news.templatetags.news_extras import querystring

        self.assertEqual(querystring({}, q="ai"), "q=ai")
        self.assertEqual(querystring({}), "")


class CsrfTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

    def test_read_endpoints_require_no_csrf(self):
        article = make_article(url="https://example.com/story")

        for url in (
            reverse("news:news_list"),
            reverse("news:news_export", args=["csv"]),
            reverse("news:news_export", args=["xlsx"]),
            reverse("news:news_rss"),
            reverse("news:news_api"),
            reverse("news:news_suggest") + "?q=ai",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        self.assertEqual(
            self.client.get(reverse("news:news_open", args=[article.pk])).status_code,
            302,
        )
