# HERMES AI AGENT

### A Web-Based AI News Aggregation and Intelligence System

**BSIT Capstone Project Concept Paper**

> BSIT 3A — Django Project

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
  saved/unread state, with search suggestions
- **Bookmarking and read tracking** stored per browser session
- **Source health dashboard** for feed status, article totals, and refresh runs
- **Exports and integrations** via CSV, XLSX, RSS, and a JSON articles API
- **Dashboard analytics** for article counts, trending stories, topic mix, and
  source breakdown
- **Installable PWA** with an offline fallback and theme settings

---

## Features

### AI News Feed
- Aggregates 20+ public RSS/Atom feeds
- Search by headline, summary, or source with autocomplete suggestions
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
- Bookmarks are stored per browser session (no account needed)
- No admin panel or sign-in surface is exposed

### Security
- Public read-only pages — no login required
- No admin panel or sign-in surface is exposed
- Refresh cooldown — successful/partial refreshes are throttled to once every
  60 seconds; a running refresh returns `409`
- CSRF protection on all state-changing requests, including session-based
  bookmark and read actions
- Session-based bookmarks and read state, no account data collected

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

> The feed reader deliberately uses **no third-party parsing library** — only
> `urllib.request` and `xml.etree.ElementTree` from the standard library — and
> the XLSX exporter writes OpenXML directly, keeping the runtime dependencies
> to Django and the MySQL driver.
