from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx


@asynccontextmanager
async def use_http_client(
    client: httpx.AsyncClient | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """
    Yield the client an HTTP adapter should send its request with.

    Args:
        client: Shared client owned by the app, kept open on exit. When None, a
            short-lived client is opened and closed on exit instead.
        transport: Transport of the short-lived client, used by tests to stub
            responses. Ignored when a shared client is given.

    Yields:
        The shared client, or the short-lived one.
    """
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(transport=transport) as own_client:
        yield own_client
