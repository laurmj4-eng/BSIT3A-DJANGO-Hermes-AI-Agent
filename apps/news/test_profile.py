"""Tests for apps.news.profile — anonymous reader profile persistence."""

import json
import uuid
from importlib import import_module

from django.conf import settings
from django.core import signing
from django.core.management import call_command
from django.db import models
from django.db.migrations import CreateModel
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.news import profile as profile_mod
from apps.news.models import Article, ReaderProfile
from apps.news.profile import (
    COOKIE_MAX_AGE,
    PROFILE_COOKIE,
    add_id,
    get_reader_profile,
    ids,
    merge_ids,
    record_history,
    remove_id,
    set_profile_cookie,
)


class ReaderProfileModelTests(TestCase):
    def test_model_has_no_pii_or_user_field(self):
        field_names = {f.name for f in ReaderProfile._meta.get_fields()}
        for banned in ("user", "email", "name", "ip", "ip_address", "username", "first_name", "last_name"):
            self.assertNotIn(banned, field_names)
        for f in ReaderProfile._meta.fields:
            self.assertNotIsInstance(f, models.ForeignKey)
        self.assertEqual(ReaderProfile._meta.db_table, "tblnewsreaderprofile")
        self.assertEqual(ReaderProfile._meta.ordering, ["-updated_at"])


class CookieRoundTripTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_create_sets_signed_cookie_and_round_trips(self):
        request = self.factory.get("/")
        created = get_reader_profile(request, create=True)
        self.assertIsNotNone(created)
        self.assertTrue(hasattr(request, "_reader_profile_cookie"))

        response = set_profile_cookie(HttpResponse(), request)
        cookie = response.cookies[PROFILE_COOKIE]
        self.assertEqual(int(cookie["max-age"]), COOKIE_MAX_AGE)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(bool(cookie["secure"]), not settings.DEBUG)

        replay = self.factory.get("/")
        replay.COOKIES[PROFILE_COOKIE] = cookie.value
        fetched = get_reader_profile(replay)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.pk, created.pk)
        self.assertEqual(fetched.token, created.token)

    def test_invalid_cookie_returns_none_without_create(self):
        request = self.factory.get("/")
        request.COOKIES[PROFILE_COOKIE] = "not-a-valid-signed-value"
        self.assertIsNone(get_reader_profile(request))

    def test_tampered_uuid_cookie_returns_none(self):
        request = self.factory.get("/")
        request.COOKIES[PROFILE_COOKIE] = signing.get_cookie_signer(salt=PROFILE_COOKIE).sign("not-a-uuid")
        self.assertIsNone(get_reader_profile(request))

    def test_unknown_token_returns_none(self):
        request = self.factory.get("/")
        request.COOKIES[PROFILE_COOKIE] = signing.get_cookie_signer(salt=PROFILE_COOKIE).sign(str(uuid.uuid4()))
        self.assertIsNone(get_reader_profile(request))


class IdListTests(TestCase):
    def setUp(self):
        self.profile = ReaderProfile.objects.create()

    def test_add_remove_dedupe_newest_first(self):
        add_id(self.profile, "bookmarks", 1)
        add_id(self.profile, "bookmarks", 2)
        add_id(self.profile, "bookmarks", 1)  # re-add moves to front, no dupe
        self.assertEqual(ids(self.profile, "bookmarks"), [1, 2])
        remove_id(self.profile, "bookmarks", 2)
        self.assertEqual(ids(self.profile, "bookmarks"), [1])
        remove_id(self.profile, "bookmarks", 999)
        self.assertEqual(ids(self.profile, "bookmarks"), [1])

    def test_600_ids_survive_no_500_cap(self):
        for n in range(600):
            add_id(self.profile, "read_ids", n)
        self.assertEqual(len(ids(self.profile, "read_ids")), 600)

    def test_bookmarks_capped_at_1000(self):
        for n in range(1100):
            add_id(self.profile, "bookmarks", n)
        self.assertEqual(len(ids(self.profile, "bookmarks")), 1000)

    def test_merge_ids_capped(self):
        merged = merge_ids(self.profile, "read_ids", list(range(1500)))
        self.assertEqual(len(merged), 1000)
        self.assertEqual(merged[0], 0)
        self.assertEqual(merged[-1], 999)

    def test_non_int_values_ignored(self):
        self.profile.bookmarks = [1, "x", None, True, 2.5, "3", 2]
        self.profile.save()
        self.assertEqual(ids(self.profile, "bookmarks"), [1, 3, 2])
        self.assertEqual(add_id(self.profile, "bookmarks", "nope"), [1, 3, 2])

    def test_malformed_json_ignored(self):
        self.profile.bookmarks = {"not": "a list"}
        self.profile.read_ids = "garbage"
        self.profile.history = 42
        self.profile.save()
        self.assertEqual(ids(self.profile, "bookmarks"), [])
        self.assertEqual(ids(self.profile, "read_ids"), [])
        self.assertEqual(record_history(self.profile, 7)[0]["id"], 7)

    def test_none_profile_tolerated(self):
        self.assertEqual(ids(None, "bookmarks"), [])
        self.assertEqual(add_id(None, "bookmarks", 1), [])
        self.assertEqual(remove_id(None, "bookmarks", 1), [])
        self.assertEqual(merge_ids(None, "bookmarks", [1]), [])
        self.assertEqual(record_history(None, 1), [])


