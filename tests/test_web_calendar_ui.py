# -*- coding: utf-8 -*-
"""Browser-level regression tests for the shared 24-hour calendar."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'web' / 'static' / 'console.css'
JS = ROOT / 'web' / 'static' / 'console.js'
ITEMCODES = ROOT / 'web' / 'static' / 'itemcodes.html'
EVENTS = ROOT / 'web' / 'static' / 'events.html'
INDEX = ROOT / 'web' / 'static' / 'index.html'
BUNDLES = ROOT / 'web' / 'static' / 'bundles.html'
ACCOUNT = ROOT / 'web' / 'static' / 'account.html'


def _tool_page(browser, path):
    """Load a real tool page with its real shared script, without a web server."""
    html = path.read_text(encoding='utf-8')
    shared = JS.read_text(encoding='utf-8')
    html = html.replace(
        '<script src="/static/console.js"></script>',
        '<script>%s</script>' % shared,
    )
    page = browser.new_page()
    page.set_content(html, wait_until='domcontentloaded')
    page.wait_for_function("typeof slugForGame === 'function'")
    return page


def _choose_game(page, game):
    page.locator('#game').evaluate(
        """(select, game) => {
          if (![...select.options].some(option => option.value === game)) {
            select.add(new Option(game, game));
          }
          select.value = game;
          select.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        game,
    )


def _standalone_page(browser, path):
    page = browser.new_page()
    page.set_content(
        path.read_text(encoding='utf-8'),
        wait_until='domcontentloaded',
    )
    return page


def _bundle_page(context):
    """Serve the real Bundle page on one origin so localStorage can reload."""
    page = context.new_page()

    def fulfill(route):
        url = route.request.url
        if url == 'http://tool.test/bundles':
            route.fulfill(body=BUNDLES.read_text(encoding='utf-8'),
                          content_type='text/html')
        elif url.endswith('/static/console.css'):
            route.fulfill(body=CSS.read_text(encoding='utf-8'),
                          content_type='text/css')
        elif url.endswith('/api/auth/me'):
            route.fulfill(json={'username': 'local.owner', 'local_mode': True})
        elif url.endswith('/api/games'):
            route.fulfill(json={'games': ['CabalPC TH']})
        elif url.endswith('/api/aztek/status'):
            route.fulfill(json={'status': 'active'})
        else:
            route.fulfill(status=404, body='not found')

    page.route('**/*', fulfill)
    page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
    page.wait_for_function("typeof renderItems === 'function'")
    return page


def _itemcode_page(context, submitted):
    """Serve the real Item Code page with only its local API fixture."""
    page = context.new_page()

    def fulfill(route):
        url = route.request.url
        if url == 'http://tool.test/itemcodes':
            route.fulfill(body=ITEMCODES.read_text(encoding='utf-8'),
                          content_type='text/html')
        elif url.endswith('/static/console.css'):
            route.fulfill(body=CSS.read_text(encoding='utf-8'),
                          content_type='text/css')
        elif url.endswith('/static/console.js'):
            route.fulfill(body=JS.read_text(encoding='utf-8'),
                          content_type='text/javascript')
        elif url.endswith('/api/auth/me'):
            route.fulfill(json={'username': 'local.owner', 'local_mode': True})
        elif url.endswith('/api/games'):
            route.fulfill(json={'games': ['CabalM TH']})
        elif url.endswith('/api/aztek/status'):
            route.fulfill(json={'status': 'active'})
        elif url.endswith('/api/itemcodes/run'):
            payload = route.request.post_data_json
            submitted.append(payload)
            route.fulfill(json={
                'results': [
                    {'name': 'First Code', 'slug': payload['itemcodes'][0]['slug'],
                     'saved': True, 'made_id': '101', 'missing': [],
                     'error': None},
                    {'name': 'Second Code', 'slug': payload['itemcodes'][1]['slug'],
                     'saved': False, 'made_id': None, 'missing': [],
                     'error': 'bundle rejected'},
                ],
                'created': 1, 'planned': 2,
            })
        else:
            route.fulfill(status=404, body='not found')

    page.route('**/*', fulfill)
    page.goto('http://tool.test/itemcodes', wait_until='domcontentloaded')
    page.wait_for_function("typeof createThese === 'function'")
    return page


