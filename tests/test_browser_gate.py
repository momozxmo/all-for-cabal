from __future__ import annotations

import asyncio

from web.browser_gate import BrowserOperationGate


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