class HistoryTests(TestCase):
    def setUp(self):
        self.profile = ReaderProfile.objects.create()

    def test_history_newest_first_dedupe_and_cap_200(self):
        for n in range(250):
            record_history(self.profile, n)
        history = self.profile.history
        self.assertEqual(len(history), 200)
        self.assertEqual(history[0]["id"], 249)
        self.assertTrue(all("at" in e and "id" in e for e in history))
        record_history(self.profile, 100)  # re-read moves to front, no dupe
        history = self.profile.history
        self.assertEqual(history[0]["id"], 100)
        self.assertEqual(len([e for e in history if e["id"] == 100]), 1)

    def test_history_malformed_entries_dropped(self):
        self.profile.history = [{"id": "x", "at": "t"}, {"id": 5}, "junk", {"id": 9, "at": "2026-01-01T00:00:00+00:00"}]
        self.profile.save()
        merged = record_history(self.profile, 1)
        ids_only = [e["id"] for e in merged]
        self.assertEqual(ids_only, [1, 9])


class MigrationAdditiveTests(TestCase):
    def test_0005_is_additive_createmodel_only(self):
        module = import_module("apps.news.migrations.0005_readerprofile")
        operations = module.Migration.operations
        self.assertTrue(operations)
        for op in operations:
            self.assertIsInstance(op, CreateModel)

    def test_makemigrations_check_shows_no_changes(self):
        # Raises SystemExit(1) if model state differs from migrations.
        call_command("makemigrations", "news", check=True, dry_run=True, verbosity=0)

class ProfileViewIntegrationTests(TestCase):
    """The feed, toggles and click-through must all use the signed profile."""

    def setUp(self):
        self.article = Article.objects.create(
            title="Profile Integration Story",
            url="https://example.com/profile-story",
            summary="A story used to prove profile persistence.",
            source="Profile Source",
            feed_key="profile",
        )
        self.other = Article.objects.create(
            title="Second Profile Story",
            url="https://example.com/profile-story-2",
            summary="Another story.",
            source="Profile Source",
            feed_key="profile",
        )

    def test_bookmark_survives_session_flush(self):
        client = Client()
        response = client.post(reverse("news:news_toggle_save", args=[self.article.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["is_saved"])

        cookie = client.cookies[PROFILE_COOKIE].value
        profile = ReaderProfile.objects.get()
        self.assertEqual(profile.bookmarks, [self.article.pk])

        fresh = Client()
        fresh.cookies[PROFILE_COOKIE] = cookie
        feed = fresh.get(reverse("news:news_list") + "?saved=1")
        self.assertEqual(feed.status_code, 200)
        self.assertContains(feed, self.article.title)
        self.assertNotContains(feed, self.other.title)

    def test_toggle_merges_legacy_session_ids(self):
        from apps.news.views import SAVED_SESSION_KEY

        client = Client()
        session = client.session
        session[SAVED_SESSION_KEY] = [self.article.pk]
        session.save()

        response = client.post(reverse("news:news_toggle_save", args=[self.other.pk]))
        self.assertEqual(response.status_code, 200)
        profile = ReaderProfile.objects.get()
        self.assertEqual(profile.bookmarks, [self.other.pk, self.article.pk])

    def test_open_records_history_and_sets_cookie(self):
        client = Client()
        response = client.get(reverse("news:news_open", args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(PROFILE_COOKIE, client.cookies)

        profile = ReaderProfile.objects.get()
        self.assertEqual(profile.history[0]["id"], self.article.pk)
        self.assertIn(self.article.pk, profile.read_ids)

    def test_profile_cookie_is_httponly_lax_and_long_lived(self):
        client = Client()
        response = client.post(reverse("news:news_toggle_read", args=[self.article.pk]))
        cookie = response.cookies[PROFILE_COOKIE]
        self.assertEqual(int(cookie["max-age"]), COOKIE_MAX_AGE)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_feed_migrates_legacy_session_bookmarks_into_profile(self):
        from apps.news.views import SAVED_SESSION_KEY

        client = Client()
        client.get(reverse("news:news_open", args=[self.article.pk]))  # creates profile
        session = client.session
        session[SAVED_SESSION_KEY] = [self.other.pk]
        session.save()

        feed = client.get(reverse("news:news_list") + "?saved=1")
        self.assertEqual(feed.status_code, 200)
        self.assertContains(feed, self.other.title)

        profile = ReaderProfile.objects.get()
        self.assertIn(self.other.pk, profile.bookmarks)
        self.assertNotIn(SAVED_SESSION_KEY, client.session)
