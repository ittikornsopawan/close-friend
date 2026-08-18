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
- Database — PostgreSQL, via SQLAlchemy 2.0 + Alembic (`packages/shared/src/close_friend_shared/db/`, migrations in `packages/shared/alembic/`) — the persona system is the first Postgres-backed feature; `app/api` and `app/worker` each open their own engine/session against it (see `## Current Structure`)
- Queue / Cache — Redis
- Orchestration — Docker Compose (`docker-compose.yml` at repo root runs the full stack: `postgres`, `redis`, `ollama`, `migrate`, `api`, `worker`, `web`)
- Architecture — Clean Architecture, Vertical Slice — `app/worker/src/close_friend_worker/persona/` is the first real example (`domain/`, `application/`, `infrastructure/`)

LangGraph (`langgraph>=1.0`) is a real dependency of `app/worker` as of the persona system — see `## Persona Response Loop` for the graph itself and `## Conventions` for how it plugs into the existing Celery task structure.

## Data Flow

```text
web -> api -> redis <- worker[N] -> ollama
```

- `app/web` only ever talks to `app/api` (HTTP). It never calls Redis, Ollama, or a worker directly.
- `app/api` is a **producer only**: it enqueues a task onto Redis and returns — it does not call Ollama and does not run persona/LLM logic itself.
- `app/worker` is the **consumer**, and is meant to run as N horizontally-scaled instances pulling off the same Redis queue (`docker compose up -d --scale worker=N`). Each worker instance is the only thing that calls Ollama, and is where the `## Persona Response Loop` and LangGraph graph execution live.
- Because inference only happens in workers, the persona pipeline's latency and throughput scale with worker count, not API instance count — scale `worker`, not `api`, to handle more concurrent conversations.

**Implemented today**: `POST/GET /conversations/{conversation_id}/messages` and `GET /personas` in `app/api/src/close_friend_api/routers/`; `close_friend_worker.respond_to_message` Celery task in `app/worker/src/close_friend_worker/tasks.py` (logic in `chat.py`, which now delegates response generation to the persona LangGraph graph — see `## Persona Response Loop`). Chat messages live in Redis, not Postgres (see `## Current Structure` for the key schema); persona definitions and per-conversation emotional/relationship state live in Postgres (see `## Persona Schema`/`## Memory Structure`).

## Architecture Layers

`app/api` and `app/worker` are meant to follow Clean Architecture organized as vertical slices (one folder per feature/use case, each with its own layers) rather than horizontal layers shared across the whole app:

- **Domain** — entities and business rules, no framework imports.
- **Application** — use cases/services that orchestrate domain logic; depends only on Domain.
- **Infrastructure** — DB (PostgreSQL), Redis, LangGraph, and other external I/O; implements interfaces defined by Application.
- **Presentation** — FastAPI routers in `app/api`, Celery task entrypoints in `app/worker`; depends on Application, never the other way around.

This is the target layering — `app/worker/src/close_friend_worker/persona/` (`domain/state.py`, `application/graph.py`, `infrastructure/{persona_repository,llm}.py`) is the first slice built this way, since the persona system was non-trivial enough to warrant it. Everything else (`routers/`, `tasks.py`, `chat.py`, `db.py`) is still the flat `src/<package>/` layout described in `## Current Structure` below — only reach for the slice pattern for the next non-trivial feature, don't retrofit existing flat code just for consistency.

## Persona Response Loop

The target per-message loop, meant to run as a LangGraph graph inside a Celery task (see `## Conventions`):

1. **Chat** — user message arrives.
2. **Assess** — LLM evaluates how it should respond.
3. **Summarize context** — summarize the current state of the conversation/situation.
4. **Persona feeling + response plan** — given the persona's definition, decide how the persona should feel right now and how it should respond.
5. **Respond from feeling** — LLM drafts the reply informed by the feeling from step 4.
6. **Persist state** — save the response and resulting feeling/context back to persona memory, so a later turn (e.g. a compliment after an earlier insult) is colored by it.
7. **Reply** — send the message back to the user.

