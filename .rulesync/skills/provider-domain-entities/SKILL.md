---
name: provider-domain-entities
description: Ensures provider adapters under `app/infrastructure/providers/` return domain entities (never raw `dict`, `list[dict]`, `Any`, or transport payloads) by converting external responses through an injected mapper (`GlobalMapper` subclass with `@maps(...)` registrations, typed as `MapperInterface`). Use when creating or editing any `*provider.py` file (excluding `test_*` files), when adding a new public provider method, or when integrating a new external API.
targets:
  - '*'
---
# Provider return contract

When creating or editing a file matching `*provider.py`, apply this only if the filename does not start with `test`.

## Domain entities only

- Public methods of provider objects must return domain entities or collections of domain entities.
- Do not return raw provider responses such as `dict`, `list[dict]`, `Any`, or transport-specific payloads.
- Keep external response shape handling inside the infrastructure provider layer.

## Mapper as bridge

- Use a mapper to convert raw responses into domain entities. Mappers subclass `GlobalMapper` (`app/infrastructure/mapper/global_mapper.py`) and register conversions with `@maps(SourceType, TargetType)`.
- Inject the mapper into the provider typed as `MapperInterface` and call `self._mapper.map(raw, Entity)` / `self._mapper.map_list(raw_list, Entity)`.
- Keep mapping centralized in mapper classes to avoid duplicated transformation logic.

## Provider shape

```python
class BondMapper(GlobalMapper):
    @maps(BondResponse, Bond)
    def response_to_bond(self, response: BondResponse) -> Bond:
        return Bond(ticker=response.symbol, price=response.last_price)


class ExampleProvider(ExampleProviderInterface):
    def __init__(self, client: ExampleClient, mapper: MapperInterface) -> None:
        self._client = client
        self._mapper = mapper

    async def get_bonds(self) -> list[Bond]:
        raw_response = await self._client.fetch_bonds()
        return self._mapper.map_list(raw_response, Bond)
```

## What to avoid

```python
class ExampleProvider(ExampleProviderInterface):
    async def get_bonds(self) -> list[dict]:
        raw_response = await self._client.fetch_bonds()
        return raw_response
```

## Reference

`app/infrastructure/db/mongo/repositories/item_repository/item_mapper.py` is the reference mapper style (`ItemMapper(GlobalMapper)` with `@maps` registrations). To type raw provider payloads before mapping, see the `type-external-service-responses` skill.
