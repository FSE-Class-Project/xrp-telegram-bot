# Copilot instructions for xrp-telegram-bot

This repo is a two-part app: a FastAPI backend and a python-telegram-bot (PTB v20) client for XRP TestNet. Agents should keep both components and their contracts in sync.

## Architecture and data flow
- Backend (`backend/`)
  - API: FastAPI app in `backend/main.py`; routes in `backend/api/routes.py` under `/api/v1`.
  - Middleware: rate limiting via SlowAPI and idempotency header pass-through in `backend/api/middleware.py`.
  - XRP: XRPL integration in `backend/services/xrp_service.py` using xrpl-py 2.5.0 (Wallet.create, submit_and_wait).
  - DB: SQLAlchemy models in `backend/database/models.py`; engine/session in `backend/database/connection.py` with Alembic migrations auto-run on startup.
  - Caching: optional Redis wrapper in `backend/services/cache_service.py` (gracefully disabled if Redis unavailable).
- Bot (`bot/`)
  - Entry: `bot/main.py` (polling dev mode). Handlers in `bot/handlers/*`, keyboards in `bot/keyboards/menus.py`.
  - Uses HTML formatting consistently (ParseMode.HTML) and central formatting helpers.
- Deployment: On Render, backend sets Telegram webhook and serves `/webhook/{bot_token}` via `backend/api/webhook.py`.

## Conventions and patterns (repo-specific)
- Auth between bot and backend uses header `X-API-Key`; verify in `backend/api/auth.py`. Don’t call protected endpoints without it.
- Idempotency: pass `Idempotency-Key` on write operations (e.g., transaction send). Middleware stores on `request.state`; DB records in `IdempotencyRecord` via `backend/utils/idempotency.py`.
- Amounts: Pydantic/API models use `Decimal` with 6 dp; DB models store float; convert carefully at boundaries. Amount validation lives in `routes.py` (XRPConstants + validators).
- XRP address validation: simple regex (`^r[a-zA-Z0-9]{24,33}$`) plus service validation. Avoid self-transfers, enforce reserve amounts.
- Settings: Pydantic Settings in `backend/config.py` with environment-aware defaults. In dev, secrets are auto-generated; in prod, require explicit env vars.
- Bot state: conversation states `AMOUNT, ADDRESS, CONFIRM`; `context.user_data` holds transient tx data; `callback_query_handler` maintains a simple nav stack.
- Caching: use `get_cache_service()` and methods on `CacheService`; code should work with cache disabled (check `.enabled`).

## Critical workflows
- Local dev (starts API + bot with polling):
  - `python run.py` (or `python run.py backend` / `python run.py bot`). Requires `TELEGRAM_BOT_TOKEN` and will auto-init DB/migrations and generate `ENCRYPTION_KEY` if missing.
- Backend only (uvicorn): `backend/main.py` creates the app and sets CORS, rate limits, and routers. Health endpoints: `/` and `/health`, plus `/api/v1/health`.
- Tests: `python run.py test` or `pytest -v tests/`. Tests use in-memory SQLite and patch XRPL calls.
- Migrations: DB schema is initialized via Alembic on startup (`init_database`). For manual changes, prefer Alembic revisions in `alembic/versions`.

## Integration points and examples
- Bot → Backend registration (excerpt from `bot/handlers/start.py`):
  ```python
  headers = {"X-API-Key": context.bot_data["api_key"]}
  await client.post(f"{api}/api/v1/user/register", json=user_data, headers=headers)
  ```
- Bot → Backend send transaction (`bot/handlers/transaction.py`):
  ```python
  headers = {"X-API-Key": api_key, "Idempotency-Key": id_key}
  await client.post(f"{api}/api/v1/transaction/send", json=payload, headers=headers)
  ```
- Webhook mode (Render): backend sets `set_webhook` using `RENDER_EXTERNAL_URL`, and receives updates at `/webhook/{TELEGRAM_BOT_TOKEN}`. Local dev uses polling only.

## Version constraints and pitfalls
- Pinned deps: PTB 20.3 + xrpl-py 2.5.0 require httpx 0.24.x. Don’t bump httpx casually.
- Encryption: secrets use Fernet via `backend/utils/encryption.py`. In prod, set `ENCRYPTION_KEY`; dev may auto-generate.
- Decimal vs float across layers—preserve precision in validation and API types; cast only at the boundary to DB or JSON floats where needed.
- Reserve logic: respect XRP base reserve; avoid sending amounts that drop balance below reserve.

## File hotspots to learn first
- Backend: `backend/main.py`, `backend/api/routes.py`, `backend/services/{xrp_service,price_service,user_service}.py`, `backend/database/{models,connection}.py`.
- Bot: `bot/main.py`, `bot/handlers/{start,transaction,price,wallet}.py`, `bot/keyboards/menus.py`.

If anything above is unclear (e.g., migration flow or cache toggles), tell us what you’re trying to change so we can add precise examples.
