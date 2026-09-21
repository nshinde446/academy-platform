"""Async entrypoint helper for Celery tasks.

Celery task bodies are synchronous; each wraps its async core in ``asyncio.run``,
which opens a *fresh* event loop per call. asyncpg connections are bound to the
loop that created them, so a pooled connection left over from a previous task run
gets handed to the next run's new loop and fails with::

    RuntimeError: got Future <...> attached to a different loop

Disposing the async engine's connection pool inside the same loop, before that
loop closes, guarantees every task run starts with connections created in its own
loop. Cheap: the worker fires these tasks minutes apart, not in a hot path.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.database.session import engine

T = TypeVar("T")


def run_task(coro_fn: Callable[[], Awaitable[T]]) -> T:
    """Run a task's async core in a new event loop, disposing DB connections after."""

    async def _wrapped() -> T:
        try:
            return await coro_fn()
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())
