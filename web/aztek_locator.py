"""Bounded, unambiguous lookup for verified Aztek controls.

Callers supply either a known stable ID or a documented no-ID selector,
never a fallback for an ID contract that failed.
"""
import json

from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class AztekLocatorError(RuntimeError):
    """An affected operation must stop; retrying another control is unsafe."""


async def require_control(scope, control, *, element_id=None, selector=None,
                          tags=(), roles=(), input_types=(), timeout=5000):
    if (element_id is None) == (selector is None):
        raise ValueError('Supply one stable ID or documented exception selector')
    query = '[id=%s]' % json.dumps(element_id) if element_id is not None else selector
    target = scope.locator(query)
    if await target.count() > 1:
        raise AztekLocatorError('Aztek: %s พบหลายตัวในขอบเขตเดียวกัน' % control)
    try:
        await target.wait_for(state='visible', timeout=timeout)
    except PlaywrightTimeoutError as error:
        raise AztekLocatorError('Aztek: %s หาไม่พบหรือยังไม่พร้อมใช้งาน' % control) from error
    if await target.count() != 1:
        raise AztekLocatorError('Aztek: %s พบหลายตัวในขอบเขตเดียวกัน' % control)
    shape = await target.evaluate('el => ({tag:el.tagName.toLowerCase(), role:el.getAttribute("role"), type:el.type})')
    if ((tags and shape['tag'] not in tags) or (roles and shape['role'] not in roles)
            or (input_types and shape['type'] not in input_types)):
        raise AztekLocatorError('Aztek: %s ชนิด control ไม่ตรงกับที่ตรวจไว้' % control)
    return target
