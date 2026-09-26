---
name: use-case-model-construct
description: Inside use cases under `app/domain/use_cases/`, build Pydantic "internal transfer objects" (typically `*Params` BaseModels passed to repositories/providers) with `Model.model_construct(...)` instead of `Model(...)`, because input validation has already run at the input boundary. Use when creating or editing any `*use_case.py` file, when reviewing a use case body, or when wiring a use case to a new repository/provider port and constructing a `Params` BaseModel to hand off to it.
targets:
  - '*'
---
# Use case internal transfer objects use `model_construct`

## Rule

Inside any file matching `app/domain/use_cases/**/*use_case.py`, when the use case instantiates a Pydantic `BaseModel` **only to transfer data to an outbound port** (repository, provider, service), build it with `Model.model_construct(...)`, not with `Model(...)`.

**Why**: validation already happens at the input boundary (Prefect flow, HTTP controller, CLI, scheduler) that builds the *incoming* `params` passed to `execute(...)`. Internal transfer objects re-pack already-trusted, already-typed data on its way out to a port, so re-running Pydantic validators on them is wasted work.

The reference implementation is `app/domain/use_cases/store/quote_use_case/insert_currency_quotes_use_case.py`.

## Scope

Applies to **internal transfer objects** — Pydantic models that the use case constructs itself to pass into a repository / provider / service method. These are usually classes whose name ends in `Params` and that are imported from `app/domain/interfaces/{repositories,providers,services}/...`.

Does **not** apply to:

- Domain **entities / aggregates / value objects** (`Quote`, `Currency`, `TickerId`, `Status`, ...): keep them validated, that is their job.
- Pydantic models built from **untrusted** data inside the use case (e.g. parsing a raw provider response, hydrating from a dict). Use the regular constructor so validators run.
- The `params` argument the use case **receives** from the outside — that is already a fully-validated instance.
- Call sites **outside** `app/domain/use_cases/` (flows, controllers, adapters). Those are the input boundary and must keep full validation via `Model(...)`.

## Example

Good — internal transfer object on the outbound side:

```python
async def execute(self, params: GetQuoteByDateRangeParams):
    quotes = await self.provider.get_quotes_currency_by_date_range(params=params)

    params_insert = InsertQuoteCurrencyByDateRangeParams.model_construct(
        currency=params.currency,
        quotes=quotes,
    )

    await self.repository.insert_quote_currency_by_date_range(params=params_insert)
```

Bad — runs Pydantic validators redundantly on already-validated data:

```python
params_insert = InsertQuoteCurrencyByDateRangeParams(
    currency=params.currency,
    quotes=quotes,
)
```

Also acceptable — inline at the call site (see `upsert_ticker_quotes_per_minute_use_case.py`):

```python
await self.repository.create_trades(
    params=CreateTradesParams.model_construct(
        symbol=params.ticker,
        market=params.market,
        trades=trades_history_domain_model,
    ),
)
```

## When editing a use case

1. Scan every Pydantic `Model(...)` call inside `execute` and any private methods.
2. For each call, ask: **"Is this Pydantic model an internal transfer object being passed to an outbound port?"**
   - Yes → switch to `Model.model_construct(...)`.
   - No (domain object, or built from raw/untrusted data) → leave the regular constructor.
3. Keep the **keyword-argument** style: `Model.model_construct(field=value, ...)`. Do not pass positional args; do not pass an unpacked dict — keeping kwargs preserves field-name visibility for the type checker and the reviewer.
4. Do **not** add `# type: ignore` or other suppressions. If `model_construct` complains, the call site itself is wrong (mismatched field name) — fix the call site, do not silence the error.
5. Do not touch the **definition** of the `*Params` class. Validators stay where they are; they will still run wherever the input boundary instantiates the model normally.

## Sweep checklist

When asked to apply this pattern across the codebase:

- [ ] List every file under `app/domain/use_cases/` matching `*use_case.py` (exclude `test_*.py`).
- [ ] In each, find every instantiation of a class imported from `app/domain/interfaces/...` whose name ends in `Params` (or another `BaseModel` used purely to call an outbound port).
- [ ] Confirm it is an internal transfer object per the rule above.
- [ ] Replace `Model(...)` with `Model.model_construct(...)`, keeping kwargs.
- [ ] Leave domain aggregates / value objects, untrusted-data hydration, and any call site outside `app/domain/use_cases/` untouched.
- [ ] After the sweep, re-read each modified file and verify the diff only contains `... .model_construct(` substitutions plus any necessary import changes (there usually are none — `model_construct` is a classmethod, no import required).
