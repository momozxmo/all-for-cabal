"""Read-only reader against synthetic DOM derived from four-game observations."""
import asyncio
import importlib.util
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright

GAMES = [('CabalPC TH', 'cabalpc'), ('CabalPC SEA', 'cabalpcsea'),
         ('CabalM TH', 'cabalm'), ('CabalM SEA', 'cabalmsea')]
ORIGIN = 'https://aztek-tools-v2.combo-interactive.com'


def saved_html(game, *, image=False, tier='GENERAL', lazy=False):
    # IDs, owning Type label/select shape and outside-form ID p are observed.
    # Values deliberately synthetic; no live write/result contract is invented.
    select = ('<button type="button" role="combobox">GENERAL</button>'
              '<select aria-hidden="true" style="position:absolute;width:1px;height:1px">'
              '<option value="GENERAL" selected>GENERAL</option>'
              '<option value="CABALPC_PREMIUM">CABALPC_PREMIUM</option></select>')
    kind = select if game.startswith('CabalPC ') else '<div>GENERAL</div>'
    image_html = '<img alt="Preview" src="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22/%3E">' if image else ''
    script = ''
    if lazy and game.startswith('CabalPC '):
        kind = '<button type="button" role="combobox"></button><select aria-hidden="true"></select>'
        script = '''<script>setTimeout(()=>{document.querySelector('select').innerHTML=
          '<option value="GENERAL" selected>GENERAL</option><option value="CABALPC_PREMIUM">CABALPC_PREMIUM</option>';
          document.querySelector('[role="combobox"]').textContent='GENERAL';},250);</script>'''
    return f'''<main><h1>แก้ไข Item</h1><p>ID: <span>91</span></p><form>
      <label>Name<input value="Wrong name"></label>
      <input id="item-name" name="name" value="Synthetic name">
      <div><label>game_item_type <span>*</span></label><div>{kind}</div></div>
      <input id="item-game-item-id" name="game_item_id" value="123">
      <textarea id="item-detail" name="detail">Synthetic description</textarea>
      <input id="item-option" name="game_options_1.itemOption" value="0">
      <input id="duration-index" name="game_options_1.durationIndex" value="0">
      <button id="game-tradeable" type="button" role="checkbox" aria-checked="false"></button>
      <button id="display-option-enable" type="button" role="switch" aria-checked="false"></button>
      <p>ID: 999</p>{image_html}<input type="file"><button type="submit">บันทึก</button>
    </form></main>{script}'''


def run_reader(html, game='CabalPC TH', *, url=None):
    spec = importlib.util.find_spec('web.new_item_reader')
    assert spec is not None, 'Saved New Item reader has not been implemented'
    from web.new_item_reader import read_saved_new_item
    slug = dict(GAMES)[game]
    target = url or f'{ORIGIN}/combo/{slug}/shop/items/91'
    async def scenario():
        requests, unexpected = [], []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(service_workers='block')
            async def route(request_route):
                request = request_route.request
                requests.append((request.method, request.url))
                if request.method == 'GET' and request.url == target:
                    await request_route.fulfill(status=200, body=html,
                                                content_type='text/html; charset=utf-8')
                else:
                    unexpected.append((request.method, request.url))
                    await request_route.abort()
            await context.route('**/*', route)
            page = await context.new_page()
            try:
                result = await read_saved_new_item(page, game=game, item_id='91', detail_url=target)
                assert unexpected == []
                assert all(method == 'GET' for method, _ in requests)
                return result
            finally:
                await browser.close()
    return asyncio.run(scenario())


@pytest.mark.parametrize('game,slug', GAMES)
@pytest.mark.parametrize('image', [False, True])
def test_reads_verified_ids_and_owned_type_without_submitting(game, slug, image):
    result = run_reader(saved_html(game, image=image), game)
    assert result['game'] == game and result['item_id'] == '91'
    assert result['values'] == {'name': 'Synthetic name', 'kind': '123', 'option': '0',
                                'duration': '0', 'item_type': 'GENERAL',
                                'tradeable': False, 'description': 'Synthetic description'}
    assert set(result['readable_fields']) == {'name', 'kind', 'option', 'duration',
                                             'item_type', 'tradeable', 'description'}
    assert result['image_present'] is image


@pytest.mark.parametrize('game,slug', GAMES[:2])
def test_lazy_pc_type_is_waited_for_not_guessed(game, slug):
    result = run_reader(saved_html(game, lazy=True), game)
    assert result['values']['item_type'] == 'GENERAL'


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong_type'])
def test_broken_stable_id_never_reads_misleading_name_field(change):
    from web.aztek_locator import AztekLocatorError
    html = saved_html('CabalPC TH')
    if change == 'missing':
        html = html.replace('id="item-name"', 'id="changed-name"')
    elif change == 'duplicate':
        html = html.replace('</form>', '<input hidden id="item-name" value="Decoy"></form>')
    else:
        html = html.replace('<input id="item-name" name="name" value="Synthetic name">',
                            '<button id="item-name" type="button">Synthetic name</button>')
    with pytest.raises(AztekLocatorError):
        run_reader(html)


@pytest.mark.parametrize('change', ['other_id', 'two_ids', 'changed_mid_read'])
def test_identity_ambiguity_stops_without_reading_a_different_record(change):
    from web.aztek_locator import AztekLocatorError
    html = saved_html('CabalPC TH')
    if change == 'other_id':
        html = html.replace('<span>91</span>', '<span>92</span>')
    elif change == 'two_ids':
        html = html.replace('<form>', '<p>ID: 92</p><form>')
    else:
        html += '<script>setTimeout(()=>document.querySelector("main p").textContent="ID: 92",100);</script>'
    with pytest.raises((AztekLocatorError, ValueError)):
        run_reader(html)


@pytest.mark.parametrize('game,slug', GAMES[2:])
def test_m_type_contract_is_not_silently_replaced_with_pc_select(game, slug):
    from web.aztek_locator import AztekLocatorError
    html = saved_html(game).replace('<div>GENERAL</div>',
           '<button type="button" role="combobox">GENERAL</button><select><option>GENERAL</option></select>')
    with pytest.raises(AztekLocatorError):
        run_reader(html, game)


def test_wrong_game_url_is_rejected_before_any_navigation():
    with pytest.raises(ValueError):
        run_reader(saved_html('CabalPC TH'), url=f'{ORIGIN}/combo/cabalm/shop/items/91')