Not a fixed contract — steps may be merged or reordered per persona or for performance. **Implemented** as a real LangGraph `StateGraph` in `app/worker/src/close_friend_worker/persona/application/graph.py`, collapsing steps 2–4 into a single structured-output LLM call as explicitly permitted above — 2 total LLM calls per message, not 5, since a local ~7B model doing 4-5 sequential calls would make replies impractically slow:

- `load_persona_context` — no LLM; loads the `personas` row + `persona_states` row (steps 1/prep).
- `assess_and_plan` — **LLM call #1**, structured JSON output (`AssessmentResult` in `persona/domain/state.py`) — steps 2–4 combined: context summary, detected trigger, resulting emotion/intensity/relationship stage, rapport delta, response plan, and a boundary check. Constrained to that persona's own `emotion_rules`/`relationship_stages` vocabulary via the prompt. Retries once on invalid JSON, then falls back to a safe neutral assessment (`persona/infrastructure/llm.py`) rather than failing the task.
- A conditional edge on `assessment.boundary_violated` — gives the `boundaries` field an actual runtime job:
  - `boundary_response` — no LLM call, a templated persona-flavored refusal (safer than trusting the model to self-refuse mid-character).
  - `respond_in_character` — **LLM call #2**, step 5 — the actual reply, prompted with the persona's `character`/`boundaries` plus the assessment's emotion/stage/plan.
- `persist_state` — step 6, no LLM; happens in `graph.py`'s `run_persona_graph()` after `graph.invoke()` returns, not as a graph node — upserts `persona_states` and inserts an `episodic_events` row iff the assessment flagged it significant.
- Step 1 ("Chat") and step 7 ("Reply") stay outside the graph in `chat.py`, exactly as originally specified — `chat.py`'s `load_messages`/`find_message_index`/`save_message`/`_mark_failed`/outer try-except are unchanged from the pre-persona MVP; only `build_ollama_history` + `call_ollama` were replaced by `generate_persona_reply()`, which opens a DB session and calls `run_persona_graph()`.

No LangGraph checkpointer — the graph runs synchronously start-to-finish within one Celery task with no interrupt/resume need; `persist_state` is the single persistence mechanism.

## Persona Schema

**Implemented** as the `personas` table (`packages/shared/src/close_friend_shared/db/models.py`), matching the original conceptual shape plus a few fields needed for the UI (`tagline`, `avatar_initials`, `tags`, `is_active`):

- `id`, `name` — identity. `id` is a slug (e.g. `nova`) that doubles as the Redis `conversation_id`, same 1:1 pattern the pre-persona hardcoded contacts used.
- `character` (JSONB) — `{backstory, personality_traits[], tone, speech_style, opening_message}`.
- `emotion_rules` (JSONB) — trigger → reaction mapping, e.g. `{"trigger": "insult", "reaction_emotion": "hurt", "intensity_delta": 0.4, "decay_per_turn": 0.05}`. Intensity is 0.0–1.0, clamped in `persona_repository.apply_assessment`.
- `relationship_stages` (JSONB) — `{"stage": "familiar", "min_rapport": 15, "tone": "..."}` thresholds; `assess_and_plan` picks from this persona's own stage vocabulary.
- `boundaries` (JSONB, `list[str]`) — hard constraints; feeds both the `respond_in_character` prompt and the `boundary_response` conditional branch in the graph.
- `research_scope` (JSONB) — schema placeholder only, per `## Project Overview`'s research subsystem. Not read or written by anything yet — still not implemented.
- `baseline_state` (JSONB) — default `{emotion, emotion_intensity, relationship_stage, rapport_score}` for a new conversation; `persona_repository.get_or_init_state` seeds a `persona_states` row from this on first turn.
- 3 seed personas ship in `packages/shared/src/close_friend_shared/db/seed.py` (`general`/`nova`/`kai` — matching the old hardcoded contact ids so existing Redis history stays meaningful): safe-for-work personality archetypes (cheerful friend, dry-witted skeptic, calm mentor), not romantic/dating content. No creator/editing UI — seed data only.

