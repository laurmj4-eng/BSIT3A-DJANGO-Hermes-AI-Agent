"""Tests for article topic classification, including the cybersecurity topic."""
from django.test import SimpleTestCase, TestCase

from apps.news.classification import TOPIC_DEFS, classify_text, ensure_topics


class CybersecurityClassificationTests(SimpleTestCase):
    def test_cyberattack_headline_classifies_as_cybersecurity(self):
        slugs = classify_text(
            'Major ransomware cyberattack hits hospital network',
            'Attackers encrypted patient records and demanded payment.',
        )
        self.assertIn('cybersecurity', slugs)

    def test_normal_ai_model_headline_is_not_cybersecurity(self):
        slugs = classify_text(
            'OpenAI releases GPT-6 with improved reasoning',
            'The new model scores higher on benchmark suites.',
        )
        self.assertNotIn('cybersecurity', slugs)

    def test_each_cybersecurity_keyword_matches(self):
        samples = {
            'cyberattack': 'Cyberattack disrupts port operations',
            'cyberattacks': 'Cyberattacks rise across Europe',
            'cybersecurity': 'Cybersecurity firm reports new campaign',
            'ransomware': 'Ransomware gang leaks stolen files',
            'malware': 'Malware found in popular app',
            'breach': 'Data breach exposes millions of records',
            'data leak': 'Data leak traced to misconfigured bucket',
            'vulnerability': 'Critical vulnerability patched in router',
            'zero-day': 'Zero-day exploited in the wild',
            'phishing': 'Phishing campaign targets bank customers',
            'threat actor': 'Threat actor linked to espionage',
            'cve': 'CVE-2026-1234 allows remote code execution',
            'security incident': 'Security incident shuts down service',
            'hacked': 'Company hacked after password reuse',
        }
        for keyword, headline in samples.items():
            with self.subTest(keyword=keyword):
                self.assertIn('cybersecurity', classify_text(headline))

    def test_generic_security_keyword_does_not_match(self):
        self.assertNotIn(
            'cybersecurity',
            classify_text('Security and safety policy update for AI models'),
        )


class CybersecurityTopicDefinitionTests(SimpleTestCase):
    def test_topic_definition_fields(self):
        topic = next(t for t in TOPIC_DEFS if t['slug'] == 'cybersecurity')
        self.assertEqual(topic['name'], 'Cybersecurity')
        self.assertTrue(topic['color'])
        self.assertTrue(topic['description'])
        self.assertIn('cybersecurity', topic['keywords'])

    def test_generic_keywords_excluded(self):
        topic = next(t for t in TOPIC_DEFS if t['slug'] == 'cybersecurity')
        self.assertNotIn('security', topic['keywords'])
        self.assertNotIn('exploit', topic['keywords'])


class EnsureCybersecurityTopicTests(TestCase):
    def test_ensure_topics_creates_cybersecurity_topic(self):
        ensure_topics()
        from apps.news.models import Topic

        topic = Topic.objects.get(slug='cybersecurity')
        self.assertEqual(topic.name, 'Cybersecurity')
        self.assertIn('ransomware', topic.keywords.split(','))
