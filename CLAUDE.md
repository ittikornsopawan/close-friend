# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Close Friend is a chatbot platform where an LLM responds through configurable **personas** — each persona defines the AI's character, response style, and emotional expression (e.g. can be provoked into anger, can be flirted with into acting smitten, can warm up into a close/familiar tone over a conversation). The AI must track conversational history within a persona and stay emotionally consistent with it — e.g. if the user insulted it earlier, a later compliment should still be colored by that earlier insult, per the persona's defined reaction style.

The project also includes a **research** subsystem that gathers information either scoped to a persona or as general-purpose AI research, and feeds the results into RAG/CAG/MAG pipelines. The goal is to study, through real research, how to build rapport with a given type of person/character.

## Tech Stack

- Web App — Next.js (TypeScript)
- Web API — Python, FastAPI
- Worker — Python, Celery (queue/dispatch, broker below) + LangGraph (agent workflow logic, invoked from within Celery tasks)
- LLM runtime — **Ollama, running locally**; all persona inference targets a local Ollama instance rather than a hosted API. Only `app/worker` calls it (see `## Data Flow`) — reachable at `CF_WORKER_OLLAMA_BASE_URL` (`http://localhost:11434` outside Docker, `http://ollama:11434` inside `docker compose`)
- Default model — `qwen2.5:7b-instruct-q4_K_M` (~4.7GB resident). Picked to run comfortably on a 16GB MacBook with headroom left over for macOS/Docker/the rest of the stack, and for materially better Thai/multilingual handling than same-size Llama models, which matters for persona conversations. Swap the tag in `## Commands` and wherever a graph references it if a different model is needed later; don't reach for anything above ~8B on a 16GB machine.
- Database — PostgreSQL
- Queue / Cache — Redis
- Orchestration — Docker Compose (`docker-compose.yml` at repo root runs the full stack: `postgres`, `redis`, `ollama`, `api`, `worker`, `web`)
- Architecture — Clean Architecture, Vertical Slice

LangGraph is not yet a dependency of `app/worker` — add it to `app/worker/pyproject.toml` when the first graph is implemented. See `## Conventions` for how it's expected to plug into the existing Celery task structure and call Ollama instead of a hosted LLM API.

## Data Flow

```text
web -> api -> redis <- worker[N] -> ollama
```

- `app/web` only ever talks to `app/api` (HTTP). It never calls Redis, Ollama, or a worker directly.
- `app/api` is a **producer only**: it enqueues a task onto Redis and returns — it does not call Ollama and does not run persona/LLM logic itself.
- `app/worker` is the **consumer**, and is meant to run as N horizontally-scaled instances pulling off the same Redis queue (`docker compose up -d --scale worker=N`). Each worker instance is the only thing that calls Ollama, and is where the `## Persona Response Loop` and LangGraph graph execution live.
- Because inference only happens in workers, the persona pipeline's latency and throughput scale with worker count, not API instance count — scale `worker`, not `api`, to handle more concurrent conversations.

**Implemented today** (no persona, no LangGraph — see `## Persona Response Loop`): `POST/GET /conversations/{conversation_id}/messages` in `app/api/src/close_friend_api/routers/conversations.py`, `close_friend_worker.respond_to_message` Celery task in `app/worker/src/close_friend_worker/tasks.py` (logic in `chat.py`), calling Ollama directly with a generic system prompt. Messages live in Redis, not Postgres — see `## Current Structure` for the key schema.

## Architecture Layers

`app/api` and `app/worker` are meant to follow Clean Architecture organized as vertical slices (one folder per feature/use case, each with its own layers) rather than horizontal layers shared across the whole app:

- **Domain** — entities and business rules, no framework imports.
- **Application** — use cases/services that orchestrate domain logic; depends only on Domain.
- **Infrastructure** — DB (PostgreSQL), Redis, LangGraph, and other external I/O; implements interfaces defined by Application.
- **Presentation** — FastAPI routers in `app/api`, Celery task entrypoints in `app/worker`; depends on Application, never the other way around.

This is the target layering — it has not been applied to the codebase yet. `app/api` and `app/worker` currently use the flat `src/<package>/` layout described in `## Current Structure` below. When adding a non-trivial feature, prefer setting up its slice (`domain/`, `application/`, `infrastructure/` under a feature folder) rather than extending the flat `routers/` structure indefinitely.

## Persona Response Loop

The target per-message loop, meant to run as a LangGraph graph inside a Celery task (see `## Conventions`):

1. **Chat** — user message arrives.
2. **Assess** — LLM evaluates how it should respond.
3. **Summarize context** — summarize the current state of the conversation/situation.
4. **Persona feeling + response plan** — given the persona's definition, decide how the persona should feel right now and how it should respond.
5. **Respond from feeling** — LLM drafts the reply informed by the feeling from step 4.
6. **Persist state** — save the response and resulting feeling/context back to persona memory, so a later turn (e.g. a compliment after an earlier insult) is colored by it.
7. **Reply** — send the message back to the user.

