"""Stores AI news articles pulled from public RSS/Atom feeds."""

from django.conf import settings
from django.db import models


class Article(models.Model):
    """A single cached AI news article."""

    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    summary = models.TextField(blank=True)
    source = models.CharField(max_length=120)
    feed_key = models.CharField(max_length=60, db_index=True)

    # Feed-supplied date is nullable; not every feed provides one.
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='news_articles',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    is_saved = models.BooleanField(default=False)

    class Meta:
        db_table = 'tblnewsarticle'
        # A feed refresh re-sees the same articles, so dedupe on the link.
        constraints = [
            models.UniqueConstraint(fields=['url'], name='unique_news_article_url'),
        ]
        ordering = ['-published_at', '-fetched_at']

    def __str__(self):
        return f'{self.source}: {self.title[:60]}'