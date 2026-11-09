# Hermes AI Agent — Public Feature Roadmap

Status: Phase 0-2 implemented and verified (2026-11-07); Phase 3 F12 (search
relevance), Phase 4 F13-F14 (install prompt, offline saved reading), and the UAT
kit shipped (2026-11-09); remaining Phase 3-5 items planned.
Scope: public-facing features. Security hardening is explicitly out of scope for this plan.
Baseline verified against the working tree on 2026-11-06 (`manage.py check` passes).

---

## 1. Goal

Turn the current public dashboard + feed into a fully shareable, indexable, persistent
AI-news product without adding accounts or a login wall.

Current experience: every headline click leaves the site (`news_open` redirect). There is
no article page to share or index, no SEO metadata, no sitemap, bookmarks die with the
session and are capped at 500 IDs, and the PWA cannot be explicitly installed or read
offline.

Success looks like: a visitor lands on `/`, understands the product in five seconds,
opens an article on-site, shares the link, saves it, comes back tomorrow with the save
still there, installs the PWA, and can read saved stories offline.

---

## 2. Verified baseline

| Area | What exists today | Evidence |
|---|---|---|
| Routes | `/` dashboard, `/news/` feed only; `/admin/` deliberately not mounted | `mysite/urls.py:13-16` |
| Article page | None. Feed/home titles link to `news:news_open`, which increments `view_count` and `redirect(article.url)` externally | `templates/news/feed.html:188,226`, `templates/home.html:217`, `apps/news/views.py` `news_open` |
| SEO | `<title>` only; no description, canonical, OG/Twitter, JSON-LD | `templates/theme/base.html:5-11` |
| Sitemap/robots | None in project code | glob found only Django's package file |
| Bookmarks/read | Session-only, max 500 IDs, silently drops oldest | `apps/news/views.py:44-46,96,122` |
| Saved searches | None; only a boolean `?saved=1` filter | `apps/news/views.py:145` |
| History | `view_count` / `last_viewed_at` fields exist and are written on open, no UI | `apps/news/models.py:47-48` |
| Search | `icontains` over title/summary/source, no ranking | `apps/news/views.py:148-154` |
| Topics | Query-param filter only, no topic pages | `apps/news/urls.py`, `_apply_filters` |
| Trending | Computed live in dashboard view, discarded | `apps/core/views.py:224-311` |
| API | `/news/api/articles/` with a limit clamp, no pagination/version/docs | `apps/news/views.py:538-555` |
| PWA | Manifest with icons + one shortcut; SW with install/fetch; no install prompt, no offline reading list, no share target | `static/manifest.webmanifest`, `static/sw.js` |
| Feeds | Hardcoded `FEEDS` list, refresh by web button or management command | `apps/news/feeds.py:29`, `apps/news/services.py`, `scripts/refresh_news.cmd` |
| Dead schema | `saved_by` FK and `is_saved` exist but are unused by views | `apps/news/models.py:38-45` |
| Tests | Django test suite across news/core/info; pytest configured; `manage.py check` clean | `pytest.ini`, `apps/news/test_*.py` |

---

## 3. Principles

1. **No accounts, no login wall.** Persistence is anonymous (signed cookie or opaque profile token).
2. **Server-rendered first.** New pages must work without JS; JS only enhances.
3. **No new heavyweight dependencies.** Stay on Django + stdlib; ApexCharts and Tabler are already vendored.
4. **Every feature ships with tests.** New routes get at least a 200/404/redirect test and one behavior test.
5. **SEO is a feature, not an afterthought.** Every public page gets title, description, canonical, OG tags.

---

## 4. Roadmap

### Phase 0 — Quick wins (0.5 day)

| # | Feature | Files | Effort |
|---|---|---|---|
| 0.1 | Add `robots.txt` pointing at the sitemap | `mysite/urls.py`, `apps/core/views.py` | S |
| 0.2 | RSS autodiscovery `<link rel="alternate">` in base head | `templates/theme/base.html` | S |
| 0.3 | Remove dead `is_saved`/`saved_by` usage from admin display or document as reserved | `apps/news/admin.py` | S |

