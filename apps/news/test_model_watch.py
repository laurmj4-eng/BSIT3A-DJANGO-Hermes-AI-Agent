"""Tests for automatic latest-model detection."""

from unittest import mock
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.news.model_watch import (
    current_models,
    detect_in_text,
    parse_version,
    scan_articles,
    update_latest_models,
)
from apps.news.models import Article, PlatformModel
from apps.news.services import run_refresh


def make_article(title, feed_key='openai_news', summary=''):
    return Article.objects.create(
        title=title,
        url=f'https://example.com/{uuid4()}',
        summary=summary,
        source='Test Feed',
        feed_key=feed_key,
        published_at=timezone.now(),
    )


class VersionParsingTests(TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version('5.5'), (5, 5))
        self.assertEqual(parse_version('6'), (6,))
        self.assertEqual(parse_version(''), ())
        self.assertEqual(parse_version('bogus'), ())

    def test_detect_highest_per_platform(self):
        found = detect_in_text('GPT-5.1 is old, GPT-6.1 just shipped')
        self.assertEqual(found['gpt'], {'label': 'GPT-6.1', 'version': '6.1'})

    def test_claude_tier_and_fallback(self):
        self.assertEqual(
            detect_in_text('Claude Opus 5.5 is here')['claude']['label'],
            'Claude Opus 5.5',
        )
        self.assertEqual(
            detect_in_text('Claude 5.5 is here')['claude']['label'],
            'Claude 5.5',
        )

    def test_other_platforms(self):
        self.assertEqual(detect_in_text('Gemini 4')['gemini']['label'], 'Gemini 4')
        self.assertEqual(detect_in_text('Llama 5')['llama']['label'], 'Llama 5')
        self.assertEqual(
            detect_in_text('Mistral Large 4')['mistral']['label'],
            'Mistral Large 4',
        )
        self.assertEqual(
            detect_in_text('DeepSeek-V4')['deepseek']['label'],
            'DeepSeek V4',
        )

    def test_no_model_mentioned(self):
        self.assertEqual(detect_in_text('Groq adds new inference capacity'), {})


class UpdateLatestModelsTests(TestCase):
    def test_creates_detected_row(self):
        make_article('Introducing GPT-6')
        update_latest_models()
        row = PlatformModel.objects.get(key='gpt')
        self.assertEqual(row.label, 'GPT-6')
        self.assertEqual(row.version, '6')

    def test_ignores_older_versions(self):
        PlatformModel.objects.create(key='gpt', label='GPT-6', version='6')
        make_article('A retrospective on GPT-5')
        changed = update_latest_models()
        self.assertEqual(PlatformModel.objects.get(key='gpt').label, 'GPT-6')
        self.assertEqual(changed, {})

    def test_upgrades_newer_version(self):
        PlatformModel.objects.create(key='gpt', label='GPT-6', version='6')
        make_article('Introducing GPT-6.1')
        changed = update_latest_models()
        self.assertEqual(PlatformModel.objects.get(key='gpt').label, 'GPT-6.1')
        self.assertEqual(changed, {'gpt': 'GPT-6.1'})

    def test_scan_prefers_official_feed_on_tie(self):
        make_article('GPT-6.1 spotted in the wild', feed_key='other_feed')
        make_article('GPT-6.1 official release', feed_key='openai_news')
        detected = scan_articles()
        self.assertEqual(detected['gpt']['version'], '6.1')
        self.assertEqual(detected['gpt']['source_title'], 'GPT-6.1 official release')

    def test_current_models_shape(self):
        PlatformModel.objects.create(key='claude', label='Claude 5.5', version='5.5')
        self.assertEqual(current_models()['claude']['label'], 'Claude 5.5')


class DashboardIntegrationTests(TestCase):
    def test_home_uses_detected_label(self):
        make_article('Introducing GPT-6.1')
        update_latest_models()
        response = self.client.get(reverse('dashboard'))
        labels = {m['key']: m['label'] for m in response.context['model_stats']}
        self.assertEqual(labels['gpt'], 'GPT-6.1')
        self.assertContains(response, 'GPT-6.1')
        for model in response.context['model_stats']:
            self.assertIsInstance(model['highlights'], list)

    def test_home_falls_back_to_curated_label(self):
        response = self.client.get(reverse('dashboard'))
        labels = {m['key']: m['label'] for m in response.context['model_stats']}
        self.assertEqual(labels['gpt'], 'GPT-6 Astra')
        for model in response.context['model_stats']:
            self.assertIsInstance(model['highlights'], list)


class RefreshHookTests(TestCase):
    @mock.patch('apps.news.services.fetch_all_feeds', return_value=([], []))
    @mock.patch('apps.news.services.update_latest_models')
    def test_refresh_runs_detector(self, detector, _fetch):
        run_refresh(trigger='test')
        detector.assert_called_once()
