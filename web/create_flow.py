# -*- coding: utf-8 -*-
"""Shared final-create interaction for Aztek v2 forms."""


CONFIRM_CREATE_SELECTOR = (
    '[role="dialog"] button:text-is("ยืนยัน"), '
    '[role="alertdialog"] button:text-is("ยืนยัน"), '
    'button:text-is("ยืนยัน"):visible'
)


async def click_create_and_wait_for_write(
        page, create_button, response_predicate, *, timeout=20000):
    """Click Create, confirm its dialog when shown, and capture the write.

    Older Aztek pages write on the first click. Newer pages open a confirmation
    dialog and write only after its exact ``ยืนยัน`` button is clicked. The
    response listener starts before either click so both versions are safe.
    """
    response = None
    confirmed = False
    try:
        async with page.expect_response(
                response_predicate, timeout=timeout) as info:
            await create_button.click()
            confirm = page.locator(CONFIRM_CREATE_SELECTOR).first
            try:
                await confirm.wait_for(state='visible', timeout=3000)
            except Exception:
                # Direct-write pages have no dialog; the first click is enough.
                pass
            else:
                await confirm.click(timeout=8000)
                confirmed = True
        response = await info.value
    except Exception:
        response = None
    return response, confirmed