## Memory Structure

Layered memory backing the response loop above — `persist_state` writes here, `assess_and_plan`/`respond_in_character` read from it. All implemented except research memory:

- **Working memory** — current conversation's raw turns; this is just the existing Redis `ChatMessage` list (`## Current Structure`), unchanged by the persona system — `build_ollama_history` still reads it the same way.
- **Emotional state** — `persona_states.emotion`/`emotion_intensity`/`emotion_cause`, updated every turn by `persist_state`, read at `assess_and_plan`/`respond_in_character`.
- **Episodic memory** — `episodic_events` table, one row per significant turn (`conversation_id`, `message_id` — a logical reference to the Redis `ChatMessage.id`, not a real FK since Redis isn't Postgres — `turn_index`, `event_type`, `description`, `emotion_impact`). Only inserted when `assessment.is_significant_event` is true, not every turn.
- **Relationship memory** — `persona_states.relationship_stage`/`rapport_score`/`known_facts`/`turn_count`, persists across sessions since it's keyed by `conversation_id` in Postgres, not Redis. `persona_states.persona_id` is a separate FK column from `conversation_id` (not reused), so multiple conversations per persona won't need a migration if multi-user auth ever arrives — still out of scope today.
- **Research memory (RAG/CAG/MAG)** — **not implemented.** `personas.research_scope` exists as a schema placeholder only; no retrieval logic, no vector store.

Storage: `packages/shared/src/close_friend_shared/db/models.py` (SQLAlchemy models, `personas`/`persona_states`/`episodic_events`), migrations in `packages/shared/alembic/`. Every JSON column uses `JSON().with_variant(JSONB(), "postgresql")` — real `JSONB` on Postgres, portable `JSON` on SQLite for tests (see `## Conventions`).

## Current Structure

Polyglot monorepo with three apps sharing one Python dependency graph:

- `app/web` — Next.js 16 (App Router, TypeScript, Tailwind v4, Turbopack). npm workspace member declared at the root `package.json`. Messenger-style chat UI: `src/components/chat/` (`ChatApp` loads personas via `usePersonas` and owns the selected-persona id, `Sidebar`/`ContactListItem`, `ChatWindow`/`MessageList`/`MessageBubble`/`MessageInput`), `src/lib/types.ts` (`Persona` matching `GET /personas`'s narrow response), `src/lib/api-client.ts` (typed fetch wrapper, reads `NEXT_PUBLIC_API_URL`), `src/hooks/usePersonas.ts` (fetch-once-on-mount, loading/error state), `src/hooks/useConversation.ts` (polls `GET .../messages` every 1s, up to 150 attempts, after sending — sized for the persona graph's up-to-~4-minute worst case, not the old single-call MVP's 60).
- `app/api` — FastAPI HTTP service. Package `close_friend_api`, entrypoint `close_friend_api.main:app`. Routes: `health.py` (`/healthz`), `conversations.py` (`POST`/`GET /conversations/{conversation_id}/messages`), `personas.py` (`GET /personas`, narrow read-model — never returns `character`/`emotion_rules`/`boundaries`, so a user can't read a persona's exact triggers out of devtools and game the emotional system). `celery_client.py` holds a broker-only Celery producer (`send_task(...)`) — it does not import `app/worker`. `redis_client.py` is a plain `redis.Redis` instance. `db.py` is a SQLAlchemy engine/`SessionLocal` from `settings.database_url`, injected into routes via `Depends(get_db)`.
- `app/worker` — Celery worker consuming a Redis-backed queue. Package `close_friend_worker`, Celery app at `close_friend_worker.celery_app:celery_app`, tasks in `close_friend_worker/tasks.py`. `chat.py` holds the message-answering orchestration (`respond_to_message`, `build_ollama_history`, `generate_persona_reply`) as plain functions the Celery task delegates to, kept separate so they're unit-testable without Celery/a broker; `generate_persona_reply` opens a DB session and calls into `persona/application/graph.py`'s `run_persona_graph()` — see `## Persona Response Loop`. `db.py` reads `CF_WORKER_DATABASE_URL`.
- `packages/shared` — Python package `close_friend_shared`: Pydantic schemas (`TaskMessage`, `JobStatus`, `ChatMessage`, `MessageRole`, `MessageStatus`) and `conversation_messages_key(conversation_id)` — the Redis key-naming function — shared between `app/api` and `app/worker` so both sides agree on queue message shapes and Redis keys without duplicating either. `db/` holds the SQLAlchemy models + Alembic migrations for Postgres (`personas`/`persona_states`/`episodic_events`) and the seed script — the schema source of truth lives here, not in either app, since both read `personas` and neither "owns" it more than the other.

**Redis message schema**: one list per conversation, `cf:conv:{conversation_id}:messages` (via `conversation_messages_key`), `RPUSH`-only, each element a JSON-encoded `ChatMessage` (`id`, `role`, `content`, `status`: `pending`/`complete`/`failed`, `created_at`). No TTL. `app/api` appends a `complete` user message + `pending` assistant placeholder and enqueues the task; `app/worker` re-reads the whole list, builds Ollama's history from `complete` messages, then `LSET`s the placeholder in place to `complete` (with the reply) or `failed` (with a generic error message, on any Ollama/connection exception — never left `pending` forever).

`app/api`, `app/worker`, and `packages/shared` are members of a single **uv workspace** rooted at the top-level `pyproject.toml` (`[tool.uv.workspace]`, `package = false` — the root itself is virtual, not an installable package). They share one `.venv` at the repo root. `app/api` and `app/worker` depend on `close-friend-shared` via `[tool.uv.sources]` workspace references, not a published package — edit `packages/shared` and both consumers see it immediately, no reinstall needed.

`app/web` is a separate **npm workspace** (root `package.json`) since it doesn't share code with the Python apps.

All three apps plus infra are orchestrated by the root `docker-compose.yml`: `postgres`, `redis`, `ollama` (local LLM runtime), one-shot init services `ollama-pull` (pulls the default model) and `migrate` (`packages/shared/Dockerfile` — runs `alembic upgrade head` then the seed script), and build services `api` (`app/api/Dockerfile`), `worker` (`app/worker/Dockerfile`), `web` (`app/web/Dockerfile`). `api`/`worker` both gate on `migrate: condition: service_completed_successfully`; `worker` additionally gates on `ollama-pull`. Each app's Dockerfile builds from the **repo root as context** (not its own subfolder), since `api`/`worker`/`migrate` need `packages/shared` and the root `uv.lock`, and `web` needs the root `package.json`/`package-lock.json` for the npm workspace — always pass `context: .` with a `dockerfile:` path when adding a service, never build from inside `app/*`.

## Commands

Run from the repo root unless noted.

### Setup

```bash
npm install                 # app/web deps
uv sync --all-packages      # app/api, app/worker, packages/shared deps into one .venv
docker compose up -d postgres redis ollama   # infra only, for running app code on the host
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M   # the ollama image starts empty
uv run --package close-friend-shared alembic -c packages/shared/alembic.ini upgrade head
uv run --package close-friend-shared python -m close_friend_shared.db.seed   # idempotent — safe to re-run
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
uv run --package close-friend-shared pytest packages/shared/tests

# single test
uv run --package close-friend-api pytest app/api/tests/test_health.py::test_healthz -q
```

There is no test suite in `app/web` yet.

## Workflow

Every task follows this sequence:

1. Create a new branch off `main` before starting work — never commit directly to `main`.
2. Do the work.
3. Before reporting the task as done, have a sub agent (via the Agent tool) review the work.
4. Only after the review is done and the result has been reported to the user, push the branch to the remote (still subject to normal confirmation before pushing):

```bash
gh auth status               # confirm gh is authenticated (repo scope) — pushes go over gh's credential helper, no separate SSH/token setup
git push -u origin <branch>  # first push of a new branch; subsequent pushes on the same branch are just `git push`
gh pr create                 # optional — open a PR against main once the branch is pushed
```

## Conventions

- Python packages use `src/` layout (`app/api/src/close_friend_api`, etc.) with `uv_build` as the build backend — always add new modules under `src/<package>/`, not next to `pyproject.toml`.
- When a value needs to cross the `app/api` → Redis → `app/worker` boundary, add/extend a model in `packages/shared/src/close_friend_shared/schemas.py` rather than redefining it in each app.
- `app/web` regenerates `app/web/AGENTS.md` and `app/web/CLAUDE.md` automatically on `next dev` — don't hand-edit them; that nested `CLAUDE.md` just points at `AGENTS.md`, which tells agents to check `app/web/node_modules/next/dist/docs/` for this Next.js version's API since it may differ from training data.
- Env vars: `app/api` reads `CF_API_*` (see `app/api/.env.example`, includes `CF_API_CORS_ORIGINS` and `CF_API_DATABASE_URL`), `app/worker` reads `CF_WORKER_REDIS_URL`, `CF_WORKER_OLLAMA_BASE_URL`, `CF_WORKER_CHAT_MODEL`, and `CF_WORKER_DATABASE_URL` (see `app/worker/src/close_friend_worker/config.py`/`db.py`). Don't add an Ollama URL setting to `app/api` — per `## Data Flow`, the API never calls Ollama.
- LangGraph graphs belong in `app/worker`, invoked from inside a `@celery_app.task` function (see `app/worker/src/close_friend_worker/tasks.py`) — Celery still owns queuing, retries, and scheduling; LangGraph only owns the agent's step logic within a task, calling Ollama via `close_friend_worker.config.OLLAMA_BASE_URL`. Don't have LangGraph consume the queue directly. `persona/application/graph.py`'s `run_persona_graph()` is the pattern to follow for the next graph — build the compiled graph once at module import (stateless, reusable), pass per-invocation data through the state dict, and inject I/O dependencies (DB session, etc.) rather than baking them into the compiled graph.
- SQLAlchemy models + Alembic migrations for Postgres live in `packages/shared/src/close_friend_shared/db/` (schema source of truth shared by both apps), not in `app/api` or `app/worker` individually — each app only owns a thin `db.py` (engine + `SessionLocal`) pointed at its own `*_DATABASE_URL` env var. Chat messages still intentionally live in Redis, not Postgres (see `## Current Structure`); only persona/memory data is Postgres-backed.
- `app/web` → `app/api` calls are direct browser fetches (no Next.js proxy route), enabled by `CORSMiddleware` in `app/api/src/close_friend_api/main.py`. `NEXT_PUBLIC_API_URL` is inlined into the client bundle at **build time** — set it as a Docker `build.args`, not a runtime `environment:` entry (see `app/web/Dockerfile`, `docker-compose.yml`'s `web` service).
- Tests that touch Redis use `fakeredis.FakeRedis(decode_responses=True)` via `monkeypatch.setattr(<module>, "redis_client", ...)`, and tests that touch Celery's producer client stub `send_task` the same way — see `app/api/tests/test_conversations.py` and `app/worker/tests/test_chat.py`. No real Redis/Celery broker is needed to run the test suites.
- Tests that touch Postgres use `create_engine("sqlite:///:memory:")` + `Base.metadata.create_all(engine)` instead of a real database — see `packages/shared/tests/test_db_models.py`, `app/worker/tests/test_persona_repository.py`/`test_graph.py`. This is exactly why every JSON column must use `JSON().with_variant(JSONB(), "postgresql")` rather than a bare `JSONB()` — the latter fails to create on SQLite. Never invoke Alembic in the test suite — migrations are Postgres-specific once autogenerated (they reference `postgresql.JSONB` directly) and only ever run against real Postgres, via the `migrate` service or the local dev command in `## Commands`. FastAPI route tests using `TestClient` additionally need `poolclass=StaticPool` on the SQLite engine (see `app/api/tests/test_personas.py`) — `TestClient` runs sync route handlers in a separate thread, and SQLite's default `:memory:` pooling gives each thread its own blank database otherwise.