Acceptance: `GET /robots.txt` returns 200 with `Sitemap: /sitemap.xml`; feed page head contains the RSS link.

---

### Phase 1 — Shareable public surface (Sprint 1, 3-4 days)

**F1. Article reader page** — `GET /news/a/<int:pk>/`
- Server-rendered article page: image, title, source, published date, topic chips, summary,
  view count, "Read original" CTA, related-articles slot, share buttons.
- Feed card titles and dashboard story links point here. `news_open/<pk>/` stays as the
  click-tracking + external redirect endpoint used by the "Read original" button.
- Files: `apps/news/views.py`, `apps/news/urls.py`, `templates/news/article.html`,
  `templates/news/feed.html`, `templates/home.html`.
- Acceptance: existing pk returns 200 with title/description; unknown pk returns 404;
  `news_open` still returns a redirect; detail renders without JS.

**F2. SEO and social layer**
- Base template meta blocks: description, canonical, robots, OG, Twitter card.
- Detail page overrides with article-specific values; JSON-LD `NewsArticle`.
- `sitemap.xml` listing home, feed, topic hubs (Phase 2), and latest N articles.
- Files: `templates/theme/base.html`, `templates/news/article.html`,
  new `apps/news/sitemap.py` or `apps/core/sitemap.py`, `mysite/urls.py`.
- Acceptance: detail contains `og:title`, `og:description`, canonical; sitemap is valid XML
  and contains article URLs; robots references it.

**F3. Landing page split**
- `/` becomes a true landing page: value proposition, live counts, topic chips, latest
  headlines, install CTA, link to full feed.
- Dashboard analytics move to `/dashboard/` (or stay as a section) to keep `/` focused.
- Files: `templates/home.html`, `apps/core/views.py`, `apps/core/urls.py`, CSS.
- Acceptance: 375px mobile pass; no JS errors; hero CTA reaches `/news/`.

---

### Phase 2 — Engagement without accounts (Sprint 2, 3-4 days)

**F4. Persistent anonymous reader profile** (the highest-impact fix)
- Issue an opaque profile token in a signed cookie on first bookmark/read.
- Store bookmarks, read IDs, history, and saved searches in a `ReaderProfile` row
  (UUID token, no PII). Session stays as fallback and migrates into the profile.
- Removes the 500-ID cap and survives session expiry.
- Files: `apps/news/models.py` + migration, new `apps/news/profile.py`,
  `apps/news/views.py`, `apps/news/context_processors.py` (optional), settings.
- Acceptance: bookmark, flush session, reload -> bookmark still set; cap no longer applies;
  no email/name fields stored; migration is additive.

**F5. Saved searches and filter chips**
- "Save this search" button stores `{name, querystring}` on the profile; chips render on
  feed and landing; click restores filters; delete chip.
- Files: `apps/news/views.py`, `templates/news/feed.html`, `apps/news/profile.py`.
- Acceptance: save a search, reload in a new session with the same cookie -> chip present
  and filter restores; malformed stored JSON ignored.

**F6. Share, keyboard, read-time**
- Web Share API with copy-link fallback on detail and feed cards.
- Shortcuts: `j/k` next/prev card, `s` save, `r` mark read, `/` focus search, `?` help.
- Read-time estimate from summary word count in a template filter.
- Files: `static/js/news-feed.js`, `templates/news/feed.html`,
  `apps/news/templatetags/news_extras.py`, CSS.
- Acceptance: shortcuts work only when focus is not in an input; share falls back to copy.

**F7. History + saved exports**
- `/history/` lists recently opened articles from `last_viewed_at`.
- `?saved=1` support in CSV/RSS/JSON exports using the profile, not the session.
- Files: `apps/news/views.py`, `apps/news/urls.py`, `templates/news/history.html`.
- Acceptance: export with saved filter returns only bookmarked rows; history only shows
  articles the current profile opened.

---

### Phase 3 — Content discovery (Sprint 3, 4-5 days)

**F8. Topic hubs**
- `/topics/` grid with counts and latest 3 per topic; `/topics/<slug>/` paginated archive,
  per-topic RSS, description and keyword list.
