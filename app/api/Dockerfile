# Build context is the repo root (uv workspace root), not app/api — see docker-compose.yml.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/shared packages/shared
COPY app/api app/api
COPY app/worker/pyproject.toml app/worker/pyproject.toml

RUN uv sync --frozen --package close-friend-api

EXPOSE 8000
CMD ["uv", "run", "--package", "close-friend-api", "uvicorn", "close_friend_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
