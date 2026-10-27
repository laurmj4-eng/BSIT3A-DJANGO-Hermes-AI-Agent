"""Detect the newest released model per platform from cached headlines."""

from django.core.management.base import BaseCommand

from apps.news.model_watch import update_latest_models


class Command(BaseCommand):
    help = 'Detect the newest model released per platform from recent headlines.'

    def handle(self, *args, **options):
        changed = update_latest_models()
        if not changed:
            self.stdout.write('No newer models detected.')
            return
        for key, label in sorted(changed.items()):
            self.stdout.write(f'{key}: {label}')
