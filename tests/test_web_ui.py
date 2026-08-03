# -*- coding: utf-8 -*-
"""Static contract for the Item Finder browser UI."""
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(ROOT, 'web', 'static', 'index.html'), encoding='utf-8').read()
BUNDLES = open(os.path.join(ROOT, 'web', 'static', 'bundles.html'),
               encoding='utf-8').read()
EVENTS = open(os.path.join(ROOT, 'web', 'static', 'events.html'),
              encoding='utf-8').read()
ITEMCODES = open(os.path.join(ROOT, 'web', 'static', 'itemcodes.html'),
                 encoding='utf-8').read()
PRODUCTS = open(os.path.join(ROOT, 'web', 'static', 'products.html'),
                encoding='utf-8').read()
ACCOUNT = open(os.path.join(ROOT, 'web', 'static', 'account.html'),
               encoding='utf-8').read()
CONSOLE_JS = open(os.path.join(ROOT, 'web', 'static', 'console.js'),
                  encoding='utf-8').read()


def test_product_page_is_in_the_pipeline_and_shop_handoff():
    assert 'id="btnToProduct"' in HTML
    assert 'afc.productQueue.v1' in PRODUCTS
    for page in (HTML, BUNDLES, ITEMCODES, EVENTS, PRODUCTS):
        assert 'href="/products"' in page or 'id="btnToProduct"' in page


def test_created_bundle_ids_can_be_handed_to_products_by_source_key():
    assert 'workspace_id:state.workspaceId' in HTML
    assert 'afc.productBundleHandoff' in BUNDLES
    assert "source_group_key:row.group_key" in BUNDLES
    assert "sendMade('/products')" in BUNDLES
    assert 'function applyBundleHandoff(payload)' in PRODUCTS


def test_create_bundle_stands_on_its_own_page():
    """It is a tool, not a view of a search: a bundle can be started from
    nothing and its items typed in, with no workspace anywhere in sight."""
    for element_id in ('game', 'queuePick', 'btnQueueNew', 'btnQueueDel',
                       'btnAddRow', 'itemsTable', 'rewardList', 'btnPreview',
                       'btnCreateOne', 'btnCreateAll', 'bundleResults', 'log'):
        assert ('id="%s"' % element_id) in BUNDLES, element_id
    assert '/api/bundles/run' in BUNDLES
    assert '/api/workspaces/' not in BUNDLES


def test_item_finder_hands_bundles_over_rather_than_building_them():
    """Item Finder's part ends at the handoff — no create button lives there."""
    assert "window.location.href='/bundles'" in HTML
    assert 'afc.bundleHandoff' in HTML and 'afc.bundleHandoff' in BUNDLES
    assert '/api/bundles/run' not in HTML


def test_item_finder_can_send_selected_event_sheets_directly():
    assert 'id="btnToEvent"' in HTML
    assert '/events?game=' in HTML
    assert 'afc.eventHandoff' in HTML
    assert 'afc.eventHandoff' in EVENTS


def test_event_drafts_and_group_keys_survive_the_bundle_handoff():
    assert 'event_drafts:d.event_drafts||[]' in HTML
    for fragment in ('event_drafts', 'group_key', 'state.eventDrafts'):
        assert fragment in BUNDLES, fragment
    assert 'event_drafts:state.eventDrafts' in BUNDLES
    assert 'row.group_key' in EVENTS
    assert 'item.group_key === row.group_key' in EVENTS


def test_itemcode_drafts_survive_the_bundle_handoff():
    assert 'itemcode_drafts:d.itemcode_drafts||[]' in HTML
    for fragment in ('itemcode_drafts', 'state.itemcodeDrafts',
                     'ITEMCODE_DRAFT_KEY'):
        assert fragment in BUNDLES, fragment
    assert 'itemcode_drafts:state.itemcodeDrafts' in BUNDLES
    assert 'function applyBundleHandoff(payload)' in ITEMCODES


def test_the_queue_outlives_a_reload():
    """Half-built bundles must survive a refresh or a trip back to the search."""
    assert 'localStorage' in BUNDLES and 'afc.bundleQueue' in BUNDLES


def test_a_bundle_can_be_checked_against_the_document_without_leaving_the_page():
    """Going back to the results table means reading every group at once; the
    handful of rows in this bundle carry the document's own words instead."""
    for column in ('ชื่อในเอกสาร', 'พารามิเตอร์ที่เช็ค', 'คำอธิบายไอเทม'):
        assert column in BUNDLES, column
    for field in ('file_name', 'name_mismatch', 'params', 'doc_qty'):
        assert field in BUNDLES, field
    # Document rows that found no item are the most dangerous omission, so they
    # follow the bundles over rather than staying on the search page.
    assert 'missList' in BUNDLES and 'afc.notFound' in BUNDLES


