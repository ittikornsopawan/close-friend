# close-friend

Monorepo with three apps:

- `app/web` — Next.js (TypeScript) frontend
- `app/api` — FastAPI backend
- `app/worker` — Celery background worker
- `packages/shared` — Python schemas shared by `app/api` and `app/worker`

## Setup

```bash
npm install          # installs app/web
uv sync --all-packages   # installs app/api, app/worker, packages/shared
docker compose up -d # starts postgres + redis
```

## Running

```bash
npm run dev --workspace app/web                              # http://localhost:3000
uv run --package close-friend-api uvicorn close_friend_api.main:app --reload  # http://localhost:8000
uv run --package close-friend-worker celery -A close_friend_worker.celery_app worker --loglevel=info
```