def test_local_mode_hides_hosted_auth_in_every_tool_header():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        pages = [
            _standalone_page(browser, INDEX),
            _standalone_page(browser, BUNDLES),
            _tool_page(browser, ITEMCODES),
            _tool_page(browser, EVENTS),
        ]

        for page in pages:
            page.evaluate("""applyRuntimeMode({
              username: 'local.owner', role: 'admin', local_mode: true
            })""")
            assert not page.locator('#btnLogout').is_visible()
            assert not page.locator('#currentUser').is_visible()
            account_link = page.locator('[data-account-link]')
            assert account_link.is_visible()
            assert account_link.inner_text() == 'เชื่อม Aztek'

        browser.close()


def test_local_mode_account_page_keeps_only_aztek_controls():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _standalone_page(browser, ACCOUNT)

        page.evaluate("""applyRuntimeMode({
          username: 'local.owner', role: 'admin', local_mode: true
        })""")

        hosted_sections = page.locator('[data-hosted-auth]')
        assert hosted_sections.count() == 2
        for index in range(hosted_sections.count()):
            assert not hosted_sections.nth(index).is_visible()
        assert page.locator('#localCaptureButton').is_visible()
        assert not page.locator('#bookmarklet').is_visible()
        assert not page.locator('#createPairingButton').is_visible()
        assert page.locator('#disconnectAztekButton').is_visible()
        browser.close()


def test_done_button_really_hides_the_calendar_popover():
    """A CSS display rule must not override the popover's hidden state."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<input id="when" class="dtpick" type="text">')
        page.add_style_tag(path=str(CSS))
        page.add_script_tag(path=str(JS))
        page.evaluate('attachPickers()')

        page.locator('#when').click()
        popover = page.locator('.dtpop')
        assert popover.is_visible()

        page.get_by_role('button', name='ตกลง').click()
        assert not popover.is_visible()
        browser.close()


def test_calendar_popover_is_not_clipped_by_its_card():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 420, 'height': 500})
        page.set_content('''
          <div class="card" style="width:360px;margin:24px">
            <div class="card-body">
              <input id="when" class="dtpick" type="text"
                     value="2026-07-31 00:00:00">
            </div>
          </div>
        ''')
        page.add_style_tag(path=str(CSS))
        page.add_script_tag(path=str(JS))
        page.evaluate('attachPickers()')
        page.locator('#when').click()

        visible_below_card = page.evaluate('''() => {
          const card = document.querySelector('.card').getBoundingClientRect();
          const pop = document.querySelector('.dtpop').getBoundingClientRect();
          const target = document.elementFromPoint(pop.left + 12, card.bottom + 12);
          return pop.bottom > card.bottom
            && !!target && document.querySelector('.dtpop').contains(target);
        }''')

        assert visible_below_card is True
        browser.close()


def test_bundle_quantity_accepts_more_than_one_typed_digit():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = _bundle_page(context)
        page.evaluate('''() => {
          state.queue = [{key: 'b1', name: 'Bundle 1', type: 'FIXED',
            deliver: true, rewards: [], items: [
              {id: '10', name: 'Item', qty: '1', tier: 'Common', rate: ''}
            ]}];
          state.active = 'b1';
          select('b1');
        }''')
        quantity = page.locator('#itemsTable tbody tr').first.locator(
            'input[type="number"]').first

        quantity.click()
        quantity.press('Control+A')
        page.keyboard.type('42')

        assert quantity.input_value() == '42'
        assert page.evaluate("current().items[0].qty") == '42'
        context.close()
        browser.close()


def test_bundle_random_tier_and_rate_are_reachable_in_an_800px_shop_table():
    """Shop/document columns must scroll instead of clipping the live controls."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 800, 'height': 1000})
        page = _bundle_page(context)
        page.evaluate('''() => {
          state.queue = [{key: 'shop-random', name: 'Shop RANDOM',
            type: 'RANDOM', deliver: true, rewards: [], items: [{
              id: '101', name: 'A very long Shop item name that cannot fit',
              qty: '51', tier: 'Rare', rate: '12.5', shared: false,
              file_name: 'Shop Plan.xlsx', doc_qty: '51',
              params: 'PLAYER_EXPERIENCE',
              desc: 'A long source description for the document column'
            }]}];
          state.active = 'shop-random';
          select('shop-random');
        }''')

        layout = page.evaluate('''() => {
          const wrapper = document.querySelector('#itemsTable').closest('.table-wrap');
          const tier = document.querySelector('#itemsTable tbody select');
          const rate = document.querySelector('#itemsTable tbody .rate-col input');
          const reveal = node => {
            const wrap = wrapper.getBoundingClientRect();
            let box = node.getBoundingClientRect();
            if (box.left < wrap.left) wrapper.scrollLeft += box.left - wrap.left;
            if (box.right > wrap.right) wrapper.scrollLeft += box.right - wrap.right;
            box = node.getBoundingClientRect();
            const point = document.elementFromPoint(
              box.left + Math.min(3, box.width / 2), box.top + box.height / 2);
            return box.left >= wrap.left - 1 && box.right <= wrap.right + 1
              && !!point && (point === node || node.contains(point));
          };
          return {
            hasHorizontalOverflow: wrapper.scrollWidth > wrapper.clientWidth,
            tierReachable: reveal(tier),
            rateReachable: reveal(rate)
          };
        }''')

        assert layout == {
            'hasHorizontalOverflow': True,
            'tierReachable': True,
            'rateReachable': True,
        }

        tier = page.locator('#itemsTable tbody select')
        rate = page.locator('#itemsTable tbody .rate-col input')
        tier.scroll_into_view_if_needed()
        tier.select_option('Epic')
        rate.scroll_into_view_if_needed()
        rate.fill('33.5')

        assert tier.input_value() == 'Epic'
        assert rate.input_value() == '33.5'
        assert page.evaluate(
            "[current().items[0].tier, current().items[0].rate]"
        ) == ['Epic', '33.5']
        context.close()
        browser.close()


