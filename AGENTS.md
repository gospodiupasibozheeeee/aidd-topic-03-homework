# Repository Guidelines

## Project Structure & Module Organization

This investing demo uses Django 4.1, Django REST Framework, PostgreSQL, Redis, Celery, Plotly, and the Tinkoff Invest API.

- `config/`: Django settings, root URLs, ASGI/WSGI entry points, and Celery configuration.
- `dashboard/`: share models, forms, views, background tasks, and migrations. `api/v1/` implements the REST API; `services/` handles market data and charts; `management/commands/add_shares.py` imports shares.
- `user/`: authentication views, forms, and templates using Django's built-in user model.
- Each app keeps templates and static assets under its own namespaced directories.
- `dashboard/tests.py`: existing API and HTML tests. `HOMEWORK.md` defines assignment requirements.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- `docker compose up -d`: start PostgreSQL and Redis.
- `python manage.py migrate`: apply database migrations.
- `python manage.py runserver`: start the local development server.
- `python manage.py add_shares`: import shares; requires a valid Tinkoff token.
- `celery -A config worker -l info` and `celery -A config beat`: run background processing and scheduling in separate terminals.
- `python manage.py test`: run all tests; append `dashboard` to limit discovery.
- `black .` and `isort .`: format Python and sort imports using the tools pinned in `requirements.txt`.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for functions and variables, and `PascalCase` for classes. Follow existing Django app boundaries; keep external market-data calls in `dashboard/services/`. Generate model migrations with `python manage.py makemigrations` and commit them alongside model changes. Preserve namespaced template and static paths.

## Testing Guidelines

Use Django's test runner and DRF's `APITestCase`, following `dashboard/tests.py`. Name methods `test_<behavior>`. Cover successful requests, validation failures, and missing records; mock external API calls. Tests need PostgreSQL access and permission to create a test database. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Existing commits use short imperative subjects, such as `Add homework assignment`. Keep commits focused. Describe behavior changes, validation commands and results, linked issues when applicable, and migration or configuration needs in PRs. Include screenshots for UI changes.

## Configuration & Assignment Workflow

Configure the empty `SECRET_KEY` and, for market-data operations, `TINKOFF_TOKEN` in `config/settings.py` locally; never commit credentials. Settings do not currently load `.env` automatically. Follow `HOMEWORK.md`: use an independent branch and project copy for each agent, preserve existing functionality, and distinguish defect fixes from new features.
