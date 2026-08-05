# Product Live Actions Design

## Goal

Make the Product execution area match the established Event and Item Code
workflow. Remove the Product-only mode radios and selection checkbox so the
actions are explicit and visible in one card.

## Scope

This change is limited to `web/static/products.html` and its browser regression
tests. It does not change Item Code, Event, Product parsing, Product form
fields, the Product API contract, or the Aztek runner.

## Layout

Replace the current sticky action strip with a normal card titled
`สร้างบนเว็บจริง`. The card contains three always-visible buttons in this
order:

1. `👁 เปิดหน้าเว็บดูก่อน (อันที่เลือก)`
2. `🚀 สร้างจริง (อันที่เลือก)`
3. `⚡ สร้างทุกอันในคิว (N)`

The result message and Product result rows remain below the buttons. Existing
retry controls inside result rows remain unchanged.

Remove the `กรอกเพื่อตรวจสอบ` / `สร้างจริง` mode radios and the
`เลือก Product นี้สำหรับสร้างจริง` checkbox from the UI and JavaScript
bindings.

## Button Behaviour

### Preview selected Product

- Disabled when the queue has no active Product.
- Runs the existing preview request for only the active Product with
  `do_save=false`.
- A successful preview belongs to that Product key.
- Switching to another Product locks the selected-create button until that
  Product has been previewed successfully.
- Editing the active Product after preview locks selected-create again so the
  reviewed form cannot silently differ from the created form.

### Create selected Product

- Disabled until the active Product has completed a successful preview.
- Uses the existing confirmation dialog and sends only the active Product with
  `do_save=true`.
- Remains disabled for an already-created Product with a Product ID.

### Create every Product in the queue

- Button text always shows the number of queue entries that do not yet have a
  Product ID.
- Disabled when that count is zero.
- Sends every runnable Product without a Product ID, in queue order, with
  `do_save=true`.
- Uses one confirmation dialog that shows the total and Product names.
- Existing preflight validation still rejects missing Category, Bundle ID,
  Currency, price, or required dates before any API request.
- This bulk action does not require previewing each Product first, matching the
  current Event and Item Code bulk-create workflow.

## State and Results

The existing Product queue remains the source of truth. The removed checkbox
is no longer used to choose creation scope. Existing statuses, Product IDs,
missing-field results, logs, and retry behaviour remain unchanged.

The UI derives button enabled states and the bulk count every time the queue is
rendered, the active Product changes, a field changes, or a run finishes.

## Safety

- Preview never presses the Aztek create button.
- Create actions retain the explicit confirmation dialog.
- Already-created Products are excluded from both create actions.
- No real Aztek record is created during automated verification.

## Tests

Browser regression tests will verify:

- the new card and all three buttons are visible;
- the old mode radios and selection checkbox are absent;
- selected-create is locked before preview and unlocked only for the Product
  that was previewed;
- switching or editing locks selected-create again;
- the bulk button count excludes Products that already have Product IDs;
- bulk create sends all remaining queue entries in queue order with
  `do_save=true`;
- preview still sends one active Product with `do_save=false`.

Focused Product UI tests run first, followed by the complete test suite.
