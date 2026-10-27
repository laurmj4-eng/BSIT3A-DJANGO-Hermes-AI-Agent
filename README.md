# Hermes AI Agent

**An AI News Intelligence System**

> BSIT 3A — Django Project

A web-based AI news aggregation system that gathers artificial intelligence
headlines from multiple trusted sources into a single, searchable intelligence
feed. Built with Django 5 and MySQL.

---

## Group Members

| Name |
| --- |
| MJ Laurito |
| JM Advincula |
| Inbanez Alfon Franc |

---

10/7/2026 100 Points

## About the System

Hermes AI Agent pulls live news from several public RSS/Atom feeds and presents
them in one clean dashboard. Instead of opening ten different tabs to keep up
with the AI industry, users get a single feed they can search, filter, and
save stories from.

The system ships with:

- **Live feed aggregation** from 5 sources — Google News (AI), TechCrunch AI,
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
- Aggregates 5 public RSS/Atom feeds
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

---

## Project Structure

```
BSIT3A-DJANGO-Hermes-AI-Agent/
├── manage.py
├── requirements.txt
├── mysite/                 # project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── error_views.py
│   └── wsgi.py
├── apps/
│   ├── core/               # public dashboard
│   ├── users/              # legacy CRUD app (installed, not routed)
│   ├── info/               # legacy CRUD app (installed, not routed)
│   └── news/               # AI news aggregator
│       ├── feeds.py        # RSS/Atom fetching & normalisation
│       ├── classification.py
│       ├── services.py     # refresh locking and run tracking
│       ├── health.py       # source health views
│       ├── exporters.py    # CSV/XLSX
│       ├── models.py       # Article, Topic, RefreshRun
│       ├── views.py        # feed, refresh, bookmark, API views
│       └── migrations/
├── templates/
│   ├── news/               # feed, source health, offline
│   ├── theme/              # base layout, topbar, footer, settings
│   ├── errors/             # custom 404/500
│   └── home.html           # dashboard
├── static/
│   ├── css/                # Tabler + custom design system
│   ├── js/                 # feed, dashboard, PWA, theme scripts
│   ├── icons/              # app icons
│   ├── manifest.webmanifest
│   └── sw.js
└── sql/                    # optional database dump and import guide
```

---

## Getting Started

### Requirements
- Python 3.12+
- MySQL or MariaDB running on `localhost:3306`

### 1. Clone the repository

```bash
git clone https://github.com/laurmj4-eng/BSIT3A-DJANGO-Hermes-AI-Agent.git
cd BSIT3A-DJANGO-Hermes-AI-Agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the database

```bash
mysql -u root -e "CREATE DATABASE bsitcrud CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
```

Optionally import the included dump instead:

```bash
mysql -u root bsitcrud < sql/bsitcrud.sql
```

### 5. Configure the database connection

The defaults match a local XAMPP MySQL install. Override them with environment
variables when needed:

| Variable | Default |
| --- | --- |
| `DB_NAME` | `bsitcrud` |
| `DB_USER` | `root` |
| `DB_PASSWORD` | empty |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `3306` |

`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS` are also read
from the environment. Set `DJANGO_DEBUG=0` for production; that enables HTTPS
redirects, secure session/CSRF cookies, and HSTS. Tune it with
`DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`,
`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`, and `DJANGO_SECURE_HSTS_PRELOAD` when
running behind a proxy.

### 6. Apply migrations

```bash
python manage.py migrate
```

### 7. Run the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> — the dashboard is public, no sign-in needed.

### 8. Load the news

Go to **AI News** in the top navigation and click **Refresh feeds**. The first
run pulls the latest articles from all configured sources.

### 8b. Keep the news fresh automatically (Windows)

`scripts/refresh_news.cmd` runs one refresh in a console;
`scripts/refresh_news_silent.py` is the no-window variant. Register an hourly
Task Scheduler job:

```powershell
schtasks /Create /TN "Hermes News Refresh" /SC HOURLY /MO 1 /TR "\"C:\path\to\project\.venv\Scripts\pythonw.exe\" \"C:\path\to\project\scripts\refresh_news_silent.py\"" /F
```

Output is appended to `%TEMP%\hermes-refresh.log`.

### 9. Run the test suite

```bash
python manage.py test
```

---

## Usage

| Page | Path | Access |
| --- | --- | --- |
| Dashboard | `/` | Public |
| AI News | `/news/` | Public |
| Articles API | `/news/api/articles/` | Public |
| RSS | `/news/rss/` | Public |
| CSV / XLSX export | `/news/export/csv/`, `/news/export/xlsx/` | Public |

---

## Notes

- Refresh is on demand rather than scheduled, so the system never hammers a
  public feed without being asked.
- Successful and partial refreshes have a 60-second cooldown; a refresh that is
  already running returns `409`, and a cooldown response returns `429` with a
  `Retry-After` header.
- VentureBeat rate-limits aggressively (HTTP 429). When this happens the
  refresh reports a **partial success** listing the failed source rather than
  failing outright.
- Feed sources are configured in `apps/news/feeds.py`.
- The service worker caches static assets and an offline page; bump the cache
  version in `static/sw.js` after changing static files.
- `manage.py check --deploy` still warns about the development secret key and
  the optional HSTS subdomain/preload flags. Set `DJANGO_SECRET_KEY` to a long
  random value and enable those HSTS flags before deployment; `DEBUG=0` enables
  the HTTPS, HSTS, and secure-cookie defaults.

---

## License

Developed for academic purposes as part of the BSIT 3A curriculum.
