# UAT Kit — Hermes AI News Aggregator

## Purpose & Scope
User Acceptance Testing for the Hermes AI News Aggregator (Django 5.0.14, MySQL/MariaDB). Validate that the system meets functional and usability requirements from a participant perspective. No PII is collected; participant profiles use anonymous signed-cookie `hermes_reader`.

## Schedule
- Pre‑test: environment setup, participant onboarding
- Test window: 7 timed tasks + 7‑item Likert survey
- Post‑test: data extraction, moderator debrief

## Roles
- **Moderator** — orchestrates session, enforces moderation rules, records observations
- **Observer** — silent, records peripheral notes only
- **Participant** — runs the system under test, completes profile form and tasks

## Ethics Note
- No PII collected. Participant identity is an anonymous signed cookie `hermes_reader`.
- No LLM interactions during testing.
- Participant may withdraw at any time.

## Environment Checklist
1. Start XAMPP MySQL.
2. Activate venv: `.\.venv\Scripts\python.exe manage.py runserver`
3. Verify these routes return 200:
   - `/`
   - `/dashboard/`
   - `/news/`
   - `/news/a/<pk>/`
   - `/news/history/`
   - `/news/sources/`

## Participant Profile Form
| Field | Type |
|---|---|
| Course / Year | text |
| AI‑news familiarity (1‑5) | Likert |
| PWA familiarity (1‑5) | Likert |

## Timed Tasks (7)

| # | Steps | Expected Result | Success Criteria |
|---|---|---|---|
| 1 | Install PWA: open `/news/`, click "Add to home screen" / use Chrome "Install" prompt. | PWA installed, app shell loads without browser UI. | Install banner accepted; `/news/` re‑loads in standalone mode. |
| 2 | Browse: land on `/`, navigate to `/news/`, observe feed. | Landing page shows latest feed items; 24 configured feeds visible. | Feed loads; at least one article card visible. |
| 3 | Search: enter term in `/news/?q=`, observe autocomplete suggestion at `/news/api/suggest/`. | Autocomplete drops list with at least one matching term. | Suggestion appears within 600 ms; matches typed term. |
| 4 | Filter: use source/topic/from/to/saved/unread filters on `/news/`. | Results narrow by selected source/topic/date range. | Filter chips apply; item count drops accordingly. |
| 5 | Save search: enter filter combo, click "Save search". Restore from saved list. | Saved search persists; restore re‑applies same filters. | Saved search appears in user list; restore yields same results. |
| 6 | Bookmark + mark read: open `/news/a/<pk>/`, bookmark article, mark read. | Article saved to reading list; history updates. | Bookmark icon toggles; mark‑read updates status; `/news/history/` reflects change. |
| 7 | Export: go to `/news/export/csv/`, download CSV; open in spreadsheet. | CSV file downloads and opens; column headers match model fields. | File downloads; first row contains expected headers (title, source, date). |

### Optional Offline Check (Chrome DevTools)
- Open DevTools → Application → Service Workers → "Offline".
- Reload `/news/`; verify cached content loads or graceful fallback.

## Per‑Task Record Row
`start URL, steps (comma‑separated), expected result, success Y/N, time-on-task (seconds), observer notes`

## 7‑Item 5‑Point Likert Survey
1. Ease of search
2. Result relevance
3. Topic‑label trust
4. Layout clarity
5. PWA install
6. Offline usefulness
7. Overall satisfaction

## Scoring
- **Task success rate** = (tasks succeeded / 7) × 100%
- **Mean time‑on‑task** = average across all 7 tasks
- **Mean Likert per item** = average rating per survey question across participants
- **Descriptive analysis** = frequency counts, median, range; report any item with SD > 1.5

## Moderation Rules
- No leading help unless participant is stuck > 2 min; then prompt once, log intervention.
- Log every intervention with timestamp and participant quote.
- Stop task on frustration (sighs, repeated "I can't", or request to quit).
- Debrief immediately after stop.