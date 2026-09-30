"""Exercise checkbox-to-queue handoffs through the real UI and HTTP API."""
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

from web.workspaces import WorkspaceRepository


@pytest.fixture
def finder_page(client, member, test_database, request):
    scoped = getattr(request, 'param', '')
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'selection.xlsx')
        workspace.game = 'CabalPC TH'
        workspace.results = [
            {'aztek_id': '100', 'item_name': 'First prize',
             'item_kind': '1', 'item_option': '0', 'duration_index': '0',
             'sources': ['Demo'], 'group_keys': ['demo']},
            {'aztek_id': '200', 'item_name': 'Second prize',
             'item_kind': '2', 'item_option': '0', 'duration_index': '0',
             'sources': ['Demo'], 'group_keys': ['demo']},
        ]
        if scoped == 'shared':
            workspace.results[0]['sources'] = ['G1']
            workspace.results[0]['group_keys'] = ['G1']
            workspace.results[1] = {
                **workspace.results[0], 'sources': ['G2'], 'group_keys': ['G2'],
            }
            workspace.results.append({
                'aztek_id': '200', 'item_name': 'Second prize',
                'item_kind': '2', 'item_option': '0', 'duration_index': '0',
                'sources': ['G2'], 'group_keys': ['G2'],
            })
            workspace.occurrences = [
                {'kind': '1', 'opt': '0', 'dur': '0', 'sources': ['G1']},
                {'kind': '1', 'opt': '0', 'dur': '0', 'sources': ['G2']},
                {'kind': '2', 'opt': '0', 'dur': '0', 'sources': ['G2']},
            ]
        elif scoped:
            workspace.results[0]['sources'] = ['Other']
            workspace.results[0]['group_keys'] = ['other']
            workspace.results.append({
                'aztek_id': '300', 'item_name': 'Third prize',
                'item_kind': '3', 'item_option': '0', 'duration_index': '0',
                'sources': ['Demo'], 'group_keys': ['demo'],
            })
        workspace_id = workspace.id

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        # Only external font requests are blocked. HTML, scripts, API selection
        # and Bundle construction all run unchanged against the real app.
        context.route('https://**', lambda route: route.abort())

        def serve_app(route):
            request = route.request
            url = urlsplit(request.url)
            response = client.request(
                request.method, url.path + ('?' + url.query if url.query else ''),
                content=request.post_data_buffer,
                headers={'Content-Type': request.headers.get(
                    'content-type', 'application/json')},
            )
            route.fulfill(
                status=response.status_code, body=response.content,
                content_type=response.headers.get('content-type', 'text/plain'),
            )

        context.route('http://tool.test/**', serve_app)
        context.add_init_script(
            "localStorage.setItem('afc.workspaceId', %r)" % workspace_id)
        page = context.new_page()
        url = 'http://tool.test/'
        if scoped and scoped != 'shared':
            url += '?workspace_id=%s&source_group_key=%s' % (workspace_id, scoped)
        page.goto(url, wait_until='domcontentloaded')
        page.locator('#resultsTable input.pick').nth(1).wait_for()
        yield page
        context.close()
        browser.close()


@pytest.mark.parametrize('width', [1280, 390])
def test_selected_handoff_excludes_unchecked_prizes(finder_page, width):
    """Dropping selected_indexes must add the unchecked prize and fail this."""
    page = finder_page
    page.set_viewport_size({'width': width, 'height': 900})
    checkbox = page.locator('#resultsTable input.pick').nth(1)
    checkbox.focus()
    checkbox.press('Space')
    page.locator('#btnBundleOpen').focus()
    page.locator('#btnBundleOpen').press('Enter')
    page.wait_for_url('http://tool.test/bundles')
    page.locator('#itemsTable tbody tr').first.wait_for()

    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['200']


def test_selected_action_requires_a_selection_and_counts_checked_rows(finder_page):
    page = finder_page
    selected = page.locator('#btnBundleOpen')
    assert selected.is_disabled()
    assert '(0)' in selected.inner_text()
    assert page.locator('#btnBundleAll').is_enabled()
    assert '(2)' in page.locator('#btnBundleAll').inner_text()

    page.locator('#resultsTable input.pick').first.check()
    assert selected.is_enabled()
    assert '(1)' in selected.inner_text()
    page.locator('#btnSelectAll').click()
    assert '(2)' in selected.inner_text()
    page.locator('#btnClearSelection').click()
    assert selected.is_disabled()
    assert '(0)' in selected.inner_text()


@pytest.mark.parametrize('checked', [False, True])
def test_send_all_ignores_checkbox_selection(finder_page, checked):
    page = finder_page
    if checked:
        page.locator('#resultsTable input.pick').nth(1).check()
    page.locator('#btnBundleAll').click()
    page.wait_for_url('http://tool.test/bundles')
    page.locator('#itemsTable tbody tr').first.wait_for()

    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['100', '200']


@pytest.mark.parametrize('finder_page', ['shared'], indirect=True)
def test_send_all_keeps_shared_items_in_every_bundle(finder_page):
    page = finder_page
    page.locator('#resultsTable input.pick').nth(1).check()
    page.locator('#btnBundleAll').click()
    page.wait_for_url('http://tool.test/bundles')
    page.locator('#itemsTable tbody tr').first.wait_for()
    picker = page.locator('#queuePick')
    options = picker.locator('option').evaluate_all(
        '(options) => options.map(option => option.value)')
    assert len(options) == 2
    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['100']
    picker.select_option(options[1])
    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['100', '200']


@pytest.mark.parametrize('finder_page', ['demo'], indirect=True)
def test_selected_handoff_uses_visible_group_indexes(finder_page):
    """A scoped view's first row is not the workspace's first row."""
    page = finder_page
    assert page.locator('#resultsTable tbody tr').count() == 2
    page.locator('#resultsTable input.pick').first.check()
    page.locator('#btnBundleOpen').click()
    page.wait_for_url('http://tool.test/bundles')
    page.locator('#itemsTable tbody tr').first.wait_for()

    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['200']


@pytest.mark.parametrize('finder_page', ['demo'], indirect=True)
def test_send_all_in_product_view_stays_within_the_visible_group(finder_page):
    page = finder_page
    page.locator('#btnBundleAll').click()
    page.wait_for_url('http://tool.test/bundles')
    page.locator('#itemsTable tbody tr').first.wait_for()
    assert page.locator('#queuePick option').count() == 1
    assert page.locator('#itemsTable tbody tr td:nth-child(2) input').evaluate_all(
        '(inputs) => inputs.map(input => input.value)') == ['200', '300']


@pytest.mark.parametrize('finder_page', ['demo'], indirect=True)
def test_bundle_review_uses_the_same_visible_selection(finder_page):
    page = finder_page
    page.locator('#resultsTable input.pick').first.check()
    page.locator('#btnBundles').click()
    page.locator('#bundleDialog[open]').wait_for()
    assert page.locator('#bundleList td.id').all_text_contents() == ['200']
