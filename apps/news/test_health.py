"""Tests for apps.news.health — source health dashboard views and data."""

import json
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.news import health
from apps.news.feeds import FEEDS
from apps.news.models import Article, RefreshRun


class HealthDataTests(TestCase):
    """Direct data function tests for _health_rows, _summary and the views."""

    def setUp(self):
        for index in range(3):
            Article.objects.create(
                title=f"Google AI article {index}",
                url=f"https://example.com/google-ai-{index}",
                source="Google News — AI",
                feed_key="google_ai",
                published_at=datetime(2026, 10, 27, 10, index, tzinfo=timezone.utc),
            )
        for index in range(2):
            Article.objects.create(
                title=f"TechCrunch AI article {index}",
                url=f"https://example.com/techcrunch-ai-{index}",
                source="TechCrunch — AI",
                feed_key="techcrunch_ai",
                published_at=datetime(2026, 10, 27, 9, index, tzinfo=timezone.utc),
            )

    def test_sources_json_keys(self):
        response = self.client.get(reverse("news:sources_json"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sources", data)
        self.assertIn("summary", data)
        self.assertIn("generated_at", data)
        source = data["sources"][0]
        for key in ("key", "name", "total", "status", "error"):
            self.assertIn(key, source)

    def test_refresh_log_json_has_duration(self):
        RefreshRun.objects.create(
            status="success",
            trigger="web",
            created_count=5,
            updated_count=2,
            total_articles=10,
            finished_at=datetime.now(timezone.utc),
        )

        response = self.client.get(reverse("news:sources_runs"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("runs", data)
        run_data = data["runs"][0]
        for key in ("duration_seconds", "id", "status", "trigger"):
            self.assertIn(key, run_data)

    def test_json_serializable_datetimes_iso(self):
        RefreshRun.objects.create(
            status="partial",
            trigger="cron",
            created_count=1,
            total_articles=1,
            finished_at=datetime.now(timezone.utc),
            errors=[{"key": "x", "source": "X", "error": "boom"}],
        )

        data = self.client.get(reverse("news:sources_json")).json()

        self.assertIsInstance(data["generated_at"], str)
        latest = data.get("latest_run")
        if latest:
            self.assertIsInstance(latest["started_at"], str)
            self.assertIsInstance(latest["finished_at"], str)

    def test_health_rows_counts_statuses_and_order(self):
        RefreshRun.objects.create(
            status="partial",
            trigger="web",
            errors=[
                {
                    "key": FEEDS[1]["key"],
                    "source": FEEDS[1]["name"],
                    "error": "boom",
                }
            ],
        )

        rows = health._health_rows()
        by_key = {row["key"]: row for row in rows}

        self.assertEqual(rows[0]["status"], "error")
        self.assertEqual(by_key["google_ai"]["total"], 3)
        self.assertEqual(by_key["techcrunch_ai"]["total"], 2)
        self.assertEqual(by_key["google_ai"]["status"], "ok")
        self.assertEqual(by_key[FEEDS[1]["key"]]["status"], "error")
        self.assertGreaterEqual(len(rows), len(FEEDS))

    def test_summary(self):
        rows = [
            {"status": "ok"},
            {"status": "ok"},
            {"status": "error"},
            {"status": "idle"},
        ]

        self.assertEqual(
            health._summary(rows),
            {"total": 4, "ok": 2, "error": 1, "idle": 1},
        )


class HealthManifestTests(TestCase):
    """The PWA manifest is valid JSON with the required install fields."""

    def test_manifest_has_required_fields(self):
        manifest_path = settings.BASE_DIR / "static" / "manifest.webmanifest"
        self.assertTrue(manifest_path.exists())

        with manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)

        self.assertIn("name", manifest)
        self.assertIn("start_url", manifest)
        self.assertTrue(manifest["icons"])


class RefreshRunModelTests(TestCase):
    """Test RefreshRun.duration_seconds property."""

    def test_duration_seconds_when_finished(self):
        now = datetime.now(timezone.utc)
        run = RefreshRun.objects.create(
            status="success",
            trigger="web",
            finished_at=now,
        )
        # auto_now_add ignores the constructor value, so update via queryset.
        RefreshRun.objects.filter(pk=run.pk).update(
            started_at=now - timedelta(seconds=42)
        )
        run.refresh_from_db()

        self.assertEqual(run.duration_seconds, 42)

    def test_duration_seconds_when_running(self):
        run = RefreshRun.objects.create(status="running", trigger="web")

        self.assertIsNone(run.duration_seconds)
