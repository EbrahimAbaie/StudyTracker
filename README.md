# StudyTracker

Offline personal study progress tracker and forecaster for the Iranian Computer Engineering master's entrance exam.

StudyTracker records actual study and practice activity. It does not create study plans, recommend subjects, schedule your day, or use AI. You decide what to study; the application shows progress, remaining workload, capacity, and a forecast based on recorded activity.

## Features

- Persian, RTL, responsive dark interface
- Subject and resource management with numeric display priorities
- Study sessions linked to resources
- Practice statistics for correct, wrong, and unanswered questions
- Manual resource completion while preserving the original estimate
- Jalali dates with Persian, Arabic, and Latin digit support
- Remaining exam days and workload-versus-capacity comparison
- Forecasts based on up to 28 days of real activity
- Filterable, paginated activity history
- SQLite WAL mode with safe live backups
- Local-only static assets and fonts; no runtime external requests

## Requirements

- Python 3.13
- Docker and Docker Compose (recommended)

The project uses Django 6.1, SQLite, Gunicorn, WhiteNoise, jdatetime, Django templates, plain CSS, and plain JavaScript. It does not use React, REST frameworks, Node.js, PostgreSQL, Redis, Celery, external APIs, CDNs, analytics, telemetry, or AI APIs.

## Run with Docker

```bash
docker compose up -d --build
```

Open <http://127.0.0.1:8000>.

Only the `web` service is created, the port is bound to localhost, and Gunicorn runs with one worker. Create an optional Django admin account with:

```bash
docker compose exec --user appuser web python manage.py createsuperuser
```

The main application does not require login. Django Admin is available at `/admin/`.

## Run without Docker

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 127.0.0.1:8000
```

## Data and configuration

The SQLite database is stored at `./data/db.sqlite3` on the host and `/app/data/db.sqlite3` in Docker. `docker compose down` does not remove this persistent data; deleting `data/` manually deletes the database, generated secret key, and backups.

On the first run, enter the exam title, Jalali exam date, and weekly available minutes in Settings, then add subjects and resources. Demo data is never created automatically.

The default timezone is `Asia/Tehran` and can be overridden with `TIME_ZONE`. Set `SECRET_KEY` through the environment or a `.env` file. If it is not supplied in Docker, the entrypoint creates and stores a random key in `data/.secret-key`.

Subjects and resources are displayed by ascending priority: `1`, `2`, `3`, and so on. Priority `1` appears first; larger numbers appear later. Equal priorities use the name or title as the tie-breaker.

## Backup and restore

```bash
docker compose exec web python manage.py backup_db
```

Backups are written to `./data/backups/`. The command uses SQLite's backup API, checks `PRAGMA integrity_check`, and only keeps the final file after a successful backup.

To restore a backup, create a backup of the current database, stop the application with `docker compose down`, verify the selected file with `PRAGMA integrity_check;`, move any existing `db.sqlite3-wal` and `db.sqlite3-shm` files aside, replace `data/db.sqlite3`, and start with `docker compose up -d`.

## Management commands

```bash
python manage.py seed_demo       # optional, idempotent demo data
python manage.py backup_db       # integrity-checked SQLite backup
python manage.py verify_storage  # verify WAL, sync mode, and timeout
```

## Verification

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
python manage.py verify_storage
```

The test suite covers models, forms, Jalali dates, digit normalization, progress calculations, manual completion, forecasting edge cases, CRUD routes, CSRF, history filtering, escaping, query bounds, SQLite WAL, persistence, and backup integrity. `/health/` returns plain-text `OK` with status `200`.

## Project structure

```text
config/                 Django settings, URLs, and WSGI
tracker/models.py       Database models and invariants
tracker/forms.py        Input parsing and validation
tracker/calculations.py Pure deterministic calculations
tracker/selectors.py    Read queries and aggregations
tracker/services.py     Write operations and backups
tracker/views.py        Request/response orchestration
tracker/management/     backup_db, seed_demo, verify_storage
tracker/tests/          Automated tests
templates/              Django templates
static/                 Local CSS, JavaScript, icons, and fonts
data/                   Persistent database and backups
```

Vazirmatn font files are bundled locally under `static/fonts/vazirmatn/`; no font or asset is downloaded at runtime.

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0).

You may use, modify, and distribute this software for noncommercial purposes, subject to the terms of the license. Commercial use requires separate permission from the copyright holder.