def test_created_bundle_results_survive_leaving_and_returning_to_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = _bundle_page(context)
        page.evaluate('''() => {
          state.results = [{name: 'Made Bundle', saved: true, bundle_id: '90210',
            added: 2, total: 2, rewards_total: 0, rewards_added: 0}];
          state.made = [{name: 'Made Bundle', bundle_id: '90210',
            workspace_id: 'workspace-1', group: 'G1', group_key: 'g1'}];
          renderResults(state.results, false);
          document.getElementById('handoff').hidden = false;
          saveQueue();
        }''')
        page.close()

        restored = _bundle_page(context)
        restored.wait_for_timeout(50)

        assert restored.locator('#bundleResults tbody tr').count() == 1
        assert '90210' in restored.locator('#bundleResults').inner_text()
        assert restored.locator('#handoff').is_visible()
        assert restored.evaluate("state.made[0].bundle_id") == '90210'
        context.close()
        browser.close()


def test_generated_slugs_end_with_the_selected_server_without_duplicates():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_script_tag(path=str(JS))

        assert page.evaluate(
            "slugForGame('Summer Event', 'CabalM TH')"
        ) == 'summer-event-mth'
        assert page.evaluate(
            "slugForGame('Summer Event', 'CabalM SEA')"
        ) == 'summer-event-msea'
        assert page.evaluate(
            "slugForGame('Summer Event', 'CabalPC TH')"
        ) == 'summer-event-pcth'
        assert page.evaluate(
            "slugForGame('Summer Event', 'CabalPC SEA')"
        ) == 'summer-event-pcsea'
        assert page.evaluate(
            "slugForGame('summer-event-msea', 'CabalM SEA')"
        ) == 'summer-event-msea'
        browser.close()


def test_itemcode_slug_button_uses_the_selected_server():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        _choose_game(page, 'CabalPC TH')
        page.evaluate("select(queue.add(blankCode()).key)")

        page.locator('#nameEn').fill('Summer Event')
        page.locator('#btnSlug').click()

        assert page.locator('#slug').input_value() == 'summer-event-pcth'
        browser.close()


def test_imported_itemcode_slug_uses_the_selected_server_once():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        _choose_game(page, 'CabalM SEA')

        page.evaluate(
            "addDrafts([{name_th: 'Imported', slug: 'imported-code'}], 'test')"
        )
        assert page.evaluate("queue.current().slug") == 'imported-code-msea'

        page.evaluate(
            "addDrafts([{name_th: 'Ready', slug: 'ready-msea'}], 'test')"
        )
        assert page.evaluate("queue.current().slug") == 'ready-msea'
        browser.close()


def test_imported_itemcode_datetime_displays_a_space_instead_of_t():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)

        page.evaluate("""
          addDrafts([{
            name_th: 'Imported',
            start_time: '2026-07-26T00:00:00',
            end_time: '2026-08-31T23:59:59'
          }], 'test')
        """)

        assert page.locator('#startTime').input_value() == '2026-07-26 00:00:00'
        assert page.locator('#endTime').input_value() == '2026-08-31 23:59:59'
        browser.close()


