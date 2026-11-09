"""Tests for weighted search relevance in the news feed."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.news.models import Article


def make_article(**overrides):
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


def page_articles(response):
    return list(response.context["articles"].object_list)


class SearchRankTests(TestCase):
    def test_title_hit_outranks_summary_only_hit(self):
        now = timezone.now()
        title_hit = make_article(title="quantum breakthrough", summary="other", published_at=now)
        summary_hit = make_article(title="other", summary="quantum breakthrough", published_at=now)

        response = self.client.get(reverse("news:news_list"), {"q": "quantum"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([a.pk for a in page_articles(response)], [title_hit.pk, summary_hit.pk])

    def test_multi_term_and_excludes_partial_matches(self):
        target = make_article(title="Claude beats GPT in benchmark")
        make_article(title="Claude only")
        make_article(title="GPT only")

        response = self.client.get(reverse("news:news_list"), {"q": "claude GPT"})

        self.assertEqual([a.pk for a in page_articles(response)], [target.pk])

    def test_no_query_keeps_newest_first(self):
        now = timezone.now()
        old = make_article(title="Old", published_at=now - timedelta(days=5))
        new = make_article(title="New", published_at=now)

        response = self.client.get(reverse("news:news_list"))

        self.assertEqual([a.pk for a in page_articles(response)], [new.pk, old.pk])

    def test_explicit_sort_oldest_respected_with_query(self):
        now = timezone.now()
        old = make_article(title="quantum old", published_at=now - timedelta(days=5))
        new = make_article(title="other", summary="quantum new", published_at=now)

        response = self.client.get(reverse("news:news_list"), {"q": "quantum", "sort": "oldest"})

        self.assertEqual([a.pk for a in page_articles(response)], [old.pk, new.pk])

    def test_response_200_and_both_articles_present_for_term(self):
        a = make_article(title="alpha term")
        b = make_article(title="beta", summary="term here")

        response = self.client.get(reverse("news:news_list"), {"q": "term"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual({a.pk, b.pk}, {x.pk for x in page_articles(response)})
