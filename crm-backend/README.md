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

# optional: copy env template
copy .env.example .env

# migrate + seed
alembic upgrade head
python scripts/seed.py

# run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Default admin: `admin` / `admin123`

OpenAPI: http://127.0.0.1:8000/docs

## Required config (non-debug / production)

| Variable | Meaning |
|----------|---------|
| `DEBUG` | Must be `false` in production |
| `JWT_SECRET` | Strong secret (≥32 chars); weak default `dev-secret-change-me` is **rejected** when `DEBUG=false` |
| `CORS_ORIGINS` | Comma-separated frontend origins whitelist (no `*`) |

See `.env.example`.

## MVP APIs

Auth, departments/users/roles, leads (import/assign/claim/convert), accounts/contacts, activities/timeline/attachments, opportunities/pipelines, pool rules & quotas, sales targets & dashboards, dicts/custom fields/layouts, approvals/todos/notifications, audit logs.

### Help / 系统使用说明书（CYGN-4）

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/help/manual` | Bearer login | Full Markdown body + TOC |
| GET | `/api/v1/help/manual/meta` | Bearer login | Title / version / TOC only |

- Content file: `content/user_manual.md`（替换后按文件 mtime 刷新进程内缓存；`version` 常量需人工递增）
- Response fields: `title`, `version`, `format` (`markdown`), `updatedAt`, `toc[]` (`level`/`id`/`title`), and `content` on the full endpoint
- **Frontend contract (CYGN-5)**：渲染 Markdown 标题锚点时必须使用接口返回的 `toc[].id`，不要用渲染器默认 slugger
- Errors: `401 UNAUTHORIZED`, `404 NOT_FOUND`

```bash
PYTHONPATH=. pytest tests/test_help_manual.py -q
```

Phase-2 tables (contract/ticket/campaign) are migrated as schema skeletons.
