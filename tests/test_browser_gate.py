from __future__ import annotations

import asyncio

from web.browser_gate import BrowserOperationGate
import pytest


def test_one_slot_does_not_overlap_browser_operations():
    """Removing the shared semaphore would let the second operation overlap."""
    async def scenario():
        gate = BrowserOperationGate(1)
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        order: list[str] = []

        async def first():
            async with gate.slot():
                order.append('first-enter')
                first_entered.set()
                await release_first.wait()
                order.append('first-exit')

        async def second():
            await first_entered.wait()
            async with gate.slot():
                order.append('second-enter')

        one = asyncio.create_task(first())
        two = asyncio.create_task(second())
        await first_entered.wait()
        await asyncio.sleep(0)

        assert order == ['first-enter']

        release_first.set()
        await asyncio.gather(one, two)
        assert order == ['first-enter', 'first-exit', 'second-enter']

    asyncio.run(scenario())


def test_update_waits_for_active_and_waiting_work_and_blocks_new_work():
    async def scenario():
        gate = BrowserOperationGate(1)
        async with gate.slot():
            assert gate.begin_update() is False
        assert gate.begin_update() is True
        with pytest.raises(RuntimeError, match='อัปเดต'):
            async with gate.slot():
                pytest.fail('must not start work during install preparation')
        gate.end_update()
        async with gate.slot():
            assert gate.begin_update() is False
    asyncio.run(scenario())
