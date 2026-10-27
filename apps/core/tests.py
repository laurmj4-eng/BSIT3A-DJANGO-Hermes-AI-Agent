from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.news.feeds import FEEDS
from apps.news.models import Article, RefreshRun, Topic
from apps.news.services import latest_run


class PublicAccessTests(TestCase):
    """The site is a public dashboard; no sign-in wall anywhere."""

    def test_dashboard_is_public(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_root_serves_dashboard(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)

    def test_news_page_is_public(self):
        response = self.client.get(reverse('news:news_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'news/feed.html')

    def test_old_home_url_redirects(self):
        response = self.client.get('/home/')

        self.assertEqual(response.status_code, 302)

    def test_removed_account_routes_are_gone(self):
        self.assertEqual(self.client.get('/users/').status_code, 404)
        self.assertEqual(self.client.get('/info/').status_code, 404)
        self.assertEqual(self.client.get('/register/').status_code, 404)

    def test_bookmark_is_public_and_session_scoped(self):
        article = Article.objects.create(
            title='Test story',
            url='https://example.com/story',
            source='Test',
            feed_key='test',
        )
        save_url = reverse('news:news_toggle_save', args=[article.pk])

        response = self.client.post(save_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_saved'])

        # A different browser session does not inherit the bookmark.
        other_browser = self.client_class()
        page = other_browser.get(reverse('news:news_list'))
        self.assertEqual(page.context['saved_total'], 0)

        response = self.client.post(save_url)
        self.assertFalse(response.json()['is_saved'])

class DashboardContextTests(TestCase):
    """Dashboard context: totals, topics, trending, source health."""

    @staticmethod
    def _article(title, source, feed_key, days_ago=0, views=0, viewed=False):
        now = timezone.now()
        return Article.objects.create(
            title=title,
            url=f'https://example.com/{title.replace(" ", "-")}',
            summary=f'summary {title}',
            source=source,
            feed_key=feed_key,
            published_at=now - timedelta(days=days_ago),
            fetched_at=now - timedelta(days=days_ago),
            view_count=views,
            last_viewed_at=now - timedelta(days=1) if viewed else None,
        )

    def setUp(self):
        self.topic_a = Topic.objects.create(slug='llms', name='LLMs', color='#ff0000')
        self.topic_b = Topic.objects.create(slug='agents', name='Agents', color='#00ff00')
        self.old = self._article('Old story', 'Src A', FEEDS[0]['key'], days_ago=10, views=5, viewed=True)
        self.mid = self._article('Mid story', 'Src A', FEEDS[0]['key'], days_ago=2)
        self.new = self._article('New story', 'Src B', FEEDS[1]['key'], days_ago=0, views=9, viewed=True)
        self.mid.topics.add(self.topic_a)
        self.new.topics.add(self.topic_a)
        self.old.topics.add(self.topic_b)

    def test_dashboard_totals_and_topics(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        ctx = response.context
        self.assertEqual(ctx['total_articles'], 3)
        # fetched_at is auto_now_add, so every seeded article was fetched today.
        self.assertEqual(ctx['articles_today'], 3)
        self.assertEqual(ctx['articles_week'], 3)
        self.assertEqual(ctx['read_total'], 0)
        self.assertEqual(ctx['unread_total'], 3)
        self.assertEqual(ctx['total_sources'], 2)
        self.assertEqual(ctx['configured_sources'], len(FEEDS))
        self.assertEqual(ctx['topic_count'], 2)
        stats = {t['slug']: t for t in ctx['topic_stats']}
        self.assertEqual(stats['llms']['total'], 2)
        self.assertEqual(stats['agents']['total'], 1)
        self.assertEqual(stats['llms']['share'], 67)
        self.assertEqual(stats['agents']['share'], 33)
        self.assertEqual(ctx['latest_articles'][0].title, 'New story')
        self.assertTrue(hasattr(ctx['latest_articles'][0], 'is_saved'))
        self.assertEqual(len(ctx['latest_articles']), 3)

    def test_trending_ranks_topic_surge_and_excludes_old(self):
        response = self.client.get(reverse('dashboard'))
        trending = list(response.context['trending_articles'])
        # Same topic (LLMs): the read story leads, the unread one follows.
        self.assertEqual([a.pk for a in trending], [self.new.pk, self.mid.pk])

        # A heavily viewed story outside the 72h window never trends.
        stale = self._article(
            'Stale story', 'Src C', FEEDS[0]['key'], days_ago=8, views=99, viewed=True
        )
        stale.topics.add(self.topic_a)
        response = self.client.get(reverse('dashboard'))
        self.assertNotIn(stale.pk, [a.pk for a in response.context['trending_articles']])

        # A fresh burst on another topic outranks a single read story.
        burst = [
            self._article(f'Agent release {i}', 'Src C', FEEDS[2]['key'], days_ago=0)
            for i in range(3)
        ]
        for article in burst:
            article.topics.add(self.topic_b)

        response = self.client.get(reverse('dashboard'))
        ids = [a.pk for a in response.context['trending_articles']]
        self.assertEqual(len(ids), 5)
        # The accelerating topic leads, the steady one follows, old fill last.
        self.assertIn(ids[0], {a.pk for a in burst})
        self.assertEqual(ids[1], self.new.pk)
        self.assertIn(self.mid.pk, ids)

    def test_source_health_and_counts(self):
        response = self.client.get(reverse('dashboard'))
        health = {row['key']: row for row in response.context['source_health']}
        for feed in FEEDS:
            self.assertIn(feed['key'], health)
        self.assertEqual(health[FEEDS[0]['key']]['status'], 'ok')
        self.assertEqual(health[FEEDS[0]['key']]['total'], 2)
        self.assertEqual(response.context['feeds_ok'], 2)
        self.assertEqual(response.context['feeds_error'], 0)

    def test_refresh_run_errors_surface(self):
        RefreshRun.objects.create(
            status='partial',
            errors=[{'key': FEEDS[0]['key'], 'source': FEEDS[0]['name'], 'error': 'boom'}],
        )
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['refresh_status'], 'partial')
        self.assertIsNotNone(response.context['latest_run'])
        health = {row['key']: row for row in response.context['source_health']}
        self.assertEqual(health[FEEDS[0]['key']]['status'], 'error')
        self.assertEqual(health[FEEDS[0]['key']]['error'], 'boom')
        self.assertGreaterEqual(response.context['feeds_error'], 1)

    def test_session_read_marks_and_unread(self):
        session = self.client.session
        session['read_articles'] = [self.new.pk]
        session.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['read_total'], 1)
        self.assertEqual(response.context['unread_total'], 2)
        latest = {a.pk: a for a in response.context['latest_articles']}
        self.assertTrue(latest[self.new.pk].is_read)

    def test_empty_database_renders(self):
        Article.objects.all().delete()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['topic_stats'][0]['share'], 0)
        self.assertEqual(list(response.context['latest_articles']), [])
        self.assertEqual(list(response.context['trending_articles']), [])

    def test_model_coverage_groups_models_by_platform(self):
        self._article('Claude launches a new reasoning model', 'Src A', FEEDS[0]['key'])
        self._article('Groq speeds up inference on its LPU', 'Src B', FEEDS[1]['key'])

        response = self.client.get(reverse('dashboard'))
        models = {m['key']: m for m in response.context['model_stats']}

        self.assertEqual(models['claude']['platform_name'], 'Anthropic')
        self.assertEqual(models['claude']['total'], 1)
        self.assertTrue(models['claude']['logo'])
        self.assertTrue(models['claude']['platform_logo'])
        self.assertIn('groq', models)
        self.assertEqual(models['groq']['platform_name'], 'Groq')
        self.assertEqual(models['groq']['total'], 1)
        self.assertContains(response, 'icons/models/model-claude.svg')
        self.assertContains(response, 'icons/models/platform-groq.svg')