def test_both_pages_agree_on_the_server_and_the_mode():
    """A bundle has to be created on the server its item ids came from, and the
    mode decides which document columns are worth reading."""
    for key in ("'afc.game'", "'afc.mode'"):
        assert key in HTML, key
        assert key in BUNDLES, key


def test_leaving_the_search_page_does_not_throw_the_search_away():
    """The workspace already lives on the server; the page just has to ask for
    it again instead of starting empty."""
    assert 'afc.workspaceId' in HTML
    assert 'restoreWorkspace' in HTML


def test_ui_exposes_desktop_item_finder_controls():
    required_ids = [
        'modeEvent', 'modeItemcode', 'modeShop', 'game', 'webAny', 'webYes',
        'webNo', 'templateFile', 'planFile', 'btnImportTemplate', 'btnImportPlan',
        'btnClearWorkspace', 'criteriaTable', 'btnSearch', 'btnStop', 'btnSelectAll',
        'btnClearSelection', 'btnCopySelected', 'btnCopyAll', 'btnExportXlsx',
        'btnExportCsv', 'btnBundles', 'resultsTable', 'notFoundList', 'log',
        'btnClearLog', 'sheetDialog', 'bundleDialog', 'btnBundleOpen',
    ]
    for element_id in required_ids:
        assert ('id="%s"' % element_id) in HTML, element_id


def test_ui_uses_workspace_api_and_handles_regroup_reset():
    required_fragments = [
        '/api/import-template', '/api/import-plan', '/api/import-plan/apply',
        '/api/workspaces/', '/ws/search', 'workspace_id', 'reset_results',
        'selected_indexes', 'navigator.clipboard',
    ]
    for fragment in required_fragments:
        assert fragment in HTML, fragment
    use_workspace = HTML.split('function useWorkspace(data)', 1)[1].split('async function upload', 1)[0]
    assert 'resetResults()' in use_workspace
    assert 'renderNotFound(data.not_found||[])' in use_workspace


def test_ui_has_all_result_columns_and_shop_description():
    for label in ('Aztek ID', 'ชื่อในเว็บ', 'ชื่อในไฟล์', 'พารามิเตอร์ที่เช็ค',
                  'กลุ่ม / ตาราง', 'คำอธิบายไอเทม'):
        assert label in HTML, label


def test_item_finder_header_has_identity_connection_and_logout():
    for element_id in ('currentUser', 'aztekStatus', 'btnAccount', 'btnLogout'):
        assert ('id="%s"' % element_id) in HTML, element_id
    for fragment in (
        '/api/auth/me', '/api/aztek/status', '/api/auth/logout', 'apiFetch',
        'aztek_session_required', 'aztek_session_expired', 'aztekConnected',
    ):
        assert fragment in HTML, fragment
    # An expired web session must bounce to the login page, not fail silently.
    assert "window.location.replace('/login')" in HTML


def test_local_mode_contract_keeps_aztek_link_and_hides_hosted_auth():
    for page in (HTML, BUNDLES, ITEMCODES, EVENTS):
        assert 'data-hosted-auth' in page
        assert 'data-account-link' in page
    assert 'applyRuntimeMode' in HTML
    assert 'applyRuntimeMode' in BUNDLES
    assert 'applyRuntimeMode' in CONSOLE_JS
    assert ACCOUNT.count('data-hosted-auth') == 3
    assert 'applyRuntimeMode(data)' in ACCOUNT


def test_login_and_account_pages_use_the_approved_auth_api_contract_safely():
    static_dir = os.path.join(ROOT, 'web', 'static')
    login_path = os.path.join(static_dir, 'login.html')
    account_path = os.path.join(static_dir, 'account.html')

    assert os.path.exists(login_path), login_path
    assert os.path.exists(account_path), account_path
    login_html = open(login_path, encoding='utf-8').read()
    account_html = open(account_path, encoding='utf-8').read()

    for fragment in (
        'loginForm', 'username', 'password', '/api/auth/login',
        'JSON.stringify({username,password})', 'textContent',
    ):
        assert fragment in login_html, fragment
    for fragment in (
        '/api/auth/me', '/api/auth/change-password', '/api/auth/logout',
        'changePasswordForm', 'current_password', 'new_password',
        'logoutButton', 'textContent',
        # Real Aztek connection UI (replaces the earlier placeholder).
        '/api/aztek/pairing-token', 'pairingToken', '/api/aztek/status',
        '/api/aztek/session', 'pairingCountdown',
    ):
        assert fragment in account_html, fragment
    for html in (login_html, account_html):
        assert 'innerHTML' not in html
        assert 'insertAdjacentHTML' not in html


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print('ALL PASS (%d)' % len(tests))
