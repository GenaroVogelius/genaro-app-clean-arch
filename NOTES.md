# genaro-app — Notes

Backend API that ingests podcasts from the **iTunes Search API** into
**MongoDB**. For each podcast it downloads the artwork image, stores it on disk
and extracts a color palette from it. Built with FastAPI following Clean
Architecture + DDD.

**Stack:** FastAPI + Uvicorn · MongoDB (Beanie on PyMongo async) · httpx ·
Pillow · slowapi · uv · Python 3.13 · pytest, mypy, ruff, import-linter.

## Table of contents

1. [New on here?](#new-on-here)
2. [Architecture](#architecture)
3. [Running locally](#running-locally)
4. [Tests & quality checks](#tests--quality-checks)
5. [Testing strategy & CI](#testing-strategy--ci)
6. [Design decisions](#design-decisions)
7. [Adding a feature](#adding-a-feature)
8. [Troubleshooting](#troubleshooting)
9. [RuleSync](#rulesync)
10. [Next production steps](#next-production-steps)

---

## New on here?

Welcome! The quickest way to get up to speed is to let an LLM walk you
through the codebase. Open the repo in your AI assistant (Claude Code, Cursor,
Copilot or Codex, see [RuleSync](#rulesync)) and run the **onboarding** skill
(`.rulesync/skills/onboarding/`):

```text
/onboarding
```

It gives you a guided tour of the architecture, the podcast slice, how to run
the app and the tests, and the project rules, and you can ask follow-up
questions as you go. Then use this file as a reference:

1. Read [Architecture](#architecture) to learn the layers and the dependency rule.
2. Follow [Running locally](#running-locally) to get the API and MongoDB up.
3. Run the [Tests & quality checks](#tests--quality-checks) to confirm your setup.
4. Before your first change, read [Adding a feature](#adding-a-feature).

---

## Architecture

### Layers

```
                 HTTP (X-API-Key header)
  Client ─────────────────────────────────────┐
                                              ▼
  ┌──────────────────── infrastructure/api ────────────────────┐
  │ podcast_routes.py   schemas/ (request/response models)     │
  │ security/ (API key) dependencies/ (DI: builds use cases)   │
  └──────────────────────────────┬─────────────────────────────┘
                                 │ calls
                                 ▼
  ┌────────────────────────── domain ──────────────────────────┐
  │ use_cases/   Get / List / Export / Ingest one / many       │
  │ podcast/     aggregate/ (Podcast, Artwork), queries/       │
  │ ingestion/   IngestionSummary, PodcastArtworkResolver      │
  │ common/      Status, DatabaseTypes                         │
  │ interfaces/  PORTS (repositories, providers, storage,      │
  │              services, logger, mapper)                     │
  └──────────────────────────────▲─────────────────────────────┘
                                 │ implemented by
  ┌─────────────────── infrastructure adapters ────────────────┐
  │ MongoPodcastsRepository ───────────────▶ MongoDB           │
  │ ITunesProvider (+ ITunesMapper) ───────▶ itunes.apple.com  │
  │ HttpArtworkDownloader ─────────────────▶ artwork image URL │
  │ LocalArtworkStorage ───────────────────▶ media/artwork/    │
  │ PillowColorPaletteExtractor, Logger                        │
  └────────────────────────────────────────────────────────────┘
```

**Dependency rule:** the domain never imports infrastructure. It may only use
the stdlib and `pydantic`. `lint-imports` enforces this through the contracts
in `pyproject.toml` (`[tool.importlinter]`). Adapters are wired to ports in
`app/infrastructure/api/dependencies/`, which is the composition root.

To see the general architecture of the project, explore the import graph
interactively in the browser:

```bash
uv run import-linter explore app
```

### Ingestion flow

```
POST /api/podcasts/ingest?term=&limit=&country=     POST /api/podcasts/{id}/ingest
              │                                                   │
   provider.search(criteria)                       provider.lookup_by_id(id)
              │                                                   │
   drop duplicate ids in the batch                                │
              │                                                   │
   for each podcast (bulk: max PODCAST_INGEST_CONCURRENCY) ◀──────┘
     1. repository.get_podcast_by_id()          → stored version, if any
     2. PodcastArtworkResolver.resolve()
          download image → store on disk → extract palette
          (skipped when the artwork URL did not change)
     3. repository.store_podcast()              → CREATED | UPDATED | UNCHANGED | ERROR
              │                                                   │
   IngestionSummary (fetched, created, updated,        Status (201 created, 200 otherwise)
   unchanged, duplicates, failed)
```

### Directory layout

```
app/
├── main.py              # FastAPI app, lifespan (Mongo + shared httpx client), CORS, error handlers
├── config/settings.py   # Pydantic Settings (env vars, env files)
├── domain/              # Business core, stdlib + pydantic only
│   ├── podcast/         # Modules grouped by domain concept
│   │   ├── aggregate/   # Podcast (root), Artwork, PaletteColor, Explicitness
│   │   ├── queries/     # Criteria, pages and search results (not part of the aggregate)
│   │   └── exceptions.py # Podcast errors (not found, not a podcast, persistence, retrieval)
│   ├── ingestion/       # IngestionSummary, ArtworkResolution, PodcastArtworkResolver,
│   │                    # ArtworkUnavailableError
│   ├── common/          # Status, DatabaseTypes, ExternalServiceError
│   ├── interfaces/      # Ports: repositories, providers, storage, services, logger, mapper
│   ├── use_cases/       # One folder per use case, test next to it
│   ├── validations/
└── infrastructure/      # Adapters
    ├── api/             # Routes, schemas, dependencies (DI), security (API key)
    ├── db/mongo/        # Connection + repositories/<name>_repository/{*_document,*_mapper,*_repository}.py
    ├── providers/       # External APIs (itunes_provider, artwork_provider, http_client)
    ├── services/        # color_palette (Pillow), local_artwork_storage
    ├── mapper/          # GlobalMapper base (@maps registrations)
    ├── logger/          # Console + rotating file logger
    └── utils/           # decorators, functions, testing (VCR helper)
podman/local/            # Containerfile, compose file, .env.example, bind volumes
```

---

## Running locally

### Prerequisites

- [Podman](https://podman.io/) and `podman compose` (podman-compose plugin)
- [uv](https://docs.astral.sh/uv/). It installs Python 3.13 by itself if needed.

### Environment variables

```bash
cp podman/local/.env.example podman/local/.env
```

| Variable | Default | Purpose |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `MONGODB_USER` / `MONGODB_PASSWORD` | `admin` / `password123` | Mongo root credentials (also used by the compose Mongo container) |
| `MONGODB_DATABASE` | `genaro-app-mongodb` | Database name |
| `MONGODB_URL` | built from the above, host `mongodb` | Full connection string. Set it when running the API on the host (see Mode B) |
| `ALLOW_ORIGINS` | `*` | CORS allowed origin |
| `AUTH` | `True` | API-key auth on/off. Set `False` only for local dev |
| `API_KEY` | none | Value clients must send in the `X-API-Key` header |
| `RATE_LIMIT` | `10/minute` | Requests each client IP may make across the whole API, e.g. `100/hour` |
| `RATE_LIMIT_ENABLED` | `True` | Rate limiting on/off |

Optional overrides (defaults in `app/config/settings.py`):
`ITUNES_BASE_URL`, `ITUNES_TIMEOUT_SECONDS`, `PODCAST_INGEST_CONCURRENCY` (5),
`PODCAST_EXPORT_BATCH_SIZE` (500), `ARTWORK_STORAGE_DIR` (`media/artwork`), `ARTWORK_TIMEOUT_SECONDS`,
`ARTWORK_PALETTE_SIZE` (5), `API_PREFIX` (`/api`), `DEBUG`.

Settings reads these env files, and later files win:
`podman/local/.env` → `./.env` → `podman/local/devcontainer.env`. Real
environment variables override all of them. `podman/local/.env` is read even
when running on the host.

### Mode A: full stack in Podman (app + MongoDB)

```bash
podman compose -f podman/local/compose.local.yml up -d --build   # first time / after dependency changes
podman compose -f podman/local/compose.local.yml up -d           # later runs
podman compose -f podman/local/compose.local.yml logs -f app     # follow API logs
podman compose -f podman/local/compose.local.yml down            # stop everything
```

The repo is bind-mounted into the container and Uvicorn runs with `--reload`,
so code changes apply without rebuilding.

### Mode B: API on the host, MongoDB in Podman

```bash
uv sync --group dev
podman compose -f podman/local/compose.local.yml up -d mongodb
export MONGODB_URL="mongodb://admin:password123@localhost:27017/genaro-app-mongodb?authSource=admin"
uv run uvicorn app.main:app --reload
```

(You can put `MONGODB_URL` in `podman/local/.env` instead of exporting it,
but only if you don't also use Mode A. The container would then try to reach
`localhost`.)

### Using the API

- Swagger UI: <http://localhost:8000/docs>. Use the **Authorize** button to set
  `X-API-Key`.
- Every endpoint except `GET /api/podcasts/health` requires the API key when
  `AUTH=True`.
- Each client IP gets `RATE_LIMIT` requests (10/minute by default) shared
  across every endpoint. Over it, the API answers 429 with a `Retry-After`
  header. `/docs`, `/redoc`, `/openapi.json` and the health check don't count.

---

## Tests & quality checks

```bash
uv sync --group dev                  # install dev dependencies once

uv run pytest                        # full suite (no DB or network needed)
uv run pytest app/domain             # only one folder
uv run pytest -k ingest              # by name
uv run pytest --cov=app              # with coverage

uv run mypy app                      # type checking
uv run lint-imports                  # architecture contracts (domain ↛ infrastructure)
uv run import-linter explore app     # interactive import graph in the browser
uv run ruff check app                # lint
uv run ruff format --check app       # formatting (drop --check to apply)
```

If you prefer an activated venv: `source .venv/bin/activate`, then run the
same commands without `uv run`.

---

## Testing strategy & CI

Tests live next to the code they test (`test_*.py`, found under `app/`).

| Layer | Approach |
|---|---|
| Use cases (`domain/use_cases/**`) | Hand-written **Fake** classes that implement the ports and record calls. No infrastructure. |
| Mongo repositories | `mongomock_motor.AsyncMongoMockClient` + `init_beanie`. An in-memory Mongo, no real DB. |
| External providers (iTunes) | **VCR cassettes** (`*.yaml` next to the test) via `app/infrastructure/utils/testing/vcr.py`. |
| Artwork downloader / storage / palette | Mocked HTTP transport, temp dirs, in-memory images. |
| API routes | `TestClient` + `app.dependency_overrides` to inject fakes. |

**VCR record mode.** The `VCR_RECORD_MODE` env var controls it (default
`new_episodes`):

- `none`: replay only. Fails if a request has no cassette. **CI uses this.**
- `new_episodes` (local default): replays what exists and records new requests
  against the real API.
- To re-record a cassette, delete the `.yaml` and run the test once with
  network access (`VCR_RECORD_MODE=once uv run pytest path/to/test_file.py`).
  Check the diff for secrets before committing. Cookies and auth headers are
  filtered automatically.

**CI:** `.github/workflows/tests.yml` runs on every push and on PRs to `main`.
It installs uv and Python 3.13, runs `uv sync --locked --group dev`, then
`uv run pytest` with `VCR_RECORD_MODE=none`. mypy, ruff and lint-imports are
not in CI yet, so run them locally before pushing.

---

## Design decisions

- **Idempotent ingestion.** Podcasts are keyed by `podcast_id`.
  `store_podcast` inserts (`CREATED`), replaces (`UPDATED`) or does nothing when
  the data is identical (`UNCHANGED`). Running the same ingestion twice never
  duplicates data.
- **Batch resilience.** Duplicate ids inside one search result are dropped and
  counted as `duplicates`. A podcast that fails is logged and counted as
  `failed`, and the rest of the batch still runs. Only a failure of the search
  itself aborts (→ 502).
- **Bounded concurrency.** The bulk ingestion processes at most
  `PODCAST_INGEST_CONCURRENCY` podcasts at once (`asyncio.Semaphore`), which
  avoids hammering iTunes and the artwork hosts.
- **Streaming export.** `GET /api/podcasts/export` downloads the whole
  catalog as a CSV file (`podcasts-<UTC timestamp>.csv`), sorted by
  `podcast_id`. Memory stays flat however big the catalog is:
  - Mongo is read with **keyset batches** (`podcast_id > last_id`, limit
    `PODCAST_EXPORT_BATCH_SIZE`) on the unique `podcast_id` index. There is
    no skip/limit, which slows down as the offset grows. There is no cursor
    held open for the whole download either, which Mongo would kill after
    10 idle minutes behind a slow client. Because `podcast_id` never changes,
    an ingestion running during the export can't make a row appear twice.
  - Each batch is written to the response as one CSV chunk and then dropped.
  - The first batch is read before responding, so an unreachable database
    still answers 503. If a later batch fails, the 200 is already sent, so
    the error is logged and the connection is aborted. The client sees a
    failed download instead of a truncated file that looks complete.
  - Columns: `podcast_id, name, author, feed_url, view_url, genre,
    episode_count, release_date` (ISO 8601), `country, explicitness,
    artwork_source_url, artwork_path, artwork_palette`. The palette is joined
    as `#1a2b3c:0.6|#ffffff:0.4`. Missing values are empty cells.
- **Artwork resolution** (`domain/services/podcast_artwork`). Artwork is only
  downloaded when it was never processed or its source URL changed. If
  processing fails, the previously processed artwork is kept. If there is none,
  the unprocessed URL is stored so it isn't lost. Missing artwork never fails
  the ingestion.
- **One shared `httpx.AsyncClient`** is opened in the app lifespan and injected
  into every outbound adapter, so connections are reused. It is closed on
  shutdown.
- **Beanie auto-discovery.** Any `*_document.py` inside
  `db/mongo/repositories/*_repository/` is registered at startup. No manual
  list to maintain.
- **Ports speak the domain.** Repository write methods return the `Status`
  model, not raw enums or driver results. Providers return domain entities
  converted through a `GlobalMapper` subclass, never raw dicts or API payloads.
- **Domain exceptions → HTTP codes** in the routes: not found → 404, not a
  podcast → 422, external service error → 502, persistence error → 503.
- **Health check.** `GET /api/podcasts/health` pings Mongo and returns 503 when
  it is unreachable. It is the only unauthenticated route.
- **API-key auth** uses `secrets.compare_digest` (constant time). If auth is
  enabled but no `API_KEY` is configured, every request is rejected instead of
  failing open.
- **Rate limiting** (`infrastructure/api/rate_limit.py`, slowapi). One bucket
  per client IP for the whole API (`application_limits`, not per-endpoint
  `default_limits`). The health check is exempt (`@rate_limit_exempt`):
  load balancers poll it from a few fixed IPs, and a 429 would take a healthy
  task out of rotation. Counters live in memory: per process and reset on
  restart, which is fine for the single uvicorn worker. Scaling out needs a
  shared store (`storage_uri="redis://..."`). Behind a reverse proxy every
  client would share the proxy's IP, so the key function would have to read
  the `X-Forwarded-For` set by that proxy. It uses `SlowAPIMiddleware`, not `SlowAPIASGIMiddleware`,
  because the ASGI one breaks streaming responses like the CSV export.

---

## Adding a feature

Follow the podcast slice as the reference implementation. The linked skills in
`.rulesync/skills/` spell out each rule in detail.

1. **Domain model:** group it by concept under `domain/<concept>/` (pydantic
   only): the aggregate root and what it owns in `aggregate/`, related criteria
   and results in `queries/`. Generic types go in `domain/common/`.
2. **Port:** add the interface in `domain/interfaces/<kind>/`. Write methods on
   repositories return `Status`
   ([repository-writes-return-status](.rulesync/skills/repository-writes-return-status/SKILL.md)).
3. **Use case:** add `domain/use_cases/<entity>/<action>/<action>_use_case.py`
   with `async def execute(...)`, depending only on ports and domain entities
   ([use-case-abstractions](.rulesync/skills/use-case-abstractions/SKILL.md),
   [use-case-model-construct](.rulesync/skills/use-case-model-construct/SKILL.md)).
4. **Use case test:** put a `test_<action>_use_case.py` next to it, using Fakes
   ([use-case-test-fakes](.rulesync/skills/use-case-test-fakes/SKILL.md)).
5. **Adapter:**
   - DB: `db/mongo/repositories/<name>_repository/` with `*_document.py`,
     `*_mapper.py` and `*_repository.py`. The document is auto-registered.
   - External API: `providers/<name>_provider/` with typed `responses/`, a
     mapper and VCR tests
     ([provider-domain-entities](.rulesync/skills/provider-domain-entities/SKILL.md),
     [type-external-service-responses](.rulesync/skills/type-external-service-responses/SKILL.md)).
6. **Wiring:** add factory functions and `Annotated[..., Depends(...)]` aliases
   in `infrastructure/api/dependencies/`.
7. **HTTP:** add the route plus request/response schemas in `infrastructure/api/`,
   map domain exceptions to status codes, and protect the route with
   `dependencies=[Depends(require_api_key)]`.
8. **Checks:** run `pytest`, `mypy`, `lint-imports` and `ruff`.

---

## Troubleshooting

- **Permission denied on bind mounts (Fedora/SELinux).** Volumes in
  `compose.local.yml` use `:z` so SELinux allows access. Keep it when adding
  new mounts.
- **Rootless Podman file ownership.** The app container runs as `user: root`,
  which maps to your host user in rootless Podman. `userns_mode: keep-id` is
  deliberately not used because it triggers a crun/netavark
  `ping_group_range` error on some setups.
- **`401 Invalid or missing API key`.** Send `X-API-Key: <API_KEY>`, or set
  `AUTH=False` for local dev. With `AUTH=True` and no `API_KEY` set, *every*
  request is rejected (the log says "AUTH is enabled but API_KEY is not
  configured").
- **API on the host can't reach Mongo / server selection timeout.**
  `MONGODB_URL` must point at `localhost:27017`, not `mongodb`, and the Mongo
  container must be up (`podman compose -f podman/local/compose.local.yml ps`).
- **Reset the database.** Run `podman compose -f podman/local/compose.local.yml down`,
  then delete `podman/local/volumes/mongodb_data/`.
- **Stale container venv after changing dependencies.** Rebuild with
  `up -d --build`, or delete `podman/local/volumes/app_venv/`.
- **Tests hit the real iTunes API.** With the default
  `VCR_RECORD_MODE=new_episodes`, a request missing from the cassette gets
  recorded live. Use `VCR_RECORD_MODE=none` to reproduce CI.
- **Where things are written.** Logs go to stdout and to `logs/app.log`
  (rotating, 10 MB × 5). Artwork is saved under `media/artwork/`. Both are
  git-ignored.

---

## RuleSync

[RuleSync](https://rulesync.dyoshikawa.com/) turns one ruleset in `.rulesync/`
into each AI assistant's native format, so instructions aren't duplicated per
tool. Targets are configured in `rulesync.jsonc`: `claudecode`, `cursor`,
`copilot` and `codexcli`.

```bash
pnpm install -g rulesync

rulesync import --targets cursor          # pull existing Cursor rules into .rulesync/
rulesync generate --targets claudecode    # write Claude Code files from .rulesync/
rulesync generate --targets cursor        # write Cursor files from .rulesync/
```

What's in `.rulesync/`:

- **rules/**: `python-venv-commands-always`, `functions-creator-modificator`
- **skills/**: `use-case-abstractions`, `use-case-model-construct`,
  `use-case-test-fakes`, `repository-writes-return-status`,
  `provider-domain-entities`, `type-external-service-responses`
- **commands/**: `review-pr`
- **hooks.json**: formatter run after file edits

---

## Next production steps

What's still needed to run this service in production on AWS.

### Production image

`podman/local/Containerfile.local` is built for development. It ships gcc, git
and build-essential, compose runs it as root, and Uvicorn runs with `--reload`.
None of that belongs in production.

- **Separate multi-stage `Containerfile`.** The builder stage runs
  `uv sync --locked --no-dev`. The runtime stage is a slim Python image that
  copies only the venv and `app/`, with no gcc or git.
- **Non-root user, no `--reload`.** Run Uvicorn as an unprivileged user.
- **CA bundle for DocumentDB.** The image includes the AWS RDS CA bundle, for security reasons.
- **Health checks.** `GET /api/podcasts/health` becomes the readiness check,
  since it pings the database. Liveness gets its own lightweight check that
  doesn't touch the database, so a database outage takes tasks out of
  rotation instead of restarting all of them.

### Configuration and secrets

`app/config/settings.py` has defaults that are fine locally but dangerous in
production: `MONGODB_PASSWORD="password123"`, `DEBUG=True` and
`ALLOW_ORIGINS="*"`.

- **It stays 12-factor.** `Settings` already reads everything from environment
  variables, so production only changes where those values come from.
- **No unsafe defaults.** In production, `MONGODB_*`, `API_KEY` and
  `ALLOW_ORIGINS` are required. A misconfigured task refuses to start instead
  of quietly using `password123`. `DEBUG` defaults to `false`.
- **Non-secret config** (concurrency, batch sizes, rate limits, timeouts) is
  set in the ECS task definition and versioned in Terraform with the rest of
  the infrastructure.
- **Secrets live in AWS Secrets Manager.** ECS injects them into the task as
  environment variables. They never appear in the image or the repo.
- **DocumentDB credentials.** The database password is stored in Secrets
  Manager with managed rotation turned on. `MONGODB_URL` must include
  `tls=true`, `tlsCAFile=<bundle path>` and `retryWrites=false`, because
  DocumentDB doesn't support retryable writes.
- **Per-client API keys.** Replace the single shared `API_KEY` with one key
  per client, stored hashed in the database, so each key can be rotated or
  revoked on its own or we can use JTW for auth.

### Deploying on AWS

The same image is built once and runs with a different command for each job:

| Command | Runs as |
|---|---|
| `api` | ECS Fargate service, scaled on CPU and request count |
| `migrate` | One-off ECS Fargate task, run before each rollout (see below) |
| `prefect-worker` | ECS Fargate service that polls the Prefect work pool and starts each flow run as its own ECS task (see [Continuous ingestion](#continuous-ingestion)) |
| `worker --queue=feeds\|episodes\|artwork` | One ECS Fargate service per SQS queue, scaled on queue depth. Only in the Prefect + SQS stage |

- **ECR** stores the images, each tagged with the git SHA it was built from.
- **Terraform** defines all the infrastructure: ECS cluster and services, task
  definitions, ECR, DocumentDB, S3/CloudFront, Secrets Manager, IAM roles and
  alarms.
- **Amazon DocumentDB** runs in private subnets. Only the ECS tasks' security
  group can reach it.
- **Rate limiting with more than one task.** As noted in
  [Design decisions](#design-decisions), slowapi counts in memory per process.
  With several tasks it needs a shared store (`storage_uri`). The key function
  must also read `X-Forwarded-For`, or every client would share the load
  balancer's IP.

### Continuous ingestion

Today podcasts are only ingested when someone calls
`POST /api/podcasts/ingest` or `POST /api/podcasts/{id}/ingest`. The work runs
inside the HTTP request, and nothing keeps the catalog fresh on its own.
Ingestion should run on a schedule, so nobody has to call the endpoints by
hand. The endpoints stay for one-off runs.

The setup depends on the volume. Both stages call the same use cases, so moving
from the first to the second doesn't touch the domain.

**Moderate volume (tens of thousands of feeds): Prefect only.**

- **Flows are a driving adapter.** They live in
  `app/infrastructure/orchestration/` and build the use cases (for example
  `IngestPodcastsUseCase`) the same way the FastAPI routes do. The domain
  never imports Prefect. Add an import-linter contract to enforce it.
- **Scheduled deployments replace the manual calls.** A cron schedule runs the
  discovery flow (search terms and countries from config) and the refresh
  flow for podcasts already stored.
- **Batch the work.** One task handles a few hundred podcasts and calls a bulk
  upsert. That keeps the tracked task runs in the thousands per day instead of
  one per item.
- **Built-in reliability.** Prefect gives retries, timeouts, run history and a
  UI. Its concurrency and rate limits, shared across workers, enforce the
  iTunes limit (about 20 requests/min) and a limit per feed host.
- **Runs on ECS.** A Prefect ECS work pool starts each flow run as a Fargate
  task. Secrets stay in Secrets Manager and are injected as environment
  variables, not stored in Prefect Blocks, so `Settings` remains the single
  source of configuration.
- **The API stops doing the work.** The ingest endpoints trigger a Prefect
  deployment run and answer `202` with the flow run id. The run's state
  replaces a hand-made `/jobs/{id}` endpoint.

**Millions of episodes, polled continuously: Prefect + SQS.**

At this volume, tracking every feed fetch as a Prefect task would overload the
Prefect server. Prefect keeps the scheduling and coordination, and SQS carries
the per-item work.

- **Prefect handles:** schedules, discovery, backfills, the periodic "find
  feeds that are due and push them to SQS" pass, and manual reruns.
- **SQS and worker services handle:** fetching feeds, upserting episodes and
  processing artwork. Each queue has its own `worker --queue=...` ECS service
  that scales on queue depth.
- **SQS guarantees.**
  - Each queue has a dead-letter queue for messages that keep failing.
  - The visibility timeout redelivers the message a crashed worker was
    holding.
  - Redelivery is safe because every write is an idempotent upsert keyed by
    id (see [Design decisions](#design-decisions)).

### Migrations as their own step

Today `connect_to_mongo()` (`app/infrastructure/db/mongo/database.py`) calls
`init_beanie`, which creates the indexes every time the app starts. On a large
collection an index build is slow, it holds up the rollout, and every new task
races to run it.

- **A `migrate` task runs first.** It creates the indexes and runs any data
  migrations, then exits. If it fails, the deploy stops and the running
  version keeps serving.
- **The app starts without building indexes.** It only connects and
  registers the document models.
- **Expand/contract schema changes.** Old and new tasks run side by side
  during a rollout, so a change never breaks the version still running:
  1. Expand: add the new field or index.
  2. Deploy code that reads both the old and the new shape.
  3. Backfill the existing documents.
  4. Contract: remove the old shape in a later release.

### Rollout

**CI pipeline.** It currently runs only pytest.

- **Add quality checks.** Add `ruff`, `mypy` and `lint-imports` to
  `.github/workflows/tests.yml`.
- **Build once.** On merge to `main`, build the image, scan it with Trivy, and
  push it to ECR tagged with the git SHA.
- **Promote the same image.** It is deployed to staging first. After the
  smoke tests pass, a manual approval promotes that same image to production.

**ECS rolling update.**

- **Keep full capacity.** Set `minimumHealthyPercent=100` and
  `maximumPercent=200`. New tasks start next to the old ones and only receive
  traffic once the readiness check passes. Old tasks are then drained.
- **Automatic rollback.** The ECS deployment circuit breaker rolls back when
  new tasks keep failing to become healthy. CloudWatch alarms on the 5xx rate
  and latency also roll the deployment back.
- **Manual rollback** means redeploying the previous git SHA's image.
- **Graceful shutdown.** On SIGTERM, Uvicorn stops accepting connections and
  finishes in-flight requests within the task's `stopTimeout`.

### Artwork storage

`LocalArtworkStorage` writes images to the task's own disk. Fargate disks are
ephemeral and not shared between tasks, so images would be lost on every
deploy and missing on every other task.

- **S3 adapter.** Add an `S3ArtworkStorage` adapter behind the existing
  `ArtworkStorageInterface` and wire it in `infrastructure/api/dependencies/`.
  The domain doesn't change.
- **CloudFront** serves the images from S3.
- **Content-addressed keys.** Each image is stored under the sha256 of its
  bytes. Artwork shared by many shows is stored once, and an image whose bytes
  haven't changed skips palette extraction entirely.
- **Palette extraction in a process pool.** `PillowColorPaletteExtractor` uses
  `asyncio.to_thread`, which still competes for the GIL. A process pool keeps
  that CPU work from ever slowing down async I/O.

### Observability

`Logger` prints plain-text lines, plus a rotating file outside containers.
That's hard to search and can't be linked across requests.

- **Structured JSON logs** go to stdout, and ECS ships them to CloudWatch
  Logs. Every line carries the request and trace id.
- **OpenTelemetry traces.** Instrument FastAPI, httpx and pymongo, and export
  the traces through an AWS Distro for OpenTelemetry (ADOT) collector sidecar
  to X-Ray. One request can then be followed through the API, iTunes, the
  artwork download and the database.
