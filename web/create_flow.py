# -*- coding: utf-8 -*-
"""Shared final-create interaction for Aztek v2 forms."""


CONFIRM_CREATE_SELECTOR = (
    '[role="dialog"] button:text-is("ยืนยัน"), '
    '[role="alertdialog"] button:text-is("ยืนยัน"), '
    'button:text-is("ยืนยัน"):visible'
)


async def click_create_and_wait_for_write(
        page, create_button, response_predicate, *, timeout=20000,
        confirm_resolver=None, create_activator=None, confirm_activator=None):
    """Click Create, confirm its dialog when shown, and capture the write.

    Older Aztek pages write on the first click. Newer pages open a confirmation
    dialog and write only after its exact ``ยืนยัน`` button is clicked. The
    response listener starts before either click so both versions are safe.
    """
    response = None
    confirmed = False
    confirmation_error = None
    activation_error = None
    try:
        async with page.expect_response(
                response_predicate, timeout=timeout) as info:
            if create_activator is None:
                await create_button.click()
            else:
                try:
                    await create_activator(create_button)
                except Exception as exc:
                    activation_error = exc
                    raise
            if confirm_resolver is not None:
                # Migrated consumers validate their dialog contract. A write
                # already observed must not trigger another confirmation click.
                if not info.is_done():
                    try:
                        confirm = await confirm_resolver()
                        if confirm is not None and not info.is_done():
                            if confirm_activator is None:
                                await confirm.click(timeout=1000)
                                confirmed = True
                            else:
                                confirmed = await confirm_activator(confirm, lambda: not info.is_done())
                    except Exception as exc:
                        confirmation_error = exc
            else:
                # Other flows retain their existing behavior until migrated.
                confirm = page.locator(CONFIRM_CREATE_SELECTOR).first
                try:
                    await confirm.wait_for(state='visible', timeout=3000)
                except Exception:
                    pass
                else:
                    await confirm.click(timeout=8000)
                    confirmed = True
        response = await info.value
    except Exception:
        if activation_error is not None:
            raise activation_error
        if confirmation_error is not None:
            raise confirmation_error
        response = None
    return response, confirmed
