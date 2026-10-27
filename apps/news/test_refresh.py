"""Tests for apps.news.services and the refresh_news management command."""

from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.news.models import Article, RefreshRun, Topic
from apps.news.services import (
    LOCK_STALE_MINUTES,
    RefreshLockError,
    can_refresh,
    latest_run,
    run_refresh,
)


def _article(url, title="Some AI headline", summary="A summary."):
    return {
        "title": title,
        "url": url,
        "summary": summary,
        "source": "Test Feed",
        "feed_key": "test",
        "published_at": None,
    }


class RunRefreshTests(TestCase):
    def test_creates_articles_and_success_run(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=([_article("https://example.com/1")], []),
        ):
            run = run_refresh(trigger="web")
        self.assertEqual(run.status, "success")
        self.assertEqual(run.created_count, 1)
        self.assertEqual(run.updated_count, 0)
        self.assertEqual(run.total_articles, 1)
        self.assertEqual(Article.objects.count(), 1)
        self.assertEqual(latest_run().id, run.id)

    def test_second_run_updates_not_duplicates(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=([_article("https://example.com/1")], []),
        ):
            run_refresh()
            run2 = run_refresh()
        self.assertEqual(Article.objects.count(), 1)
        self.assertEqual(run2.status, "success")
        self.assertEqual(run2.created_count, 0)
        self.assertEqual(run2.updated_count, 1)

    def test_topics_applied(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=(
                [_article("https://example.com/oai", title="OpenAI releases GPT-5")],
                [],
            ),
        ):
            run_refresh()
        article = Article.objects.get(url="https://example.com/oai")
        slugs = set(article.topics.values_list("slug", flat=True))
        self.assertIn("openai-gpt", slugs)
        self.assertTrue(Topic.objects.filter(slug="openai-gpt").exists())

    def test_partial_on_one_error(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=(
                [_article("https://example.com/1")],
                [{"key": "x", "source": "X", "error": "boom"}],
            ),
        ):
            run = run_refresh()
        self.assertEqual(run.status, "partial")
        self.assertEqual(len(run.errors), 1)

    def test_all_failed_no_exception(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=(
                [],
                [{"key": "a", "source": "A", "error": "down"}],
            ),
        ):
            run = run_refresh()
        self.assertEqual(run.status, "failed")
        self.assertTrue(run.errors)
        self.assertEqual(run.created_count, 0)

    def test_crash_marks_run_failed_and_reraises(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            side_effect=RuntimeError("kaboom"),
        ):
            with self.assertRaises(RuntimeError):
                run_refresh()
        run = latest_run()
        self.assertEqual(run.status, "failed")
        self.assertIsNotNone(run.finished_at)
        self.assertIn("kaboom", run.errors[-1]["error"])


class LockTests(TestCase):
    def test_running_run_blocks_refresh(self):
        RefreshRun.objects.create(status="running")
        with self.assertRaises(RefreshLockError):
            run_refresh()
        self.assertFalse(can_refresh())

    def test_stale_running_run_is_released(self):
        stale = RefreshRun.objects.create(status="running")
        RefreshRun.objects.filter(pk=stale.pk).update(
            started_at=timezone.now() - timedelta(minutes=LOCK_STALE_MINUTES + 5)
        )
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=([_article("https://example.com/1")], []),
        ):
            run = run_refresh()
        stale.refresh_from_db()
        self.assertEqual(stale.status, "failed")
        self.assertEqual(stale.errors[-1]["error"], "stale lock released")
        self.assertEqual(run.status, "success")
        self.assertTrue(can_refresh())

    def test_can_refresh_true_when_no_running(self):
        self.assertTrue(can_refresh())


class CommandTests(TestCase):
    def test_call_command_success(self):
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=([_article("https://example.com/1")], []),
        ):
            call_command("refresh_news", "--limit", 10)
        run = latest_run()
        self.assertEqual(run.status, "success")
        self.assertEqual(run.trigger, "command")
        self.assertEqual(Article.objects.count(), 1)

    def test_call_command_lock_error(self):
        RefreshRun.objects.create(status="running")
        with patch("apps.news.services.fetch_all_feeds") as mock_fetch:
            with self.assertRaises(Exception):
                call_command("refresh_news")
        mock_fetch.assert_not_called()

    def test_force_clears_lock(self):
        RefreshRun.objects.create(status="running")
        with patch(
            "apps.news.services.fetch_all_feeds",
            return_value=([_article("https://example.com/1")], []),
        ):
            call_command("refresh_news", "--force")
        self.assertEqual(latest_run().status, "success")
        self.assertFalse(RefreshRun.objects.filter(status="running").exists())