Not a fixed contract — steps may be merged or reordered per persona or for performance (e.g. collapsing steps 2–4 into a single LLM call) as the implementation matures. **Not yet implemented** — what exists today (`app/worker/src/close_friend_worker/chat.py`) is a deliberately simpler MVP: one direct Ollama call with a generic "helpful, friendly assistant" system prompt, no persona, no emotion/feeling step, no LangGraph. It's the plumbing (`web → api → redis → worker → ollama`) proven end-to-end, not this loop.

## Persona Schema

Conceptual shape of a persona definition (target — no concrete model/table yet):

- `id`, `name` — identity.
- `character` — personality description, backstory, tone/speech style.
- `emotion_rules` — trigger → reaction mapping (e.g. insult → anger, flirtation → smitten), including how intensity builds and decays over turns.
- `relationship_stages` — thresholds/criteria for progressing stranger → familiar → close, and how tone/behavior shifts at each stage.
- `boundaries` — hard constraints the persona won't cross regardless of emotional state or how the user provokes it.
- `research_scope` — what topics/sources this persona's research subsystem may pull from (persona-specific research vs. general research, per `## Project Overview`).
- `baseline_state` — default feeling and relationship stage for a new conversation.

## Memory Structure

Layered memory backing the response loop above — step 6 writes here, steps 3–4 read from it:

- **Working memory** — current conversation's raw turns plus the running context summary from step 3; scoped to the active session.
- **Emotional state** — current feeling(s) toward the user, intensity, and what caused it; updated at step 6, read at steps 4–5.
- **Episodic memory** — significant events tied to a turn reference (e.g. "user insulted me at turn 12"), so a later turn can be colored by an earlier one.
- **Relationship memory** — persists across sessions: relationship stage, known facts about the user, running rapport signal.
- **Research memory (RAG/CAG/MAG)** — retrieval store for persona-specific or general research results feeding the response loop's context step; kept separate from the memories above since it's knowledge-oriented rather than relationship-oriented.

Likely storage split: PostgreSQL for relationship/episodic memory (structured, queryable), Redis for working memory/session state (fast, ephemeral), and a vector store for research memory retrieval — probably `pgvector` on the existing PostgreSQL instance rather than a fourth datastore, but not yet decided. Not yet implemented.

## Current Structure

Polyglot monorepo with three apps sharing one Python dependency graph:

- `app/web` — Next.js 16 (App Router, TypeScript, Tailwind v4, Turbopack). npm workspace member declared at the root `package.json`. Messenger-style chat UI: `src/components/chat/` (`ChatApp` owns selected-contact state, `Sidebar`/`ContactListItem`, `ChatWindow`/`MessageList`/`MessageBubble`/`MessageInput`), `src/lib/contacts.ts` (hardcoded `Contact[]`, `id` doubles as `conversation_id`), `src/lib/api-client.ts` (typed fetch wrapper, reads `NEXT_PUBLIC_API_URL`), `src/hooks/useConversation.ts` (polls `GET .../messages` every 1s, up to 60 attempts, after sending).
- `app/api` — FastAPI HTTP service. Package `close_friend_api`, entrypoint `close_friend_api.main:app`. Routes: `health.py` (`/healthz`), `conversations.py` (`POST`/`GET /conversations/{conversation_id}/messages`). `celery_client.py` holds a broker-only Celery producer (`send_task(...)`) — it does not import `app/worker`. `redis_client.py` is a plain `redis.Redis` instance.
- `app/worker` — Celery worker consuming a Redis-backed queue. Package `close_friend_worker`, Celery app at `close_friend_worker.celery_app:celery_app`, tasks in `close_friend_worker/tasks.py`. `chat.py` holds the actual message-answering logic (`respond_to_message`, `build_ollama_history`, `call_ollama`) as plain functions the Celery task delegates to, kept separate so they're unit-testable without Celery/a broker.
- `packages/shared` — Python package `close_friend_shared`: Pydantic schemas (`TaskMessage`, `JobStatus`, `ChatMessage`, `MessageRole`, `MessageStatus`) and `conversation_messages_key(conversation_id)` — the Redis key-naming function — shared between `app/api` and `app/worker` so both sides agree on queue message shapes and Redis keys without duplicating either.

**Redis message schema**: one list per conversation, `cf:conv:{conversation_id}:messages` (via `conversation_messages_key`), `RPUSH`-only, each element a JSON-encoded `ChatMessage` (`id`, `role`, `content`, `status`: `pending`/`complete`/`failed`, `created_at`). No TTL. `app/api` appends a `complete` user message + `pending` assistant placeholder and enqueues the task; `app/worker` re-reads the whole list, builds Ollama's history from `complete` messages, then `LSET`s the placeholder in place to `complete` (with the reply) or `failed` (with a generic error message, on any Ollama/connection exception — never left `pending` forever).

`app/api`, `app/worker`, and `packages/shared` are members of a single **uv workspace** rooted at the top-level `pyproject.toml` (`[tool.uv.workspace]`, `package = false` — the root itself is virtual, not an installable package). They share one `.venv` at the repo root. `app/api` and `app/worker` depend on `close-friend-shared` via `[tool.uv.sources]` workspace references, not a published package — edit `packages/shared` and both consumers see it immediately, no reinstall needed.

