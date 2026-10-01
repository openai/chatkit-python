import asyncio
from collections.abc import AsyncIterator

import pytest

from chatkit.agents import _merge_generators


@pytest.mark.parametrize("exit_path", ["error", "cancel", "close", "exhausted"])
async def test_merge_generators_cleans_up_pending_reads(exit_path):
    started = asyncio.Event()
    cleaned = asyncio.Event()
    reads = []

    async def waiting() -> AsyncIterator[str]:
        reads.append(asyncio.current_task())
        started.set()
        try:
            await asyncio.Event().wait()
            yield "unused"
        finally:
            # Cleanup may itself require an event-loop turn.
            await asyncio.sleep(0)
            cleaned.set()

    async def source() -> AsyncIterator[str]:
        await started.wait()
        if exit_path == "error":
            raise ValueError("source failed")
        if exit_path == "exhausted":
            return
        if exit_path == "cancel":
            await asyncio.Event().wait()
        yield "first"

    merged = _merge_generators(source(), waiting())
    next_item = asyncio.ensure_future(anext(merged))
    try:
        await started.wait()
        if exit_path == "cancel":
            next_item.cancel()
            with pytest.raises(asyncio.CancelledError):
                await next_item
        elif exit_path == "error":
            with pytest.raises(ValueError, match="source failed"):
                await next_item
        elif exit_path == "exhausted":
            with pytest.raises(StopAsyncIteration):
                await next_item
        else:
            assert await next_item == "first"
            await merged.aclose()
        assert cleaned.is_set()
        assert all(task.done() for task in reads)
    finally:
        # Keep the failing baseline test from leaking its own tasks.
        for task in reads:
            task.cancel()
        await asyncio.gather(*reads, return_exceptions=True)
        await merged.aclose()
