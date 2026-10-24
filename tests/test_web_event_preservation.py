"""Public Event fill preserves test-owned widgets, not a live DOM contract.

The Event tool does not send header editor/image data. These sentinels verify
that filling the supported fields leaves both language states untouched.
"""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.event_runner import EventBuilder
from test_web_event_id_first import CREATE_URLS, event_create_html, event_create_spec


def preserved_widgets(active):
    sections = []
    for title, kind in (('รูปภาพ', 'image'), ('รายละเอียด', 'details')):
        tabs, panels = [], []
        for language, label in (('th', 'ไทย'), ('en', 'English')):
            selected = language == active
            tabs.append('<button type="button" role="tab" aria-selected="%s">%s</button>'
                        % (str(selected).lower(), label))
            control = ('<input type="file" data-file="%s">' % language if kind == 'image'
                       else '<iframe data-editor="%s" srcdoc="<body contenteditable=\'true\'>'
                            '<p>keep-%s-details</p></body>"></iframe>' % (language, language))
            panels.append('<div role="tabpanel" %s>%s</div>'
                          % ('' if selected else 'hidden', control))
        sections.append('<section data-preserve-root><header><h2>%s</h2></header>'
                        '<div role="tablist">%s</div>%s</section>'
                        % (title, ''.join(tabs), ''.join(panels)))
    return ''.join(sections)


@pytest.mark.parametrize('url', CREATE_URLS)
@pytest.mark.parametrize('active', ('th', 'en'))
def test_event_fill_preserves_existing_header_images_editors_and_language(url, active):
    async def exercise():
        html = event_create_html().replace('</form>', preserved_widgets(active) + '</form>')
        unexpected = []
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(headless=True)
            try:
                context = await browser.new_context(service_workers='block')

                async def serve(route):
                    if route.request.method == 'GET' and route.request.url == url:
                        await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                    else:
                        unexpected.append((route.request.method, route.request.url))
                        await route.abort()

                await context.route('**/*', serve)
                page = await context.new_page()
                await page.goto(url)
                for language in ('th', 'en'):
                    await page.locator('[data-file="%s"]' % language).set_input_files({
                        'name': 'keep-%s.png' % language,
                        'mimeType': 'image/png', 'buffer': ('%s-bytes' % language).encode(),
                    })

                missing = await EventBuilder(lambda *_: None).fill_form(page, event_create_spec())
                actual = await page.evaluate('''() => ({
                    selected: [...document.querySelectorAll('[data-preserve-root] [role="tab"]')]
                        .map(el => el.getAttribute('aria-selected')),
                    editors: [...document.querySelectorAll('[data-editor]')]
                        .map(el => el.contentDocument.body.innerHTML),
                    files: [...document.querySelectorAll('[data-file]')]
                        .map(el => [...el.files].map(file => [file.name, file.size, file.type])),
                    header: ['slug','name_th','name_en'].map(id =>
                        document.querySelector('main form [id="'+id+'"]').value),
                    submits: document.querySelector('main form').dataset.submits || '0'
                })''')
            finally:
                await browser.close()
        return missing, actual, unexpected

    missing, actual, unexpected = asyncio.run(exercise())
    assert missing == []
    assert actual['header'] == ['requested-event', 'กิจกรรมที่ขอ', 'Requested event']
    assert actual['selected'] == (['true', 'false'] if active == 'th' else ['false', 'true']) * 2
    assert actual['editors'] == ['<p>keep-th-details</p>', '<p>keep-en-details</p>']
    assert actual['files'] == [[['keep-th.png', 8, 'image/png']], [['keep-en.png', 8, 'image/png']]]
    assert actual['submits'] == '0'
    assert unexpected == []