def test_itemcode_blank_code_uses_bangkok_midnight_and_fills_both_names():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)

        entry = page.evaluate("blankCode('Fallback Name')")

        expected_start = datetime.now(ZoneInfo('Asia/Bangkok')).strftime(
            '%Y-%m-%d 00:00:00')
        assert entry['name_th'] == 'Fallback Name'
        assert entry['name_en'] == 'Fallback Name'
        assert entry['start_time'] == expected_start
        assert entry['limited'] is False
        assert (entry['quantity'], entry['remaining']) == ('', '')
        browser.close()


def test_itemcode_code_wide_limit_matches_aztek_layout_and_payload():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        page.evaluate("select(queue.add(blankCode('Manual')).key)")

        assert not page.locator('#itemLimited').is_checked()
        assert not page.locator('#itemLimitFields').is_visible()

        page.locator('#itemLimited').click()
        assert page.locator('#itemLimitFields').is_visible()
        columns = page.locator('#itemLimitFields').evaluate(
            "el => getComputedStyle(el).gridTemplateColumns.split(' ').length")
        assert columns == 2
        page.locator('#itemQuantity').fill('40')
        page.locator('#itemRemaining').fill('39')

        assert page.evaluate("queue.current().limited") is True
        manual = page.evaluate("jobFrom(queue.current())")
        assert (manual['limited'], manual['quantity'], manual['remaining']) \
            == (True, '40', '39')

        page.evaluate("""
          addDrafts([{
            name_th: 'Imported', name_en: 'Imported EN',
            limited: true, quantity: '25', remaining: '24'
          }], 'test')
        """)
        assert page.locator('#itemLimited').is_checked()
        assert page.locator('#itemLimitFields').is_visible()
        assert page.locator('#itemQuantity').input_value() == '25'
        assert page.locator('#itemRemaining').input_value() == '24'
        imported = page.evaluate("jobFrom(queue.current())")
        assert (imported['limited'], imported['quantity'], imported['remaining']) \
            == (True, '25', '24')
        browser.close()


def test_changing_game_does_not_rewrite_a_manual_itemcode_slug():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        _choose_game(page, 'CabalM TH')
        page.evaluate("select(queue.add(blankCode()).key)")
        page.locator('#slug').fill('operator-choice')

        _choose_game(page, 'CabalPC SEA')

        assert page.locator('#slug').input_value() == 'operator-choice'
        assert page.evaluate("queue.current().slug") == 'operator-choice'
        browser.close()


def test_event_slug_button_uses_the_selected_server():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        _choose_game(page, 'CabalM TH')
        page.evaluate("select(queue.add(blankEvent()).key)")

        page.locator('#nameEn').fill('Anniversary')
        page.locator('#btnSlug').click()

        assert page.locator('#slug').input_value() == 'anniversary-mth'
        browser.close()


def test_changing_game_does_not_rewrite_a_manual_event_slug():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        _choose_game(page, 'CabalM TH')
        page.evaluate("select(queue.add(blankEvent()).key)")
        page.locator('#slug').fill('manual-event')

        _choose_game(page, 'CabalPC SEA')

        assert page.locator('#slug').input_value() == 'manual-event'
        assert page.evaluate("queue.current().slug") == 'manual-event'
        browser.close()


def test_locked_eligibility_is_visible_on_event_and_itemcode_forms():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        event_page = _tool_page(browser, EVENTS)
        event_page.evaluate("select(queue.add(blankEvent()).key)")
        event_kind = event_page.locator('#kind')
        assert event_kind.is_visible()
        assert event_kind.is_disabled()
        assert event_kind.input_value() == 'WINNER'
        assert event_kind.locator('option').all_text_contents() == ['WINNER']

        itemcode_page = _tool_page(browser, ITEMCODES)
        itemcode_page.evaluate("select(queue.add(blankCode()).key)")
        itemcode_kind = itemcode_page.locator('#kind')
        assert itemcode_kind.is_visible()
        assert itemcode_kind.is_disabled()
        assert itemcode_kind.input_value() == 'ALL'
        assert itemcode_kind.locator('option').all_text_contents() == ['ALL']
        browser.close()


