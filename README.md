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
- **Search and filtering** across headlines, summaries, and sources
- **Bookmarking** to save articles for later
- **Dashboard analytics** — article counts, saved totals, and a per-source
  breakdown

---

## Features

### AI News Feed
- Aggregates 5 public RSS/Atom feeds
- Search by headline, summary, or source
- Filter by a specific source
- Paginated results
- One-click bookmark / un-bookmark
- Manual refresh with live status reporting

### Dashboard
- Cached article count and active source count
- Saved-article total
- User and Info record totals
- Latest 6 headlines
- Per-source article breakdown with progress bars

### User Management
- Superuser-only CRUD for user accounts
- Create, edit, and delete users from the interface
- Search and pagination

### Security
- Login required for every page
- Superuser gate on user management
- Rate limiting — locks an account out for 1 minute after 5 failed attempts
- CSRF protection on all state-changing requests
- Password strength validation on registration

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Framework | Django 5.0.14 |
| Database | MySQL / MariaDB (`bsitcrud`) |
| Frontend | Tabler UI, Bootstrap 5.3.7, Font Awesome 6.5.1 |
| Feed parsing | Python standard library only (`urllib` + `xml.etree`) |
| Excel export | openpyxl 3.1.5 |

> The feed reader deliberately uses **no third-party parsing library** — only
> `urllib.request` and `xml.etree.ElementTree` from the standard library — so
> the project keeps a minimal dependency footprint.

---

## Project Structure

```
mj_django/
├── manage.py
├── requirements.txt
├── pytest.ini
├── bsitcrud.sql            # database dump
├── mysite/                 # project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   └── wsgi.py
├── apps/
│   ├── core/               # authentication & dashboard
│   ├── users/              # user management CRUD
│   ├── info/               # personal information CRUD
│   └── news/               # AI news aggregator
│       ├── feeds.py        # RSS/Atom fetching & normalisation
│       ├── models.py       # Article model
│       ├── views.py        # feed, refresh, bookmark views
│       └── migrations/
├── templates/
│   ├── auth/               # login & registration
│   ├── news/               # news feed page
│   ├── theme/              # base layout, sidebar, footer
│   ├── users/              # user list
│   ├── info.html
│   └── home.html           # dashboard
└── static/
    ├── css/app-theme.css   # custom design system
    ├── js/
    └── libs/
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
mysql -u root bsitcrud < bsitcrud.sql
```

### 5. Configure the database connection

Edit `mysite/settings.py` to match your local MySQL credentials:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bsitcrud',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### 6. Apply migrations

```bash
python manage.py migrate
```

### 7. Create an administrator account

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and sign in.

### 9. Load the news

Go to **AI News** in the sidebar and click **Refresh feeds**. The first run
will pull around 95 articles from the configured sources.

---

## Usage

| Page | Path | Access |
| --- | --- | --- |
| Login | `/` | Public |
| Register | `/register/` | Public |
| Dashboard | `/home/` | Logged in |
| AI News | `/news/` | Logged in |
| Info | `/info/` | Logged in |
| Users | `/users/` | Superuser only |
| Admin | `/admin/` | Superuser only |

---

## Notes

- Refresh is on demand rather than scheduled, so the system never hammers a
  public feed without being asked.
- VentureBeat rate-limits aggressively (HTTP 429). When this happens the
  refresh reports a **partial success** listing the failed source rather than
  failing outright.
- Feed sources are configured in `apps/news/feeds.py`.

---

## License

Developed for academic purposes as part of the BSIT 3A curriculum.