- Files: `apps/news/views.py`, `apps/news/urls.py`, `templates/news/topics.html`,
  `templates/news/topic_detail.html`, sitemap.
- Acceptance: valid slug 200, unknown slug 404 (distinct from feed's empty-result rule);
  topic RSS valid; topic page included in sitemap.

**F9. Related articles**
- On detail: same-topic articles plus title-token overlap, exclude self, 4 items,
  fallback to same-source newest.
- Files: `apps/news/views.py` or new `apps/news/related.py`, `templates/news/article.html`.
- Acceptance: no self-reference; deterministic ordering; query count bounded (<= 2).

**F10. Trending page + persisted trend series**
- New `TopicDailyCount` (date, topic, count) aggregated during refresh.
- `/trending/` page: top topics last 7 days, biggest movers vs previous week, article list.
- Files: `apps/news/models.py` + migration, `apps/news/services.py`,
  `apps/news/views.py`, `apps/news/urls.py`, template.
- Acceptance: refresh populates counts idempotently; page renders with empty DB; no N+1.

**F11. Dashboard charts**
- Use vendored ApexCharts for 14-day article volume, topic mix, top sources; data via
  `json_script`; graceful empty state.
- Files: `apps/core/views.py`, `templates/home.html`, `static/js/dashboard.js`, CSS.
- Acceptance: charts render with and without data; no console errors; no layout shift.

**F12. Search relevance**
- Weighted ranking: exact title match > title prefix > title contains > summary contains >
  source contains, preserving multi-term AND behavior.
- Files: `apps/news/views.py`.
- Acceptance: title match outranks summary-only match in a fixture test; existing filters
  unaffected.

---

### Phase 4 — PWA and public API (Sprint 4, 3-5 days)

**F13. Install prompt + update flow**
- Capture `beforeinstallprompt`, show a dismissible install card, remember dismissal;
  show "new version available" when the SW updates.
- Files: `templates/theme/base.html`, `static/js/app-ui.js`, `static/sw.js`.
- Acceptance: prompt appears once on supported browsers; dismissal persists; no prompt on
  unsupported browsers or when already installed.

**F14. Offline saved reading list**
- Cache article detail pages on visit; offline fallback lists saved articles from the
  profile and serves cached copies; SW version bump.
- Files: `static/sw.js`, `templates/errors/offline.html`, `static/js/news-feed.js`.
- Acceptance: DevTools offline -> saved article opens from cache; uncached page shows
  offline page; cache is versioned and pruned.

**F15. Share target and shortcuts**
- Manifest: `share_target` to `/news/?q={text}`, shortcuts for Saved, Topics, Trending.
- Acceptance: manifest validates; shortcuts resolve 200.

**F16. API v1**
- `/api/v1/articles/` cursor pagination (opaque cursor), hard limit, allowlisted
  `source/topic/from/to/sort`, typed error JSON, `ETag`/`Cache-Control`.
- `/api/` docs page, OpenAPI JSON generated by hand (no DRF dependency).
- Keep `/news/api/articles/` as a 301/deprecated alias for one release.
- Files: new `apps/news/api.py`, `apps/news/urls.py`, `templates/news/api_docs.html`.
- Acceptance: pagination never exceeds limit; filters validated; invalid cursor -> 400;
  docs page and schema JSON return 200.

**F17. Per-topic RSS + embeddable widget**
- `/news/rss/<slug>/` and `/embed/?topic=<slug>` iframe-friendly mini feed.
- Acceptance: valid RSS; embed renders standalone with no navbar; topic filter applied.

---

### Phase 5 — Backlog (not scheduled)

- Scheduled refresh wrapper using existing `refresh_news` command (Windows Task Scheduler
  or a documented cron entry) + stale-lock alerting in the dashboard.
- Data retention command (`prune_news`) with dry-run and saved-article protection.
- Feed source management via a JSON fixture + management command (keep `/admin/` unmounted).
- Full-text search (SQLite FTS5 / Postgres SearchVector) once article volume justifies it.
- Email digest requires identity — deliberately excluded to preserve the no-accounts scope.

---

## 5. Sprint sequencing

| Sprint | Contents | Estimate | Exit gate |
|---|---|---|---|
| 0 | Quick wins | 0.5 day | robots + RSS autodiscovery live |
| 1 | F1, F2, F3 | 3-4 days | Article page + SEO + landing, tests green |
| 2 | F4, F5, F6, F7 | 3-4 days | Bookmarks survive session flush, saved searches work |
| 3 | F8, F9, F10, F11, F12 | 4-5 days | Topic hubs + trending + charts, query budgets held |
| 4 | F13, F14, F15, F16, F17 | 3-5 days | Install/offline verified, API v1 documented |

Dependency order: F1 before F2/F9; F4 before F5/F7; F10 before F11; F1 before F14.
F3 and F12 are independent and can be parallelized.

---

## 6. Acceptance and testing

Per sprint, the definition of done is:

1. `python manage.py check` clean.
2. `pytest -q` green, including new tests:
   - `apps/news/test_public_pages.py` — detail 200/404, topic hubs, history, trending.
   - `apps/news/test_seo.py` — meta tags, canonical, sitemap, robots.
   - `apps/news/test_profile.py` — persistence across session flush, cap removed, malformed data.
   - `apps/news/test_api_v1.py` — pagination, filters, invalid cursor, ETag.
   - `apps/news/test_search_rank.py` — title outranks summary.
3. Template render test with empty database (no crashes on zero articles).
4. Manual 375px + 1440px check for every new page.
5. Offline check for F14 in Chrome DevTools.
6. No new runtime dependency in `requirements.txt`; no secrets or PII added.

Regression guard: existing feed filters, refresh endpoint, cooldown, exports, and session
bookmark/read behavior must keep their current tests green.

---

## 7. Success signals

- Article detail pageviews vs external redirects (view_count split by destination).
- Returning visitors with a persisted profile (cookie present on second visit).
- Bookmarks per profile over time; reduction in "lost bookmark" reports.
- Sitemap pages indexed (Search Console after deployment).
- PWA installs where measurable; offline page hits.
- API requests by endpoint and version.

---

## 8. Out of scope

- Security hardening (explicitly deferred by operator).
- User accounts, OAuth, email digests, push notifications requiring identity.
- Paid APIs, social-media scraping, full-text article storage.
- Native mobile apps; the PWA remains the mobile story.
- Admin panel exposure; `/admin/` stays unmounted.

---

## 9. Implementation log - Phase 0 + Phase 1 (2026-11-07)

Shipped:

- `GET /news/a/<pk>/` reader page (`apps/news/views.py`, `apps/news/urls.py`,
  `templates/news/article.html`) with OG/JSON-LD, canonical, related coverage, and
  "Read original" click-through to `news_open`.
- Landing/dashboard split: `/` landing, `/dashboard/` dashboard, `/home/` redirect
  (`apps/core/views.py`, `apps/core/urls.py`, `templates/landing.html`).
- SEO surface: description/canonical/OG/Twitter blocks and absolute RSS autodiscovery in
  `templates/theme/base.html`; `/robots.txt` and `/sitemap.xml`
  (`mysite/seo.py`, `mysite/urls.py`).
- Feed cards now link on-site to the detail page; internal links no longer open new tabs.
- Standalone error pages for 404/500/offline.

Verification evidence (run in this working tree):

- `manage.py check` clean.
- `pytest -q --ds=mysite.settings_sqlite` -> 149 passed, 6 subtests passed.
- Live `runserver` smoke: `/`, `/dashboard/`, `/news/`, `/news/a/1/`, `/sitemap.xml`,
  `/robots.txt` all 200 with expected content types.
- 25/25 boss-level assertions: single H1, escaped title, valid JSON-LD, absolute
  canonical/RSS, sitemap well-formed + detail URL + no RSS entry, robots sitemap line,
  custom 404 under `DEBUG=False`.

Deferred to Phase 3+: topic hubs, trending page, search ranking, API v1, PWA offline
reading list.

---

## 10. Implementation log - Phase 2 (2026-11-07)

Shipped:

- `ReaderProfile` (`apps/news/models.py`, migration `0005_readerprofile.py`) keyed by a
  signed `hermes_reader` cookie: bookmarks, read IDs, history, saved searches, no PII.
- `apps/news/profile.py` helpers for ID lists, history (200 cap), saved searches (20 cap),
  cookie creation, and legacy session migration.
- Feed save/read toggles and article opens now persist to the profile; feed and dashboard
  reflect profile state; legacy session IDs migrate on first authenticated feed load.
- Saved searches: `POST /news/searches/save/`, `POST /news/searches/<index>/delete/`,
  save form and chips on the feed, no-JS forms.
- Share buttons (Web Share API + clipboard fallback), keyboard shortcuts (`j/k/s/r///?`),
  and read-time estimates on feed + article pages.
- `GET /news/history/` reading-history page and navbar links.
- Saved-only exports: `?saved=1` now filters CSV, RSS, and JSON API results by profile.

Verification evidence (run in this working tree):

- `manage.py check` clean; `makemigrations --check --dry-run` -> `No changes detected`.
- `pytest -q --ds=mysite.settings_sqlite` -> 186 passed, 6 subtests passed.
- Targeted suites: `test_profile.py` (21), `test_saved_searches.py` (8),
  `test_history.py` (8).
- Live `runserver` smoke: `/news/?q=phase` 200 with save form, read-time and share
  controls; `/news/a/<pk>/` 200 with share/read-time; `/news/history/` 200 empty state;
  landing 200 with History nav.

---

## 11. Implementation log - Phase 3 F12, Phase 4 F13/F14, UAT kit (2026-11-09)

Shipped:

- **F12 search relevance** (`apps/news/views.py`): per-term weighted relevance
  annotation (title exact 10, title prefix 5, title contains 4, summary 2, source 1),
  ordered by `-relevance` then newest when a query is present; explicit `oldest` and
  `title` sorts still win; multi-term AND behavior unchanged.
  Tests: `apps/news/test_search_rank.py` (5 cases).
- **F13 install prompt + update flow** (`static/js/app-ui.js`, `static/css/app-ui.css`):
  captured `beforeinstallprompt` with a dismissible Bootstrap card, localStorage
  dismissal (`hermes_install_dismissed_v1`), standalone detection, and a one-time
  `controllerchange` reload banner guarded by sessionStorage.
- **F14 offline saved reading + SW scope fix**: service worker now served from
  `/sw.js` with `Service-Worker-Allowed: /` (root scope), `/offline.html` route added,
  v12 static cache plus runtime cache for HTML navigations (network-first, cached
  article fallback), feed cards mirror saved articles into
  `localStorage['hermes_saved_articles_v1']`, and the offline page lists them.
  Tests added in `apps/core/tests.py` (`OfflineServiceWorkerTests`).
- **UAT kit**: `docs/UAT-KIT.md` (schedule, roles, ethics, environment checklist,
  participant profile, 7 timed tasks mapped to real routes, 7-item Likert survey,
  scoring, moderation rules) and `docs/UAT-RESULTS-TEMPLATE.md` (empty tables only).

Verification evidence (run in this working tree):

- `pytest -q --ds=mysite.settings_sqlite` -> 193 passed, 6 subtests passed in 6.58s.
- `manage.py check` -> no issues (0 silenced).
- `node --check` clean on `static/js/app-ui.js`, `static/js/news-feed.js`, `static/sw.js`.
- `GET /sw.js` -> 200, `application/javascript`, `Service-Worker-Allowed: /`,
  `Cache-Control: no-cache` (6,284 bytes).
- `GET /offline.html` -> 200, contains the offline page (6,652 bytes).
- `pytest apps/news/test_search_rank.py -v` -> 5 passed.

Still manual (browser context required): exercising the real `beforeinstallprompt`
event, Chrome DevTools offline reload of a cached saved article, and the SW update
banner. Remaining roadmap items: F8 topic hubs, F10 trending page, F11 dashboard
charts, F15 share target, F16 API v1, F17 per-topic RSS/embed.
