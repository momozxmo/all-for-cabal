# -*- coding: utf-8 -*-
"""Browser-level regression tests for the shared 24-hour calendar."""
from pathlib import Path

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
        assert page.locator('#bookmarklet').is_visible()
        assert page.locator('#createPairingButton').is_visible()
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

        page.evaluate("applyMode('event', false)")
        assert page.locator('#btnToEvent').is_visible()
        assert not page.locator('#btnToItemCode').is_visible()
        assert not page.locator('#btnToProduct').is_visible()

        page.evaluate("applyMode('itemcode', false)")
        assert page.locator('#btnToItemCode').is_visible()
        assert not page.locator('#btnToEvent').is_visible()
        assert not page.locator('#btnToProduct').is_visible()

        page.evaluate("applyMode('shop', false)")
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
