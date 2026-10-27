"""Management command: refresh news feeds (suitable for cron / Task Scheduler)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.news.services import RefreshLockError, run_refresh


class Command(BaseCommand):
    help = "Fetch all configured news feeds and upsert articles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum articles kept per feed (default 25).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Clear running locks (mark them failed) before refreshing.",
        )

    def handle(self, *args, **options):
        from apps.news.models import RefreshRun

        if options["force"]:
            from django.utils import timezone

            running = RefreshRun.objects.filter(status="running")
            for run in running:
                run.status = "failed"
                run.finished_at = timezone.now()
                errors = run.errors if isinstance(run.errors, list) else []
                errors.append(
                    {
                        "key": "system",
                        "source": "system",
                        "error": "stale lock released (--force)",
                    }
                )
                run.errors = errors
                run.save(update_fields=["status", "finished_at", "errors"])
            if running:
                self.stdout.write(
                    self.style.WARNING(
                        f"Forced close of {running.count()} running lock(s)."
                    )
                )

        try:
            run = run_refresh(trigger="command", per_feed_limit=options["limit"])
        except RefreshLockError as exc:
            raise CommandError(
                f"Refresh skipped: {exc} Use --force to clear a stuck lock."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Refresh {status}: created={created} updated={updated} "
                "total={total} errors={errors}".format(
                    status=run.status,
                    created=run.created_count,
                    updated=run.updated_count,
                    total=run.total_articles,
                    errors=len(run.errors or []),
                )
            )
        )
        for err in run.errors or []:
            self.stdout.write(self.style.WARNING(f"  [{err.get('key')}] {err.get('error')}"))
