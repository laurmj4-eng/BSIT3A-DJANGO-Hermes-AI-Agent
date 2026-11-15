"""Tests for the bounded image harvest queue."""

from unittest.mock import patch

from django.test import TestCase

from apps.news.image_harvest import (
    candidate_queryset,
    harvest_and_save,
    harvest_images,
    save_hits,
)
from apps.news.models import Article


def _article(url, image_url=''):
    return Article.objects.create(
        title='Story',
        url=url,
        source='Test',
        feed_key='test',
        image_url=image_url,
    )


class CandidateQueueTests(TestCase):
    def test_excludes_rows_with_an_image(self):
        blank = _article('https://example.com/blank')
        _article('https://example.com/has', 'https://cdn.example/a.jpg')
        rows = list(candidate_queryset(limit=10))
        self.assertEqual([row.pk for row in rows], [blank.pk])

    def test_existing_mode_includes_every_row(self):
        _article('https://example.com/blank')
        _article('https://example.com/has', 'https://cdn.example/a.jpg')
        self.assertEqual(len(list(candidate_queryset(limit=10, existing=True))), 2)


class SaveHitsTests(TestCase):
    def test_writes_only_when_still_blank(self):
        article = _article('https://example.com/story')
        self.assertEqual(save_hits([(article.pk, 'https://cdn.example/a.jpg', '')]), 1)
        article.refresh_from_db()
        self.assertEqual(article.image_url, 'https://cdn.example/a.jpg')

    def test_does_not_clobber_a_concurrent_image(self):
        article = _article('https://example.com/story', 'https://cdn.example/original.jpg')
        saved = save_hits([(article.pk, 'https://cdn.example/new.jpg', '')])
        article.refresh_from_db()
        self.assertEqual(saved, 0)
        self.assertEqual(article.image_url, 'https://cdn.example/original.jpg')

    def test_existing_mode_overwrites(self):
        article = _article('https://example.com/story', 'https://cdn.example/old.jpg')
        self.assertEqual(
            save_hits([(article.pk, 'https://cdn.example/new.jpg', '')], existing=True), 1
        )
        article.refresh_from_db()
        self.assertEqual(article.image_url, 'https://cdn.example/new.jpg')


class HarvestImagesTests(TestCase):
    def test_collects_successful_hits_only(self):
        first = _article('https://example.com/one')
        second = _article('https://example.com/two')

        def fake_fetch(article, timeout):
            if article.pk == first.pk:
                return (article.pk, 'https://cdn.example/one.jpg', '')
            return None

        with patch('apps.news.image_harvest._fetch_one', side_effect=fake_fetch):
            hits = harvest_images([first, second], max_images=2, workers=2, deadline=5)
        self.assertEqual([hit[0] for hit in hits], [first.pk])

    def test_harvest_and_save_counts(self):
        article = _article('https://example.com/one')
        with patch(
            'apps.news.image_harvest.harvest_images',
            return_value=[(article.pk, 'https://cdn.example/one.jpg', '')],
        ) as harvest:
            scanned, found, saved = harvest_and_save(limit=5, workers=2)
        self.assertEqual((scanned, found, saved), (1, 1, 1))
        article.refresh_from_db()
        self.assertEqual(article.image_url, 'https://cdn.example/one.jpg')
        harvest.assert_called_once()