def test_item_finder_shows_only_the_handoff_for_the_selected_mode():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            INDEX.read_text(encoding='utf-8'), wait_until='domcontentloaded')
        page.wait_for_function("typeof applyMode === 'function'")
        page.evaluate("""state.modes = {
          event:{web_mode:'no',web_locked:false},
          itemcode:{web_mode:'no',web_locked:true},
          shop:{web_mode:'no',web_locked:false}
        }""")

        page.evaluate("applyMode('event', false)")
        assert page.locator('#webNo').is_checked()
        assert page.locator('input[name=webMode]:disabled').count() == 0
        assert page.locator('#btnToEvent').is_visible()
        assert not page.locator('#btnToItemCode').is_visible()
        assert not page.locator('#btnToProduct').is_visible()

        page.evaluate("applyMode('itemcode', false)")
        assert page.locator('#webNo').is_checked()
        assert page.locator('input[name=webMode]:disabled').count() == 3
        assert page.locator('#btnToItemCode').is_visible()
        assert not page.locator('#btnToEvent').is_visible()
        assert not page.locator('#btnToProduct').is_visible()

        page.evaluate("applyMode('shop', false)")
        assert page.locator('#webNo').is_checked()
        assert page.locator('input[name=webMode]:disabled').count() == 0
        assert not page.locator('#btnToItemCode').is_visible()
        assert not page.locator('#btnToEvent').is_visible()
        assert page.locator('#btnToProduct').is_visible()
        browser.close()


def test_event_page_imports_one_event_per_sheet_with_all_reward_sets():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        _choose_game(page, 'CabalPC TH')

        assert page.locator('#btnImport').count() == 1
        assert page.locator('#sheetDialog').count() == 1
        page.evaluate("""
          addDrafts([{
            sheet: 'Activity A', sheet_key: 'sheet-a',
            name_th: 'Summer Event', name_en: 'Summer Event',
            slug: 'summer-event', start_event: '2026-07-26T00:00:00',
            end_event: '', start_claim: '2026-07-26T00:00:00',
            end_claim: '', same_window: true,
            warnings: ['ไม่พบวันสิ้นสุด'],
            rewards: [
              {group_key: 'ga', group: 'Lucky Draw', name_th: 'Lucky Draw',
               name_en: 'Lucky Draw', bundle_id: ''},
              {group_key: 'gb', group: 'Participation', name_th: 'Participation',
               name_en: 'Participation', bundle_id: ''}
            ]
          }], 'test', 'CabalPC TH')
        """)

        assert page.evaluate("queue.items.length") == 1
        assert page.evaluate("queue.current().rewards.length") == 2
        assert page.evaluate("queue.current().slug") == 'summer-event-pcth'
        assert page.locator('#startEvent').input_value() == '2026-07-26 00:00:00'
        assert page.locator('#startClaim').input_value() == '2026-07-26 00:00:00'
        assert page.locator('#endEvent').input_value() == ''
        assert 'ไม่พบวันสิ้นสุด' in page.locator('#planWarnings').inner_text()
        browser.close()


def test_event_claim_window_keeps_a_space_when_it_is_mirrored():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        page.evaluate("""
          addDrafts([{
            name_th: 'Summer Event',
            start_event: '2026-07-28T00:00:00',
            end_event: '2026-08-31T22:59:59',
            start_claim: '',
            end_claim: '',
            same_window: false,
            rewards: [{name_th: 'Summer Event', name_en: 'Summer Event'}]
          }], 'test')
        """)

        page.locator('#sameWindow').check()

        assert page.locator('#startClaim').input_value() == \
            '2026-07-28 00:00:00'
        assert page.locator('#endClaim').input_value() == \
            '2026-08-31 22:59:59'
        browser.close()


def test_event_editor_uses_aztek_section_columns_and_collapses_on_small_screens():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        page.evaluate("select(queue.add(blankEvent()).key)")

        page.set_viewport_size({'width': 1400, 'height': 1000})
        desktop = page.evaluate("""
          () => {
            const general = document.querySelector(
              '[data-event-section="general"]');
            const activity = document.querySelector(
              '[data-event-section="activity-window"]');
            return {
              generalLeft: general.getBoundingClientRect().left,
              generalRight: general.getBoundingClientRect().right,
              activityLeft: activity.getBoundingClientRect().left
            };
          }
        """)
        assert desktop['activityLeft'] > desktop['generalRight']

        page.set_viewport_size({'width': 800, 'height': 1200})
        mobile = page.evaluate("""
          () => {
            const general = document.querySelector(
              '[data-event-section="general"]');
            const activity = document.querySelector(
              '[data-event-section="activity-window"]');
            return {
              generalLeft: general.getBoundingClientRect().left,
              activityLeft: activity.getBoundingClientRect().left
            };
          }
        """)
        assert abs(mobile['generalLeft'] - mobile['activityLeft']) < 1
        browser.close()


