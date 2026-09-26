---
name: use-case-abstractions
description: Keeps use cases under `app/domain/use_cases/` depending on injected ports (repository/provider/service interfaces from `app/domain/interfaces/`) instead of concrete infrastructure, and passing domain entities (not dicts, ORM rows, or provider DTOs) between collaborators. Use when creating or editing any `*use_case.py` file, when adding a constructor dependency to a use case, when wiring a use case to a new repository/provider/service port, or when reviewing a use case for coupling to `app/infrastructure`.
targets:
  - '*'
---
# Use cases depend on abstractions and pass domain entities

When creating or editing a file matching `*use_case.py`:

## Depend on abstractions

- Inject and call **ports** (abstract repositories, provider/service interfaces) defined under `app/domain/interfaces/`—not concrete infrastructure classes (Tortoise/Beanie models, concrete repositories, HTTP clients, DB drivers, framework types).
- Constructor and method parameters for collaborators should use abstract types; wire concrete implementations only outside the use case (composition root, factories, DI).
- `app.domain` must never import from `app.infrastructure` (enforced by `import-linter check-contracts`).

```python
# BAD: concrete infrastructure in the use case
class CreateItemUseCase:
    def __init__(self, repository: MongoItemRepository, client: httpx.AsyncClient):
        ...

# GOOD: abstractions
class CreateItemUseCase:
    def __init__(self, repository: ItemWriterInterface):
        self._repository = repository
```

## Pass domain entities between objects

- **Inputs and outputs** between the use case and its collaborators should use **domain entities** (and domain value objects where applicable), not raw dicts, ORM rows, or provider-specific DTOs inside the use case body.
- Map infrastructure or external DTOs to domain types **at the edge** (repository/provider adapter via the `mapper/` layer), not in the middle of use case logic.

```python
# BAD: leaking transport/storage shapes through the use case
async def execute(self, payload: dict) -> list[dict]:
    rows = await self._repository.query_raw(payload["name"])
    return [{"n": r["name"]} for r in rows]

# GOOD: domain in, domain out
async def execute(self, item: Item) -> Status:
    return await self._repository.store_item(item)
```

## Reference

`app/domain/use_cases/item/create_item/create_item_use_case.py` depends on `ItemWriterInterface`, receives an `Item` aggregate, and returns a `Status`.

If an existing use case predates this pattern, refactor toward abstractions and domain types when you touch that file; do not expand coupling to concrete layers.
