# -*- coding: utf-8 -*-
"""Read and fill the Aztek v2 Product form.

This first slice is deliberately read-only: it harvests the Product page's
current Currency and Category options and never clicks the create button.
"""
from __future__ import annotations

import re

from playwright.async_api import async_playwright

import aztek_core as core
from web import browser_launch
from web.search_runner import to_web_url


OPTION_KINDS = frozenset({'currencies', 'categories'})


def product_create_url(game):
    return to_web_url(core.build_url(game, 'shop/products/create'))


def _clean_option_rows(rows):
    """Normalize live ``<option>`` rows without inventing a catalog."""
    output = []
    seen = set()
    for row in rows or ():
        option_id = str((row or {}).get('value') or '').strip()
        text = str((row or {}).get('text') or '').strip()
        if not option_id or not text:
            continue
        slug = ''
        label = text
        if ' - ' in text:
            possible, remainder = text.split(' - ', 1)
            if re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', possible.strip()):
                slug = possible.strip()
                label = remainder.strip()
        key = (option_id, slug, label)
        if key in seen:
            continue
        seen.add(key)
        output.append({'id': option_id, 'slug': slug, 'label': label})
    return output


async def _read_options(select):
    rows = await select.locator('option').evaluate_all(
        """nodes => nodes.map(node => ({
          value: node.value || '',
          text: (node.textContent || '').trim()
        }))""")
    return _clean_option_rows(rows)


async def _category_select(page):
    selectors = (
        'xpath=//label[contains(normalize-space(.),"หมวดหมู่")]'
        '/following::select[1]',
        'xpath=//label[contains(normalize-space(.),"Category")]'
        '/following::select[1]',
    )
    for selector in selectors:
        select = page.locator(selector).first
        if await select.count():
            return select
    return None


async def _currency_select(page):
    price = page.locator(
        'input[name="prices.0.original_price"]').first
    if not await price.count():
        add = page.locator(
            'button:has-text("เพิ่มสกุลเงิน"),'
            'button:has-text("เพิ่มราคา"),'
            'button:has-text("Add Currency")').first
        if await add.count():
            await add.click()
            await price.wait_for(state='attached', timeout=8000)
    if not await price.count():
        return None
    wrapper = price.locator(
        'xpath=ancestor::*[.//select][1]').first
    select = wrapper.locator('select').first
    return select if await select.count() else None


async def _harvest_product_options(page, wanted):
    options = {}
    if 'categories' in wanted:
        select = await _category_select(page)
        options['categories'] = (
            await _read_options(select) if select is not None else [])
    if 'currencies' in wanted:
        select = await _currency_select(page)
        options['currencies'] = (
            await _read_options(select) if select is not None else [])
    return options


async def fetch_options(game, storage_state, kinds):
    """Read requested live Product options and leave without submitting."""
    wanted = set(kinds or ()) & OPTION_KINDS
    url = product_create_url(game)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            **browser_launch.launch_kwargs(False))
        context = await browser.new_context(
            **browser_launch.context_kwargs(
                False, storage_state=storage_state))
        page = await context.new_page()
        try:
            await page.goto(
                url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2500)
            if any(part in page.url.lower()
                   for part in ('/login', '/signin')):
                raise RuntimeError('Aztek session expired')
            return await _harvest_product_options(page, wanted)
        finally:
            await context.close()
            await browser.close()
