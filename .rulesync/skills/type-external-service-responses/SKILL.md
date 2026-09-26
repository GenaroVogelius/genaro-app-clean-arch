---
name: type-external-service-responses
description: Captures real JSON from external providers, stores sample payloads under responses/, and refactors them into Pydantic models. Use when the user wants to type an external service response, add provider response models, capture API payloads from Authentik/Matriz/BCRA/etc., or scaffold `*Response` classes from live calls.
targets:
  - '*'
---
# Type external service responses

Workflow to go from untyped `dict` / raw HTTP JSON to validated Pydantic response models next to the provider.

## Prerequisites

- Identify the **provider class** (e.g. `app/infrastructure/services/auth/identity_provider/authentik/authentik.py`).
- Know which **method** returns the payload to type (one response file per distinct response shape).
- For live capture: service reachable, env vars set, and VCR configured if the test folder already uses it.

## Step 1 — Locate the provider

Open the infrastructure adapter that calls the external API. Note:

- Method name and return type today (often `dict`, `list[dict]`, or untyped).
- Whether tests already use VCR (`get_vcr_for_test(__file__)`).

Reference: `app/infrastructure/services/auth/identity_provider/authentik/authentik.py`, `app/infrastructure/providers/matriz_provider/matriz_provider.py`.

## Step 2 — Ad-hoc capture test

In the provider's `tests/` folder, add a temporary async test that calls the target method and **prints or logs the raw result**.

```python
@pytest.mark.asyncio
async def test_capture_<method>_response(<provider_fixture>: MyProvider):
    """
    Capture raw response for typing. Delete or convert after Step 4.

    IMPORTANT: Document any manual cleanup (duplicate resources, re-record notes).
    """
    with vcr.use_cassette("<method>_cassette.yaml"):  # omit if not using VCR
        result = await <provider_fixture>.<method>(...)
    print(result)  # or: import json; print(json.dumps(result, indent=2))
```

Run once with the project venv:

```bash
".venv/bin/python" -m pytest path/to/test_file.py::test_capture_<method>_response -s
```

Copy the printed JSON (or decode from the VCR cassette response body). Remove or replace this ad-hoc test when done.

Reference capture test: `app/infrastructure/services/auth/identity_provider/authentik/tests/test_authentik.py` (`test_run` pattern).

## Step 3 — Store the sample payload

Under the provider's `responses/` folder, create **one file per response shape** if it does not exist:

```
<provider_package>/
├── <provider>.py
├── responses/
│   ├── __init__.py          # export public models when ready
│   ├── create_group_response.py
│   └── ...
└── tests/
```

Paste the captured payload as a module-level literal (dict/list) or a short commented JSON excerpt. This file is the **source of truth for field names and types** during Step 4.

```python
# Scratch sample — replace with Pydantic in Step 4
create_group_response = {
    "pk": "...",
    "name": "vcr-test-group",
    ...
}
```

Examples:

- Scratch literal: `app/infrastructure/services/auth/identity_provider/authentik/responses/create_user_response.py`
- Target Pydantic: `app/infrastructure/providers/matriz_provider/responses/trades_history_response.py`

## Step 4 — Refactor to Pydantic

Replace the scratch literal with `BaseModel` classes named `{Feature}Response` (nested models for nested objects).

### Conventions

| Topic | Rule |
|-------|------|
| Field names | `snake_case` on the model; use `Field(..., alias="camelCase")` when the API uses camelCase |
| Nesting | One `BaseModel` per nested object; `List[ChildResponse]` for arrays |
| Optional fields | `Optional[T] = Field(None, alias="...")` only when the sample or API docs show null/absence |
| Domain cleanup | `@model_validator(mode="after")` for filters/normalization (see `TradesHistoryResponse`) |
| Doc sample | Optional block comment with a trimmed real JSON excerpt (`detail_account_response.py`) |

### Template

```python
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ChildResponse(BaseModel):
    symbol: str = Field(..., alias="symbol")
    size: float = Field(..., alias="size")


class MyFeatureResponse(BaseModel):
    status: str = Field(..., alias="status")
    items: List[ChildResponse] = Field(..., alias="items")

    @model_validator(mode="after")
    def normalize(self) -> "MyFeatureResponse":
        # optional: filter, coerce, defaults
        return self
```

### Wire into the provider

1. Change the method to parse with Pydantic:

   ```python
   raw = json.loads(r.text)  # or existing client return value
   return MyFeatureResponse.model_validate(raw)
   ```

   For list endpoints, validate each element or wrap in a list model.

2. Update return type hints from `dict` / `list[dict]` to the response model(s).

3. If a mapper exists, point it at the Pydantic model (see `matriz_provider.py` + `mapper.py`).

4. Export models from `responses/__init__.py` when the package exposes them.

5. Replace the ad-hoc capture test with a real test that asserts on typed fields (or keep VCR + `model_validate`).

Reference end state: `app/infrastructure/providers/matriz_provider/responses/trades_history_response.py`, usage in `matriz_provider.py`:

```python
res_validated: TradesHistoryResponse = TradesHistoryResponse.model_validate(res)
```

## Checklist

```
- [ ] Provider method identified
- [ ] Ad-hoc test run; raw JSON captured
- [ ] Sample saved under responses/<name>_response.py
- [ ] Pydantic models cover all keys used by mapper/callers
- [ ] Provider uses model_validate; types updated
- [ ] Ad-hoc capture test removed or promoted to permanent test
- [ ] responses/__init__.py exports updated (if applicable)
```

## Additional resources

- Matriz Pydantic examples: [examples.md](examples.md)