def test_itemcode_editor_uses_aztek_columns_and_collapses_on_small_screens():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        page.evaluate("select(queue.add(blankCode()).key)")

        page.set_viewport_size({'width': 1400, 'height': 1000})
        desktop = page.evaluate("""
          () => {
            const general = document.querySelector(
              '[data-itemcode-section="general"]');
            const settings = document.querySelector(
              '[data-itemcode-section="settings"]');
            const rewards = document.querySelector(
              '[data-itemcode-section="rewards"]');
            return {
              generalLeft: general.getBoundingClientRect().left,
              generalRight: general.getBoundingClientRect().right,
              settingsLeft: settings.getBoundingClientRect().left,
              rewardsLeft: rewards.getBoundingClientRect().left
            };
          }
        """)
        assert abs(desktop['generalLeft'] - desktop['settingsLeft']) < 1
        assert desktop['rewardsLeft'] > desktop['generalRight']

        page.set_viewport_size({'width': 800, 'height': 1200})
        mobile = page.evaluate("""
          () => {
            const general = document.querySelector(
              '[data-itemcode-section="general"]');
            const settings = document.querySelector(
              '[data-itemcode-section="settings"]');
            const rewards = document.querySelector(
              '[data-itemcode-section="rewards"]');
            return {
              generalLeft: general.getBoundingClientRect().left,
              settingsLeft: settings.getBoundingClientRect().left,
              rewardsLeft: rewards.getBoundingClientRect().left,
              generalTop: general.getBoundingClientRect().top,
              settingsTop: settings.getBoundingClientRect().top,
              rewardsTop: rewards.getBoundingClientRect().top
            };
          }
        """)
        assert abs(mobile['generalLeft'] - mobile['settingsLeft']) < 1
        assert abs(mobile['generalLeft'] - mobile['rewardsLeft']) < 1
        assert mobile['generalTop'] < mobile['settingsTop'] < mobile['rewardsTop']
        browser.close()


