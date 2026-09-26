# genaro-app

Backend API built with FastAPI following Clean Architecture + DDD.

## Stack

- **FastAPI** + Uvicorn
- **MongoDB** (Beanie / Motor)
- **slowapi** rate limiting
- **uv** for dependency management (Python 3.13+)
- **pytest**, **mypy**, **import-linter**

## Project structure

```
app/
├── config/           # Pydantic Settings
├── domain/           # Business core — must never import infrastructure
│   ├── aggregates/   # Entities / aggregates
│   ├── interfaces/   # Ports (repositories, services, logger, mapper, presenters)
│   ├── use_cases/    # Application logic (async def execute)
│   ├── services/     # Domain services
│   ├── enums/
│   ├── validations/
│   └── simple_entities/  # Status, ...
└── infrastructure/   # Adapters
    ├── api/          # FastAPI routes + request/response schemas
    ├── db/mongo/     # Beanie documents + repositories (auto-discovered)
    ├── mapper/       # GlobalMapper base
    ├── providers/    # External APIs
    ├── presenters/
    ├── services/
    ├── logger/
    └── utils/
```

`Item` is a minimal example slice (aggregate → port → use cases → Mongo repository → routes) to copy when adding new features.

## Setup

```bash
uv sync
source .venv/bin/activate
```

## Running

With Podman (app + MongoDB):

```bash
cp podman/local/.env.example podman/local/.env
podman compose -f podman/local/compose.local.yml up -d
```

On the host (MongoDB from compose):

```bash
podman compose -f podman/local/compose.local.yml up -d mongodb
MONGODB_URL="mongodb://admin:password123@localhost:27017/genaro-app-mongodb?authSource=admin" \
  uvicorn app.main:app --reload
```

Docs at http://localhost:8000/docs. Endpoints: `GET /api/health`, `POST /api/items`, `GET /api/items/{item_id}`.

## Checks

```bash
pytest
mypy app
lint-imports
```


## RulesSync

Rulesync turns a unified ruleset into tool-native formats so teams stop duplicating instructions across multiple AI assistants.

Instalation:
pnpm install -g rulesync

To import rules from cursor to rulesync
rulesync import --targets cursor

to export rules from rulesync into claude
rulesync generate --targets claudecode
rulesync generate --targets cursor

See more on https://rulesync.dyoshikawa.com/



<!-- TODO  -->
<!-- VER SI PROVIDER DOMAIN ENTITIES Y USE CASE ABSTRACTIONS que estan en rules estan bien. -->