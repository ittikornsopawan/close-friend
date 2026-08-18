# Build context is the repo root (uv workspace root), not packages/shared —
# see docker-compose.yml. One-shot migrate+seed image: asking app/api's or
# app/worker's already-built image to `uv run --package close-friend-shared`
# at runtime risks a network re-resolution, since that package wasn't the
# one synced at their build time — this purpose-built image avoids that.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/shared packages/shared
COPY app/api/pyproject.toml app/api/pyproject.toml
COPY app/worker/pyproject.toml app/worker/pyproject.toml

RUN uv sync --frozen --package close-friend-shared

WORKDIR /workspace/packages/shared
CMD ["sh", "-c", "uv run --package close-friend-shared alembic -c alembic.ini upgrade head && uv run --package close-friend-shared python -m close_friend_shared.db.seed"]
