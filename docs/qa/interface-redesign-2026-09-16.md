# Interface redesign verification — 2026-09-16

## Direction and boundaries

User-confirmed Gridgeist direction: an operator workspace that makes context,
the selected queue entry, and the next action visible. Preserve the dark Cabal
palette and gem identity; quiet decorative rails and gradients.

Shared presentation rules live in `web/static/workspace-ui.css` and
`web/static/workspace-ui.js`. Existing backend routes, payloads, queue storage,
import parsers, preview gates, creation eligibility, and create-all scope are
unchanged. Queue size is explicitly not presented as a validated-ready count.
Product feedback shows the selected entry's recorded last result, not an
invented diagnosis. Bundle history is distinguished from the current queue;
missing historical game/timestamp metadata is not fabricated.

## Observed verification

- Playwright Chromium, isolated contexts and controlled API fixtures; no live
  Aztek creation, reconnection, installation, or changes to the user's queues.
- Main routes: Item Finder, Bundle, Item Code, Event, Product at widths 360,
  768, 1280, 1600 px (900 px height).
- Populated Bundle, Item Code, Event editors: 360, 768, 1280 px.
- Populated Product prices and calendar: all four widths.
- Account, hosted login, and local-start: 360 px mobile viewport.
- Keyboard: first-Tab skip link and focus target, language tab arrow navigation,
  calendar Enter/Escape and focus return, Log disclosure activation.
- Overflow: document boundaries, editor control bounds, scrollable results,
  minimum readable Code/date field widths, calendar horizontal bounds.
- Primary-flow regression: bulk paste and Excel preview into editable Bundle
  queues, RANDOM/reward values, Mastercode WR, game handoffs, Product preview
  gating, currency and Bundle edits, retry scope, updater/draft preservation.
- Visually inspected generated desktop/mobile Product, price, Item Code, and
  Event captures. Corrected native Currency search styling, narrow Code fields,
  Event date fields, and an offscreen skip-link capture artifact.

## Commands and results

```powershell
python -m pytest tests/test_web_interface_ui.py tests/test_web_calendar_ui.py tests/test_web_product_ui.py tests/test_web_bundle_bulk_ui.py tests/test_web_bundle_import_ui.py tests/test_web_itemcode_wr_ui.py tests/test_web_account_ui.py tests/test_local_update_ui.py -q -p no:cacheprovider --maxfail=2
```

Final result: **130 passed in 177.04s** (34 interface checks and 96 regression
checks). `node --check` passed for workspace-ui.js and console.js.
`git diff --check` passed; Git reported existing LF/CRLF conversion warnings.

Full repository verification before the Local Setup release:

```powershell
python -m pytest -q tests --basetemp=build-cache\pytest-release-v034-elevated -p no:cacheprovider
```

Final result: **1541 passed, 1 warning in 394.87s**. The warning is the existing
development-secret fixture warning in `tests/test_local_runtime.py`.

## Limits and release state

This is not a live Aztek end-to-end test, screen-reader certification, or
physical-device usability study. Reduced-motion and
forced-colors rules are implemented but were not independently browser-audited.
No Setup build, install, commit, push, or release was performed. Existing root
checkout edits and unrelated untracked files were preserved.
