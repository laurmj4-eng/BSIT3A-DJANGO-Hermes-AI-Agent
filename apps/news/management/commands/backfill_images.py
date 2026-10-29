"""Management command: backfill Open Graph images for cached articles."""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.news.models import Article


class Command(BaseCommand):
    help = "Backfill article image_url values by fetching each article's Open Graph image."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of articles to scan (0 = all).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Seconds to sleep after each network request (default 0.5).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch images but do not write anything to the database.",
        )
        parser.add_argument(
            "--refresh-existing",
            action="store_true",
            help="Re-fetch rows that already have an image_url.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=8.0,
            help="Per-request timeout in seconds (default 8.0).",
        )

    def handle(self, *args, **options):
        # Imported lazily so this command loads even if the module is mid-write.
        from apps.news.images import fetch_og_image

        limit = options["limit"]
        delay = options["delay"]
        dry_run = options["dry_run"]
        refresh_existing = options["refresh_existing"]
        timeout = options["timeout"]

        qs = Article.objects.order_by("-published_at", "-fetched_at")
        if not refresh_existing:
            qs = qs.filter(Q(image_url="") | Q(image_url__isnull=True))
        if limit and limit > 0:
            qs = qs[:limit]

        scanned = 0
        found = 0
        saved = 0
        failed = 0

        for article in qs:
            scanned += 1
            try:
                image_url, _final_url = fetch_og_image(article.url, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - per-row isolation
                failed += 1
                self.stderr.write(
                    "  [{}] {}: {}".format(
                        article.pk, str(article.url)[:120], str(exc)[:120]
                    )
                )
            else:
                if image_url:
                    found += 1
                    if not dry_run:
                        try:
                            article.image_url = image_url
                            article.save(update_fields=["image_url"])
                            saved += 1
                        except Exception as exc:  # noqa: BLE001 - per-row isolation
                            failed += 1
                            self.stderr.write(
                                "  [{}] save failed: {}".format(
                                    article.pk, str(exc)[:120]
                                )
                            )
            if delay and delay > 0:
                time.sleep(delay)
            if scanned % 25 == 0:
                self.stdout.write(
                    f"  scanned={scanned} found={found} saved={saved} failed={failed}"
                )

        self.stdout.write(
            f"backfill_images: scanned={scanned} found={found} saved={saved} "
            f"failed={failed} dry_run={dry_run}"
        )
