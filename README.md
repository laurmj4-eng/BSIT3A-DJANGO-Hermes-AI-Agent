# HERMES AI AGENT

### A Web-Based AI News Aggregation and Intelligence System

**BSIT Capstone Project Concept Paper**

> BSIT 3A — Django Project

---

## Table of Contents

- [Concept Paper](#concept-paper)
- [Technical Overview](#technical-overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [How to Run](#how-to-run)
- [Project Structure](#project-structure)
- [Testing & Verification](#testing--verification)
- [User Acceptance Testing (UAT)](#user-acceptance-testing-uat)
- [Documentation Index](#documentation-index)

---

## Video

[https://laurmj4-eng.github.io/BSIT3A-DJANGO-Hermes-AI-Agent/evidence/hermes-ai-agent-demo-2026-10-30.mp4](https://laurmj4-eng.github.io/BSIT3A-DJANGO-Hermes-AI-Agent/evidence/hermes-ai-agent-demo-2026-10-30.mp4)

---

## Group Members

| Name |
| --- |
| MJ Laurito |
| JM Advincula |
| Inbanez Alfon Franc |

October 2026

---

## Concept Paper

### Introduction

#### Background of the Project

Artificial intelligence is advancing rapidly, and information about new models, tools, research, and industry developments is published continuously across many independent outlets. For developers and IT students, keeping current with these developments is important for learning, experimentation, and informed decision-making. However, AI-related news is fragmented across numerous websites, blogs, research repositories, and news aggregators, each with its own format, update cadence, and coverage focus. As a result, users must visit multiple sources repeatedly to assemble a complete picture of recent AI activity, which is time-consuming and prone to missing relevant updates.

The proposed Hermes AI Agent will be a web-based AI news aggregation and intelligence system developed as a BSIT 3A academic project. It will be built with Django 5 and will aggregate more than 20 public RSS and Atom feeds into a single, searchable dashboard. The system will collect headlines from these sources, normalize them into a common structure, and store them in a relational database. Duplicate articles will be removed by URL, so repeated refreshes will not create redundant entries. Topics will be assigned through keyword-based classification rather than through a language model; the system will not use a large language model or any generative AI component. Users will be able to search and filter articles by headline, summary, source, topic, date range, and read or saved state. Additional capabilities will include per-browser-session bookmarks and read tracking, a source health dashboard reporting feed status and refresh runs, CSV, XLSX, RSS, and JSON exports, dashboard analytics, and an installable progressive web application with an offline fallback. These features will reduce the effort required to monitor AI news and provide a consistent, accessible interface for the target users.

#### Statement of the Problem or Project Objectives

The central problem is that developers and IT students do not know the latest AI updates because AI news is fragmented across many sources. These users currently lack a single, consolidated, and easily searchable view of recent AI developments; without one, they must visit multiple sites and manually compare repeated or unrelated stories. Manual monitoring is inefficient and increases the likelihood that important updates are overlooked.

The project aims to design, develop, and evaluate a web-based AI news aggregation and intelligence system that addresses this problem. Specifically, the project will:

1. Aggregate public RSS and Atom feeds from more than 20 AI news sources into one dashboard and deduplicate collected articles by URL.
2. Classify articles into topics using transparent keyword rules.
3. Provide search, filtering, bookmarking, and read tracking for efficient article management.
4. Monitor source health and record refresh runs for transparency.
5. Provide export and integration options through CSV, XLSX, RSS, and a JSON articles API, together with dashboard analytics.
6. Deliver an installable progressive web application with an offline fallback and conduct user acceptance testing with IT students and developers.

The system will remain a deterministic, rule-based aggregator and will not employ a large language model or generative AI. Through these objectives, Hermes AI Agent will help developers and IT students stay informed about current AI developments through a single, consolidated interface.

#### Significance of the Project

The project will provide practical value to the following beneficiaries:

- **Developers and IT students:** a single feed for tracking AI updates, reducing the time spent switching between sources and supporting coursework, projects, and self-study.
- **AI enthusiasts and researchers:** a searchable, deduplicated view of recent AI news with topic filters, source health information, and export options for further analysis.
- **IT students and future researchers:** a reference implementation of a Django-based feed aggregation system that demonstrates RSS/Atom parsing, deduplication, session-based state, PWA support, and source monitoring.
- **The institution:** a publicly accessible digital resource that supports AI literacy and technology-enhanced learning.

#### Alignment with Institutional Research Agenda and Sustainable Development Goals

The project will align with the institution's research priority on digital transformation, ICT-enabled information services, and technology-enhanced learning. It will apply web development, database management, and information organization to a practical problem faced by developers and IT students.

The project will also contribute to the following Sustainable Development Goals:

- **SDG 4 (Quality Education):** By providing free public access to current AI information, the system will support learning, research, and skills development among students and independent learners.
- **SDG 9 (Industry, Innovation, and Infrastructure):** By building a web-based information infrastructure from open-source tools and public feeds, the project will demonstrate a low-cost digital service that can be reused and extended.

### Scope and Limitations

#### System Scope & Technical Architecture

The proposed Hermes AI Agent will be a web-based RSS/Atom news aggregation and topic-classification system for a BSIT 3A capstone project. In this project, the term "agent" refers to the automated feed-gathering and monitoring service; it does not imply a conversational AI assistant. The system will ingest more than 20 curated public RSS and Atom feeds, deduplicate articles by URL so the same story is not shown twice, and classify each article into topics using transparent keyword-based rules rather than a machine-learned model. The application will be fully public: no user accounts will be required, and personal features such as bookmarks and read state will be stored per browser session. This will keep onboarding friction low while making clear that saved state will not persist across sessions or devices.

Architecturally, the system will follow a classic server-rendered Django pattern. The backend will run on Django 5.0.14 with MySQL/MariaDB as the datastore, and feed parsing will be handled entirely with the Python standard library, avoiding heavyweight third-party feed dependencies. The presentation layer will combine Tabler UI, Bootstrap 5.3.7, and Font Awesome 6.5.1 for a consistent, responsive interface. The system will be delivered as a Progressive Web App (PWA), including a service worker and a web app manifest, so it can be installed to a home screen and used with basic offline caching on supported desktop and mobile browsers.

| Component | Description & Coverage |
| --- | --- |
| Core Modules | Feed aggregation of 20+ public RSS/Atom sources; URL-based deduplication; keyword-based topic classification; search, filtering, sorting, and pagination; session-based bookmarks and read-state tracking; source health and refresh-run monitoring; CSV, XLSX, RSS, and JSON export/API access; dashboard analytics; PWA/offline support; theme settings. |
| Technology Stack | Django 5.0.14; MySQL/MariaDB; Python standard library for RSS/Atom parsing; Tabler UI, Bootstrap 5.3.7, and Font Awesome 6.5.1; PWA support via service worker and web app manifest. |
| Target Users | Primary: developers and IT students who need a focused AI news reader. Secondary: AI enthusiasts and researchers who want a lightweight, transparent aggregation tool with keyword-based organization. |
| Limitations | Public RSS/Atom feeds only; no paid APIs or social-media scraping; no full-text article storage; no user accounts, so bookmarks and read state are session-based and do not persist across devices; no admin panel; no push notifications; no native mobile app (PWA only); no LLM or generative AI model; refresh depends on third-party feed availability and rate limits; refresh is on demand with a 60-second cooldown. |

#### Evaluation Plan

A future user acceptance test (UAT) will be conducted with 10–15 participants drawn from IT students and practicing developers. Each participant will complete representative tasks: installing the PWA on a supported browser, browsing articles by topic, searching and filtering the feed, refreshing the feed list after the 60-second cooldown, bookmarking an article within a session, and marking articles as read. The evaluation will measure task success rate, time on task for locating a specific topic, and post-test satisfaction using a five-point Likert scale. Observers will record any refresh failures attributable to third-party feed unavailability. The evaluation will analyze the collected data descriptively and use the findings to prioritize improvements in a future iteration; no claims about system performance will be made until this evaluation is completed.

A ready-to-run UAT kit — moderator script, timed tasks, Likert survey, scoring
sheet, and results template — is documented in `docs/UAT-KIT.md` and
`docs/UAT-RESULTS-TEMPLATE.md`.

---

## Technical Overview

The sections below document the implementation details referenced in the concept paper.

Hermes AI Agent pulls live news from several public RSS/Atom feeds and presents
them in one clean dashboard. Instead of opening ten different tabs to keep up
with the AI industry, users get a single feed they can search, filter, and
save stories from.

The system ships with:

- **Live feed aggregation** from 20+ sources, including Google News (AI), TechCrunch AI,
  VentureBeat AI, arXiv cs.AI, and MIT News AI
- **Automatic de-duplication** — articles are keyed on their URL, so refreshing
  never creates duplicates
- **Per-feed fault isolation** — if one source is down or rate-limiting, the
  rest still load and the user is told exactly which one failed
- **Search and filtering** across headlines, summaries, sources, topics, and
  saved/unread state, with weighted relevance ranking and autocomplete suggestions
- **Bookmarking and read tracking** stored per browser session
- **Source health dashboard** for feed status, article totals, and refresh runs
- **Exports and integrations** via CSV, XLSX, RSS, and a JSON articles API
- **Dashboard analytics** for article counts, trending stories, topic mix, and
  source breakdown
- **Installable PWA** with an install prompt, update notification, offline
  fallback, cached saved-reading list, and theme settings

---

## Features

### AI News Feed
- Aggregates 20+ public RSS/Atom feeds
- Search by headline, summary, or source with weighted relevance ranking
  (title matches outrank summary-only matches) and autocomplete suggestions
- Filter by source, topic, date range, saved state, and read state
- List or grid view, paginated results
- One-click bookmark / un-bookmark and read / unread
- Manual refresh with status reporting and a 60-second cooldown
- CSV, XLSX, RSS, and JSON export endpoints

### Dashboard
- Total, unread, saved, weekly, and topic counts
- Latest headlines with bookmarking
- Trending articles and topic mix
- Source health summary with per-source article counts
- Manual refresh and a link to the feed

### Source Health
- Per-source status: healthy, idle, failing, partial, or running
- Article totals and latest article timestamps
- Recent refresh runs with trigger, counts, duration, and errors
- Served as JSON APIs at `/news/sources/json/` and `/news/sources/runs/`

### Public Access
- No sign-in wall — the dashboard and news feed are public
- Bookmarks are stored in an anonymous signed-cookie reader profile
  (no account needed; clearing cookies resets them)
- No admin panel or sign-in surface is exposed

### Security
- Public read-only pages — no login required
- No admin panel or sign-in surface is exposed
- Refresh cooldown — successful/partial refreshes are throttled to once every
  60 seconds; a running refresh returns `409`
- CSRF protection on all state-changing requests, including bookmark and read actions
- Anonymous signed-cookie reader profile for bookmarks and read state, no account
  data collected

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Framework | Django 5.0.14 |
| Database | MySQL / MariaDB (`bsitcrud`) |
| Frontend | Tabler UI, Bootstrap 5.3.7, Font Awesome 6.5.1 |
| Feed parsing | Python standard library only (`urllib` + `xml.etree`) |
| Excel export | Hand-built OOXML package (`zipfile` + XML) |
| PWA | Service worker + web app manifest |

---

## How to Run

### Prerequisites

- Python 3.12+ (the repo ships a `.venv`)
- XAMPP with MySQL/MariaDB running

### Setup

1. Start **MySQL** from the XAMPP Control Panel.
2. Verify the `bsitcrud` database exists (defaults: user `root`, empty password,
   host `localhost:3306`).
3. Install dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   If the venv is missing: `python -m venv .venv` first.

4. Apply migrations:

   ```powershell
   .\.venv\Scripts\python.exe manage.py migrate
   ```

5. Fetch the first batch of news:

   ```powershell
   .\.venv\Scripts\python.exe manage.py refresh_news --limit 25
   ```

6. Start the development server:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
   ```

7. Open <http://127.0.0.1:8000/>

### Configuration (environment variables)

| Variable | Default |
| --- | --- |
| `DB_NAME` | `bsitcrud` |
| `DB_USER` | `root` |
| `DB_PASSWORD` | *(empty)* |
| `DB_HOST` / `DB_PORT` | `localhost` / `3306` |
| `DJANGO_DEBUG` | `1` |
| `DJANGO_SECRET_KEY` | development fallback defined in `mysite/settings.py` |

### Tests (no MySQL required)

```powershell
.\.venv\Scripts\python.exe -m pytest -q --ds=mysite.settings_sqlite
```

### Scheduled refresh (optional)

Run `scripts\refresh_news.cmd` from Windows Task Scheduler to refresh feeds
hourly. The web app also exposes a manual **Refresh feeds** button with a
60-second cooldown.

---

## Project Structure

```text
mysite/          # settings, root URLConf, SEO, error views
apps/core/       # landing page, dashboard, service worker + offline routes
apps/news/       # models, views, feeds, refresh service, classification,
                 # reader profile, exports, JSON API, search, source health
apps/info/       # informational scaffolding (not routed)
apps/users/      # auth scaffolding (not routed)
templates/       # theme base, news pages, error/offline pages
static/          # CSS, JS, icons, sw.js, manifest.webmanifest
docs/            # UAT kit, results template, improvement plan
scripts/         # refresh_news.cmd (Task Scheduler wrapper)
sql/             # database dump/seed
```

---

## Testing & Verification

- Full suite: **193 tests passed, 6 subtests passed**
  (`.\.venv\Scripts\python.exe -m pytest -q --ds=mysite.settings_sqlite`)
- `manage.py check` returns no issues
- `node --check` clean for `static/js/app-ui.js`, `static/js/news-feed.js`,
  and `static/sw.js`
- Covered areas: feed parsing and URL de-duplication, refresh lock and cooldown,
  filters/sort/pagination, weighted search relevance, bookmarks/read state/history,
  saved searches, CSV/XLSX/RSS/JSON exports, source health, SEO/sitemap/robots,
  service worker scope and offline page
- Browser-only checks (real install prompt, DevTools offline reload, update banner)
  are documented as manual steps in the UAT kit below

---

## User Acceptance Testing (UAT)

### Purpose and Scope

User Acceptance Testing for the Hermes AI News Aggregator (Django 5.0.14,
MySQL/MariaDB). The goal is to validate that the system meets its functional and
usability requirements from a participant's perspective. No PII is collected;
participant profiles use an anonymous signed-cookie `hermes_reader`.

### Schedule

- Pre-test: environment setup and participant onboarding
- Test window: 7 timed tasks plus a 7-item Likert survey
- Post-test: data extraction and moderator debrief

### Roles

- **Moderator** — runs the session, enforces moderation rules, records observations
- **Observer** — silent, records peripheral notes only
- **Participant** — uses the system under test, completes the profile form and tasks

### Ethics Note

- No PII is collected. Participant identity is an anonymous signed cookie `hermes_reader`.
- No LLM interactions during testing.
- The participant may withdraw at any time.

### Environment Checklist

1. Start XAMPP MySQL.
2. Start the server: `.\.venv\Scripts\python.exe manage.py runserver`
3. Verify these routes return 200:
   `/`, `/dashboard/`, `/news/`, `/news/a/<pk>/`, `/news/history/`, `/news/sources/`

### Participant Profile Form

| Field | Type |
| --- | --- |
| Course / Year | text |
| AI-news familiarity (1-5) | Likert |
| PWA familiarity (1-5) | Likert |

### Timed Tasks (7)

| # | Steps | Expected Result | Success Criteria |
| --- | --- | --- | --- |
| 1 | Install PWA: open `/news/`, use the Chrome install prompt / "Add to home screen" | PWA installed, app shell loads without browser UI | Install accepted; `/news/` reloads in standalone mode |
| 2 | Browse: land on `/`, navigate to `/news/`, observe the feed | Landing shows latest items; 24 configured feeds available | Feed loads with at least one article card |
| 3 | Search: enter a term in `/news/?q=` and watch autocomplete | Autocomplete returns at least one matching suggestion | Suggestion appears within 600 ms and matches the term |
| 4 | Filter: use source/topic/from/to/saved/unread filters | Results narrow to the selected source/topic/date range | Filter chips apply; item count drops accordingly |
| 5 | Save search: set filters, click "Save search", then restore it | Saved search persists and restores the same filters | Chip appears; restore yields the same results |
| 6 | Bookmark + mark read: open `/news/a/<pk>/`, bookmark, mark read | Article saved; history updates | Bookmark toggles; `/news/history/` reflects the change |
| 7 | Export: open `/news/export/csv/`, download and open the file | CSV downloads and opens; headers match model fields | File downloads; first row contains expected headers |

#### Optional Offline Check (Chrome DevTools)

- DevTools → Application → Service Workers → check **Offline**
- Reload `/news/`; verify cached content loads or the offline page appears

### Per-Task Record Row

`start URL, steps (comma-separated), expected result, success Y/N, time-on-task (seconds), observer notes`

### 7-Item 5-Point Likert Survey

1. Ease of search
2. Result relevance
3. Topic-label trust
4. Layout clarity
5. PWA install
6. Offline usefulness
7. Overall satisfaction

### Scoring

- **Task success rate** = (tasks succeeded / 7) × 100%
- **Mean time-on-task** = average across all 7 tasks
- **Mean Likert per item** = average rating per survey question across participants
- **Descriptive analysis** = frequency counts, median, range; report any item with SD > 1.5

### Moderation Rules

- No leading help unless the participant is stuck for more than 2 minutes; then
  prompt once and log the intervention
- Log every intervention with a timestamp and the participant's quote
- Stop the task on frustration (sighs, repeated "I can't", or a request to quit)
- Debrief immediately after stopping

The empty results template lives in `docs/UAT-RESULTS-TEMPLATE.md`
(no participant data has been collected).

---

## Documentation Index

| Document | Location |
| --- | --- |
| Concept paper (introduction, objectives, scope, evaluation plan) | this README |
| Technical overview, features, tech stack, setup, testing | this README |
| User Acceptance Testing kit | this README and `docs/UAT-KIT.md` |
| UAT results template (empty) | `docs/UAT-RESULTS-TEMPLATE.md` |
| Public feature roadmap and implementation log | `docs/IMPROVEMENT-PLAN.md` |
| Demo video | <https://laurmj4-eng.github.io/BSIT3A-DJANGO-Hermes-AI-Agent/evidence/hermes-ai-agent-demo-2026-10-30.mp4> |
