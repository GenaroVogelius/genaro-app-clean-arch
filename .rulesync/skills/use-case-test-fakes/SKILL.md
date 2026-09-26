---
name: use-case-test-fakes
description: Writes domain use case unit tests using test doubles (Fake classes) that implement injected port interfaces, record calls and arguments, and assert behavior without infrastructure. Use when adding or editing tests under `app/domain/use_cases/`, when the user asks for use case tests, fakes, mocks, or dependency-injected collaborators, or when mirroring patterns from existing `test_*_use_case.py` files next to a use case.
targets:
  - '*'
---
# Use case tests with Fake ports

## Placement

- Put the test module **next to the use case** it covers: `test_<use_case_snake_case>.py` in the same package as `<use_case_snake_case>.py` (same pattern as `upsert_currency_use_case` / `insert_currency_quotes_use_case`).
- Import the use case from its concrete module path (as in production wiring from the composition root is not under test here).

## Pattern

1. **Fakes implement the same abstractions** the use case constructor takes (`*Interface`, `*RepositoryInterface`, ABC ports from `app/domain/interfaces/...`). Name them `Fake<Role>` (e.g. `FakeQuoteCurrencyWriter`, `FakeCurrencyRepository`).
2. **Inject fakes** when constructing the use case: `UseCase(repository=fake_repo, provider=fake_provider)`.
3. **Record what matters**: store inbound arguments in lists (`insert_calls`, `get_quotes_params`, `store_calls`) or counters so tests assert orchestration, not I/O.
4. **Unused protocol methods**: implement with `raise NotImplementedError()` and add `# type: ignore[override]` on that stub if the type checker complains, **only** when the use case never calls them.
5. **Async**: mark tests with `@pytest.mark.asyncio` and `async def` when `execute` is async.
6. **Domain helpers**: small module-level factories for repetitive aggregates (e.g. `def currency(...) -> Currency`) to keep tests readable; build real domain types, not dicts.

## Assertions

- Prefer asserting **observable interactions**: which port was called, with what params, how many times, and final domain payloads passed to the next layer.
- For error paths, `pytest.raises` and assert **no** side effects on fakes (e.g. repository list still empty).

## References in this repo

- `app/domain/use_cases/store/upsert_currency_use_case/test_upsert_currency_use_case.py` — two fakes, call counting, list capture.
- `app/domain/use_cases/store/quote_use_case/insert_currency_quotes_use_case/test_insert_currency_quotes_use_case.py` — repository + provider fakes, params recording, happy path + `ValueError` when metadata is missing.

## Run tests

Use the project virtualenv: `".venv/bin/python" -m pytest -q path/to/test_*.py`.
