"""Stores AI news articles pulled from public RSS/Atom feeds."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Topic(models.Model):
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=20, default='#6366f1')
    description = models.CharField(max_length=160, blank=True)
    keywords = models.TextField(blank=True, help_text='Comma-separated keywords')

    class Meta:
        ordering = ['name']
        db_table = 'tblnewstopic'

    def __str__(self):
        return self.name


class Article(models.Model):
    """A single cached AI news article."""

    title = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    summary = models.TextField(blank=True)
    # Harvested from the article's og:image; feeds ship no thumbnails.
    image_url = models.URLField(max_length=500, blank=True, default='')
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
    topics = models.ManyToManyField('Topic', related_name='articles', blank=True)
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    last_viewed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'tblnewsarticle'
        # A feed refresh re-sees the same articles, so dedupe on the link.
        constraints = [
            models.UniqueConstraint(fields=['url'], name='unique_news_article_url'),
        ]
        ordering = ['-published_at', '-fetched_at']
        indexes = [
            models.Index(fields=['source'], name='article_source_idx'),
            models.Index(fields=['fetched_at'], name='article_fetched_idx'),
            models.Index(fields=['published_at', 'fetched_at'], name='article_pub_fetch_idx'),
        ]

    def __str__(self):
        return f'{self.source}: {self.title[:60]}'


class RefreshRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=[('running', 'Running'), ('success', 'Success'), ('partial', 'Partial'), ('failed', 'Failed')],
        default='running',
        db_index=True,
    )
    trigger = models.CharField(max_length=20, default='web')
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    total_articles = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-started_at']
        db_table = 'tblnewsrefreshrun'

    @property
    def duration_seconds(self):
        if self.finished_at is None:
            return None
        delta = self.finished_at - self.started_at
        return int(delta.total_seconds())

    def __str__(self):
        return f'{self.status} {self.started_at}'


class PlatformModel(models.Model):
    """Newest model detected for a platform from news headlines."""
    key = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=60)
    version = models.CharField(max_length=20, default='')
    source_title = models.CharField(max_length=300, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    detected_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'tblnewsplatformmodel'
        ordering = ['key']

    def __str__(self):
        return f'{self.key}: {self.label}'