# CRM Backend

Python FastAPI + SQLAlchemy 2 + Alembic + SQLite CRM API, aligned with `docs/design.md`.

## Stack

- FastAPI REST (`/api/v1`)
- SQLAlchemy 2.x models + Alembic migrations
- SQLite (WAL)
- JWT Bearer auth, RBAC, data scope
- APScheduler in-process pool recycle (no Redis)

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

# migrate + seed
alembic upgrade head
python scripts/seed.py

# run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Default admin: `admin` / `admin123`

OpenAPI: http://127.0.0.1:8000/docs

## MVP APIs

Auth, departments/users/roles, leads (import/assign/claim/convert), accounts/contacts, activities/timeline/attachments, opportunities/pipelines, pool rules & quotas, sales targets & dashboards, dicts/custom fields/layouts, approvals/todos/notifications, audit logs.

Phase-2 tables (contract/ticket/campaign) are migrated as schema skeletons.
