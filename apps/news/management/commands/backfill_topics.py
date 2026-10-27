from django.core.management.base import BaseCommand

from apps.news.classification import apply_topics
from apps.news.models import Article


class Command(BaseCommand):
    help = 'Backfill topics for existing articles'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=500)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        updated = 0
        qs = Article.objects.only('id', 'title', 'summary').iterator(chunk_size=batch_size)
        for article in qs:
            matched = apply_topics(article)
            if matched:
                updated += 1
        self.stdout.write(f'Updated {updated} articles')
