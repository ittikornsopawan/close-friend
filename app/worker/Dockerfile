# Build context is the repo root (uv workspace root), not app/worker — see docker-compose.yml.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/shared packages/shared
COPY app/worker app/worker
COPY app/api/pyproject.toml app/api/pyproject.toml

RUN uv sync --frozen --package close-friend-worker

CMD ["uv", "run", "--package", "close-friend-worker", "celery", "-A", "close_friend_worker.celery_app", "worker", "--loglevel=info"]