def test_itemcode_create_all_keeps_failed_entries_selected_and_retryable():
    """The real create-all button only removes results the API saved."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        submitted = []
        page = _itemcode_page(context, submitted)
        page.evaluate("""
          addDrafts([
            {name_th: 'First Code', name_en: 'First Code', slug: 'first-code',
             start_time: '2026-08-01 00:00:00',
             end_time: '2026-08-31 23:59:59',
             rewards: [{name_th: 'First Reward', name_en: 'First Reward',
                        bundle_id: '101', code_type: '1', code_list: 'ONE'}]},
            {name_th: 'Second Code', name_en: 'Second Code', slug: 'second-code',
             start_time: '2026-08-01 00:00:00',
             end_time: '2026-08-31 23:59:59',
             rewards: [{name_th: 'Second Reward', name_en: 'Second Reward',
                        bundle_id: '202', code_type: '1', code_list: 'TWO'}]}
          ], 'test', 'CabalM TH')
        """)
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#btnCreateAll').click()
        page.wait_for_function("document.querySelectorAll('#results tbody tr').length === 2")

        assert [job['name_th'] for job in submitted[0]['itemcodes']] == [
            'First Code', 'Second Code']
        assert submitted[0]['do_save'] is True
        assert page.locator('#results tbody tr').all_inner_texts() == [
            'First Code\t101\tสร้างแล้ว',
            'Second Code\t-\tbundle rejected',
        ]
        assert page.evaluate("queue.items.map(entry => entry.slug)") == ['second-code-mth']
        assert page.evaluate("queue.current().slug") == 'second-code-mth'
        assert page.locator('#queuePick').input_value() == page.evaluate(
            "queue.current().key")
        browser.close()


def test_itemcode_reward_tabs_show_one_set_and_keep_all_sets_in_payload():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        page.evaluate("""
          addDrafts([{
            name_th: 'Two Sets',
            rewards: [
              {name_th: 'First Reward', name_en: 'First Reward'},
              {name_th: 'Second Reward', name_en: 'Second Reward'}
            ]
          }], 'test')
        """)

        tabs = page.locator('.reward-tab')
        assert tabs.all_text_contents() == ['1 ชุดที่ 1', '2 ชุดที่ 2']
        assert tabs.nth(0).get_attribute('aria-selected') == 'true'
        assert tabs.nth(1).get_attribute('aria-selected') == 'false'
        assert page.locator('#rsets .rset').count() == 1
        assert page.locator('#rsets input').first.input_value() == 'First Reward'

        tabs.nth(1).click()
        assert tabs.nth(0).get_attribute('aria-selected') == 'false'
        assert tabs.nth(1).get_attribute('aria-selected') == 'true'
        assert page.locator('#rsets .rset').count() == 1
        assert page.locator('#rsets input').first.input_value() == 'Second Reward'
        assert page.evaluate(
            "jobFrom(queue.current()).rewards.map(r => r.name_th)"
        ) == ['First Reward', 'Second Reward']
        browser.close()


def test_itemcode_reward_tabs_select_added_set_remove_safely_and_reset_per_queue():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        page.evaluate("""
          addDrafts([
            {name_th: 'First Code', rewards: [
              {name_th: 'First A'}, {name_th: 'First B'}
            ]},
            {name_th: 'Second Code', rewards: [
              {name_th: 'Second A'}, {name_th: 'Second B'}
            ]}
          ], 'test')
        """)

        page.locator('.reward-tab').nth(1).click()
        page.locator('#btnAddSet').click()
        tabs = page.locator('.reward-tab')
        assert tabs.all_text_contents() == [
            '1 ชุดที่ 1', '2 ชุดที่ 2', '3 ชุดที่ 3']
        assert tabs.nth(2).get_attribute('aria-selected') == 'true'

        page.locator('#rsets .rset .danger').click()
        tabs = page.locator('.reward-tab')
        assert tabs.count() == 2
        assert tabs.nth(1).get_attribute('aria-selected') == 'true'

        page.locator('#queuePick').select_option(
            page.evaluate("queue.items[1].key"))
        assert page.locator('.reward-tab').nth(0).get_attribute(
            'aria-selected') == 'true'
        assert page.locator('#rsets input').first.input_value() == 'Second A'
        browser.close()


def test_itemcode_bundle_handoff_preserves_full_draft_and_fills_every_set():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        _choose_game(page, 'CabalPC TH')
        page.evaluate("""
          applyBundleHandoff({
            game: 'CabalPC TH',
            itemcode_drafts: [{
              group: 'group-a', name_th: 'Summer Prize',
              name_en: 'Summer Prize EN', slug: 'summer-prize-pcth',
              uses_per_user: '40', limited: true,
              quantity: '40', remaining: '40',
              start_time: '2026-08-03 00:00:00',
              end_time: '2026-08-31 23:59:59',
              rewards: [
                {name_th: 'Set 1', name_en: 'Set 1', bundle_id: ''},
                {name_th: 'Set 2', name_en: 'Set 2', bundle_id: ''}
              ]
            }],
            rows: [{group: 'Summer Prize', group_key: 'group-a',
                    name: 'Bundle A', bundle_id: '224184'}]
          })
        """)

        assert page.evaluate("queue.items.length") == 1
        entry = page.evaluate("queue.current()")
        assert entry['name_th'] == 'Summer Prize'
        assert entry['name_en'] == 'Summer Prize EN'
        assert entry['slug'] == 'summer-prize-pcth'
        assert entry['uses_per_user'] == '40'
        assert (entry['limited'], entry['quantity'], entry['remaining']) \
            == (True, '40', '40')
        assert entry['start_time'] == '2026-08-03 00:00:00'
        assert entry['end_time'] == '2026-08-31 23:59:59'
        assert [reward['bundle_id'] for reward in entry['rewards']] == [
            '224184', '224184']
        browser.close()


def test_itemcode_bundle_handoff_fallback_fills_english_and_midnight_only():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, ITEMCODES)
        _choose_game(page, 'CabalM SEA')
        page.evaluate("""
          applyBundleHandoff({
            game: 'CabalM SEA', itemcode_drafts: [],
            rows: [{group: 'Manual', group_key: 'manual',
                    name: 'Fallback Bundle', bundle_id: '900'}]
          })
        """)

        entry = page.evaluate("queue.current()")
        expected_start = datetime.now(ZoneInfo('Asia/Bangkok')).strftime(
            '%Y-%m-%d 00:00:00')
        assert (entry['name_th'], entry['name_en']) == (
            'Fallback Bundle', 'Fallback Bundle')
        assert entry['slug'] == 'fallback-bundle-msea'
        assert entry['start_time'] == expected_start
        assert entry['end_time'] == ''
        assert entry['limited'] is False
        assert entry['rewards'][0]['bundle_id'] == '900'
        browser.close()


def test_event_reward_tabs_show_one_set_and_keep_all_sets_in_payload():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        page.evaluate("""
          addDrafts([{
            name_th: 'Two Set Event',
            rewards: [
              {name_th: 'First Prize', name_en: 'First Prize'},
              {name_th: 'Second Prize', name_en: 'Second Prize'}
            ]
          }], 'test')
        """)

        tabs = page.locator('.reward-tab')
        assert tabs.all_text_contents() == ['1 ชุดที่ 1', '2 ชุดที่ 2']
        assert tabs.nth(0).get_attribute('aria-selected') == 'true'
        assert tabs.nth(1).get_attribute('aria-selected') == 'false'
        assert page.locator('#rsets .rset').count() == 1
        assert page.locator('#rsets input').first.input_value() == 'First Prize'

        tabs.nth(1).click()
        assert tabs.nth(1).get_attribute('aria-selected') == 'true'
        assert page.locator('#rsets input').first.input_value() == 'Second Prize'
        assert page.evaluate(
            "jobFrom(queue.current()).rewards.map(r => r.name_th)"
        ) == ['First Prize', 'Second Prize']
        browser.close()


def test_event_reward_tabs_select_added_set_remove_safely_and_reset_per_queue():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        page.evaluate("""
          addDrafts([
            {name_th: 'First Event', rewards: [
              {name_th: 'First A'}, {name_th: 'First B'}
            ]},
            {name_th: 'Second Event', rewards: [
              {name_th: 'Second A'}, {name_th: 'Second B'}
            ]}
          ], 'test')
        """)

        page.locator('.reward-tab').nth(1).click()
        page.locator('#btnAddSet').click()
        tabs = page.locator('.reward-tab')
        assert tabs.nth(2).get_attribute('aria-selected') == 'true'

        page.locator('#rsets .rset .danger').click()
        tabs = page.locator('.reward-tab')
        assert tabs.count() == 2
        assert tabs.nth(1).get_attribute('aria-selected') == 'true'

        page.locator('#queuePick').select_option(
            page.evaluate("queue.items[1].key"))
        assert page.locator('.reward-tab').nth(0).get_attribute(
            'aria-selected') == 'true'
        assert page.locator('#rsets input').first.input_value() == 'Second A'
        browser.close()


def test_event_bundle_ids_match_exact_group_keys_across_same_reward_names():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        _choose_game(page, 'CabalM SEA')
        page.evaluate("""
          applyBundleHandoff({
            game: 'CabalM SEA',
            event_drafts: [
              {sheet: 'A', sheet_key: 'sa', name_th: 'Event A',
               name_en: 'Event A', slug: 'event-a',
               rewards: [{group_key: 'ga', group: 'Lucky Draw',
                          name_th: 'Lucky Draw', name_en: 'Lucky Draw'}]},
              {sheet: 'B', sheet_key: 'sb', name_th: 'Event B',
               name_en: 'Event B', slug: 'event-b',
               rewards: [{group_key: 'gb', group: 'Lucky Draw',
                          name_th: 'Lucky Draw', name_en: 'Lucky Draw'}]}
            ],
            rows: [
              {group_key: 'ga', group: 'Lucky Draw', bundle_id: '101'},
              {group_key: 'gb', group: 'Lucky Draw', bundle_id: '202'}
            ]
          })
        """)

        assert page.evaluate(
            "queue.items.map(e => e.rewards[0].bundle_id)"
        ) == ['101', '202']
        browser.close()


def test_unmatched_key_is_warned_and_not_attached_to_first_event():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, EVENTS)
        page.evaluate("""
          applyBundleHandoff({
            event_drafts: [{
              sheet: 'A', sheet_key: 'sa', name_th: 'Event A',
              name_en: 'Event A', slug: 'event-a',
              rewards: [{group_key: 'ga', group: 'Lucky Draw',
                         name_th: 'Lucky Draw', name_en: 'Lucky Draw'}]
            }],
            rows: [{group_key: 'missing', group: 'Lucky Draw',
                    bundle_id: '999'}]
          })
        """)

        assert page.evaluate(
            "queue.items[0].rewards[0].bundle_id"
        ) == ''
        assert 'missing' in page.locator('#log').inner_text()
        browser.close()