`app/web` is a separate **npm workspace** (root `package.json`) since it doesn't share code with the Python apps.

All three apps plus infra are orchestrated by the root `docker-compose.yml`: `postgres`, `redis`, `ollama` (local LLM runtime), and build services `api` (`app/api/Dockerfile`), `worker` (`app/worker/Dockerfile`), `web` (`app/web/Dockerfile`). Each app's Dockerfile builds from the **repo root as context** (not its own subfolder), since `api`/`worker` need `packages/shared` and the root `uv.lock`, and `web` needs the root `package.json`/`package-lock.json` for the npm workspace — always pass `context: .` with a `dockerfile:` path when adding a service, never build from inside `app/*`.

## Commands

Run from the repo root unless noted.

### Setup

```bash
npm install                 # app/web deps
uv sync --all-packages      # app/api, app/worker, packages/shared deps into one .venv
docker compose up -d postgres redis ollama   # infra only, for running app code on the host
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M   # the ollama image starts empty
```

### Dev servers

Host processes, against the infra containers above:

```bash
npm run dev --workspace app/web
uv run --package close-friend-api uvicorn close_friend_api.main:app --reload
uv run --package close-friend-worker celery -A close_friend_worker.celery_app worker --loglevel=info
```

Or the whole stack containerized (rebuilds `api`/`worker`/`web` images on code changes — slower iteration than the host processes above, but closer to prod):

```bash
docker compose up -d --build
```

### Lint / build

```bash
npm run lint --workspace app/web
npm run build --workspace app/web
uv run ruff check .         # lints app/api, app/worker, packages/shared together
```

### Tests

```bash
uv run --package close-friend-api pytest app/api/tests
uv run --package close-friend-worker pytest app/worker/tests

# single test
uv run --package close-friend-api pytest app/api/tests/test_health.py::test_healthz -q
```

There is no test suite in `app/web` yet.

## Workflow

Every task follows this sequence:

1. Create a new branch off `main` before starting work — never commit directly to `main`.
2. Do the work.
3. Before reporting the task as done, have a sub agent (via the Agent tool) review the work.
4. Only after the review is done and the result has been reported to the user, push the branch to the remote (still subject to normal confirmation before pushing).

## Conventions

- Python packages use `src/` layout (`app/api/src/close_friend_api`, etc.) with `uv_build` as the build backend — always add new modules under `src/<package>/`, not next to `pyproject.toml`.
- When a value needs to cross the `app/api` → Redis → `app/worker` boundary, add/extend a model in `packages/shared/src/close_friend_shared/schemas.py` rather than redefining it in each app.
- `app/web` regenerates `app/web/AGENTS.md` and `app/web/CLAUDE.md` automatically on `next dev` — don't hand-edit them; that nested `CLAUDE.md` just points at `AGENTS.md`, which tells agents to check `app/web/node_modules/next/dist/docs/` for this Next.js version's API since it may differ from training data.
- Env vars: `app/api` reads `CF_API_*` (see `app/api/.env.example`, includes `CF_API_CORS_ORIGINS`), `app/worker` reads `CF_WORKER_REDIS_URL`, `CF_WORKER_OLLAMA_BASE_URL`, and `CF_WORKER_CHAT_MODEL` (see `app/worker/src/close_friend_worker/config.py`). Don't add an Ollama URL setting to `app/api` — per `## Data Flow`, the API never calls Ollama.
- LangGraph graphs belong in `app/worker`, invoked from inside a `@celery_app.task` function (see `app/worker/src/close_friend_worker/tasks.py`) — Celery still owns queuing, retries, and scheduling; LangGraph only owns the agent's step logic within a task, calling Ollama via `close_friend_worker.config.OLLAMA_BASE_URL`. Don't have LangGraph consume the queue directly. `respond_to_message` in `tasks.py` is the template to extend: it currently delegates straight to `chat.respond_to_message` (one direct Ollama call); a LangGraph version would replace `chat.call_ollama`'s single call with a graph invocation, keeping the same load/find/save-to-Redis structure around it.
- No ORM is wired up yet even though `app/api/src/close_friend_api/config.py` has a `database_url` setting — add SQLAlchemy/Alembic (or equivalent) when the first PostgreSQL-backed feature is implemented. Chat messages intentionally live in Redis, not Postgres, for now (see `## Current Structure`).
- `app/web` → `app/api` calls are direct browser fetches (no Next.js proxy route), enabled by `CORSMiddleware` in `app/api/src/close_friend_api/main.py`. `NEXT_PUBLIC_API_URL` is inlined into the client bundle at **build time** — set it as a Docker `build.args`, not a runtime `environment:` entry (see `app/web/Dockerfile`, `docker-compose.yml`'s `web` service).
- Tests that touch Redis use `fakeredis.FakeRedis(decode_responses=True)` via `monkeypatch.setattr(<module>, "redis_client", ...)`, and tests that touch Celery's producer client stub `send_task` the same way — see `app/api/tests/test_conversations.py` and `app/worker/tests/test_chat.py`. No real Redis/Celery broker is needed to run the test suites.
