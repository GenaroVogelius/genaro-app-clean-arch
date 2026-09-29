---
name: repository-writes-return-status
description: Ensures repository port methods that persist or mutate data return the domain `Status` Pydantic model (`app.domain.common.status.Status`), not a bare `StatusType` enum. Use when adding or editing repository interfaces under `app/domain/interfaces/repositories/`, their implementations under `app/infrastructure/**/repositories/`, or tests that assert outcomes of insert/update/delete/upsert/write flows.
targets:
  - '*'
---
# Repository writes return `Status`

## Rule

For **repository interfaces** (`app/domain/interfaces/repositories/**/*.py`) and their **implementations** (`app/infrastructure/**/repositories/**/*.py`):

- Any method that **writes**, **updates**, **deletes**, or otherwise **mutates persisted state** must be annotated to return **`Status`** and must return **`Status` instances** at runtime.

Use:

```python
from app.domain.common import Status, StatusType
```

- Success: `Status(status=StatusType.SUCCESS)` (optional `message` if useful).
- Failure: `Status(status=StatusType.ERROR, message="short human-readable reason")`.

Do **not** return **`StatusType`** alone from write-style methods (callers expect `Status.model_dump()`, `.status`, optional `.message`, etc.).

## Scope

**In scope** — methods whose primary job is persistence side-effects, for example names like `insert_*`, `update_*`, `delete_*`, `upsert_*`, `store_*`, `create_*` (when they write), `save_*`.

**Out of scope** — pure **reads** (`get_*`, `find_*`, `list_*`, `query_*`, …): those return domain types, DTOs, or collections as appropriate.

## Implementations

- Build `Status` with the normal constructor so validation runs: `Status(status=StatusType.SUCCESS)` / `Status(status=StatusType.ERROR, message=...)`.
- Map infrastructure failures (client errors, write exceptions) to `StatusType.ERROR` with a concise `message`.

## Tests

When asserting repository write results:

```python
result = await repository.some_write_method(...)
assert result.status == StatusType.SUCCESS
# or
assert result.status == StatusType.ERROR
```

Avoid `assert result == StatusType.SUCCESS`.

## Related project material

PostgreSQL repository examples that already follow this pattern: see `.cursor/skills/add-postgresql-repository/SKILL.md` (`store_*` → `Status`).
