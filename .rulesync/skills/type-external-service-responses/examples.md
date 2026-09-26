# Examples — type external service responses

## Authentik: capture → scratch → Pydantic

**Provider:** `app/infrastructure/services/auth/identity_provider/authentik/authentik.py`  
**Method:** `send_groups_to_idp` → returns `list[dict]` today

### Step 2 — capture test

```python
@pytest.mark.asyncio
async def test_capture_create_group_response(authentik_provider: Authentik):
    with vcr.use_cassette("send_groups_to_idp_cassette.yaml"):
        result = await authentik_provider.send_groups_to_idp(
            groups_identity_provider=[
                GroupIdentityProvider(
                    name="vcr-test-group-2",
                    parent_group_id="",
                    attributes={"source": "vcr"},
                )
            ]
        )
    print(result[0])
```

### Step 3 — scratch file

`responses/create_group_response.py` — paste `print` output (single dict or first list element).

### Step 4 — Pydantic sketch

```python
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateGroupResponse(BaseModel):
    pk: str
    name: str
    is_superuser: bool = Field(..., alias="is_superuser")
    parent: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    # ... remaining keys from sample
```

Then in `send_groups_to_idp`:

```python
return [
    CreateGroupResponse.model_validate(json.loads(r.text))
    for r in responses
]
```

---

## Matriz: target shape (no capture step needed if cassette exists)

**Sample model:** `trades_history_response.py`

```python
class TradeResponse(BaseModel):
    symbol: str = Field(..., alias="symbol")
    size: float = Field(..., alias="size")
    # ...

class TradesHistoryResponse(BaseModel):
    status: str = Field(..., alias="status")
    trades: List[TradeResponse] = Field(..., alias="trades")

    @model_validator(mode="after")
    def filter_zero_size_trades(self) -> "TradesHistoryResponse":
        self.trades = [t for t in self.trades if t.size > 0]
        return self
```

**Provider usage:**

```python
res_validated: TradesHistoryResponse = TradesHistoryResponse.model_validate(res)
return self.mapper.map(res_validated, list[Trade])
```

---

## BCRA: flat JSON keys (no alias)

When the API already uses snake_case or Spanish keys matching Python fields, aliases are optional:

```python
class CurrencyQuoteByDateRangeResponse(BaseModel):
    status: int
    metadata: Metadata
    results: List[ResultItem]
```

See `app/infrastructure/providers/bcra_provider/responses/quote_by_date_range.py`.
