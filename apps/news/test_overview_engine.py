from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.news.overview_engine import build_overview


def article(**overrides):
    defaults = {
        "id": 1,
        "title": "Cyberattack disrupts port operations",
        "summary": "A cyberattack disrupted port operations across the region this morning.",
        "source": "The Record",
        "url": "https://example.com/cyber-story",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BuildOverviewTests(SimpleTestCase):
    def test_returns_cited_bullets_and_sources(self):
        result = build_overview("cyberattack", [article()])

        self.assertEqual(result["mode"], "local")
        self.assertEqual(result["query"], "cyberattack")
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(len(result["bullets"]), 1)
        self.assertEqual(result["bullets"][0]["source"], "The Record")
        self.assertEqual(result["bullets"][0]["url"], "https://example.com/cyber-story")
        self.assertEqual(result["sources"][0]["article_id"], 1)

    def test_bullet_is_an_exact_slice_of_title_or_summary(self):
        first = article(
            id=1,
            title="Ports hit by cyberattack",
            summary="Officials confirmed the cyberattack affected three terminals today.",
        )
        second = article(
            id=2,
            title="Ransomware group claims breach",
            summary="The ransomware group claimed responsibility for the breach on Monday.",
            source="BleepingComputer",
            url="https://example.com/ransomware",
        )

        result = build_overview("cyberattack ransomware", [first, second])

        for bullet in result["bullets"]:
            origin = next(
                row for row in (first, second) if row.id == bullet["article_id"]
            )
            self.assertTrue(
                bullet["text"] in origin.summary or bullet["text"] in origin.title
            )

    def test_duplicate_sentences_collapse(self):
        summary = "The same cyberattack sentence appears in both articles today."
        result = build_overview(
            "cyberattack",
            [
                article(id=1, title="One", summary=summary),
                article(id=2, title="Two", summary=summary, source="Other"),
            ],
        )

        self.assertEqual(len(result["bullets"]), 1)

    def test_empty_query_or_articles_returns_none(self):
        self.assertIsNone(build_overview("", [article()]))
        self.assertIsNone(build_overview("cyberattack", []))
        self.assertIsNone(build_overview("the and for", [article()]))
        self.assertIsNone(build_overview("is", [article()]))

    def test_two_letter_query_ai_is_supported(self):
        item = article(
            id=1,
            title="AI model released",
            summary="A new AI model was released today with stronger reasoning.",
            source="AI News",
        )

        result = build_overview("AI", [item])

        self.assertIsNotNone(result)
        self.assertIn("AI", result["bullets"][0]["text"])

    def test_two_letter_query_does_not_match_substrings(self):
        noise = article(
            id=1,
            title="Kitchen update",
            summary="She said the kitchen was closed for repairs today.",
            source="Food",
            url="https://example.com/food",
        )
        relevant = article(
            id=2,
            title="AI model released",
            summary="A new AI model was released today with stronger reasoning.",
            source="AI News",
            url="https://example.com/ai",
        )

        result = build_overview("AI", [noise, relevant])

        self.assertEqual(result["bullets"][0]["article_id"], 2)

    def test_bullets_are_capped_by_max_sources(self):
        rows = [
            article(
                id=index,
                title=f"Cyberattack story {index}",
                summary=f"The cyberattack disrupted operations in region {index} today.",
                source=f"Source {index}",
                url=f"https://example.com/{index}",
            )
            for index in range(1, 5)
        ]

        result = build_overview("cyberattack", rows, max_sources=1, max_bullets=4)

        self.assertEqual(len(result["bullets"]), 1)
        self.assertEqual(result["source_count"], 1)
        self.assertIn("1 recent article from 1 source matches", result["lead"])

    def test_relevant_article_ranks_first(self):
        unrelated = article(
            id=1,
            title="Cooking update",
            summary="A long unrelated sentence about cooking and recipes in the kitchen today.",
            source="Food",
            url="https://example.com/food",
        )
        relevant = article(
            id=2,
            title="Cyberattack reported",
            summary="A cyberattack disrupted port operations across the region this morning.",
            source="Security",
            url="https://example.com/security",
        )

        result = build_overview("cyberattack", [unrelated, relevant])

        self.assertEqual(result["bullets"][0]["article_id"], 2)

    def test_summary_excerpts_are_preferred_over_headline_only_items(self):
        title_only = article(
            id=1,
            title="Cyberattack headline only",
            summary="",
            source="Aggregator",
            url="https://example.com/aggregator",
        )
        first = article(
            id=2,
            title="Ports hit",
            summary="The cyberattack disrupted three container terminals for several hours today.",
            source="Security",
            url="https://example.com/security-one",
        )
        second = article(
            id=3,
            title="Agency responds",
            summary="The agency confirmed the cyberattack and opened a formal investigation on Monday.",
            source="Record",
            url="https://example.com/security-two",
        )

        result = build_overview("cyberattack", [title_only, first, second])

        self.assertEqual(len(result["bullets"]), 2)
        self.assertTrue(all("headline only" not in row["text"] for row in result["bullets"]))

    def test_long_text_is_truncated_on_a_word_boundary(self):
        summary = " ".join(["cyberattack"] + ["word"] * 80)
        result = build_overview("cyberattack", [article(summary=summary)])

        text = result["bullets"][0]["text"]
        self.assertLessEqual(len(text), 240)
        self.assertFalse(text.endswith(" "))
        self.assertTrue(text.endswith("word"))

    def test_unsafe_urls_are_not_returned(self):
        result = build_overview(
            "cyberattack",
            [article(url="javascript:alert(1)")],
        )

        self.assertEqual(result["bullets"][0]["url"], "")
        self.assertEqual(result["sources"][0]["url"], "")
