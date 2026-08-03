# Item Code Bundle Handoff and Data-Driven Limit Design

Date: 2026-08-03

## Goal

Preserve the complete Item Code draft when an operator creates bundles first,
fill missing English names and the current-day midnight start time, and support
the current Aztek v2 code-wide `จำกัดจำนวน` control without turning finite
limits on for unlimited plans.

## Scope

- Fix the Item Finder -> Bundle -> Item Code handoff.
- Preserve Item Code names, slug, usage count, dates, reward sets, and limit
  metadata across that handoff.
- Add the code-wide limit switch and its two numeric fields to the Local Item
  Code settings panel.
- Add the same fields to the Item Code API request and Aztek form filler.
- Derive limit state only from explicit or calculable imported counts.
- Keep reward-set `จำกัดจำนวน Code` behavior unchanged.
- Do not change Event or Product form behavior.
- Do not create a real Aztek record during implementation or verification.
- Do not build an installer, commit, push, or publish a release unless the user
  explicitly requests it after verification.

## Imported Draft Rules

An Item Code draft carries these code-wide fields:

- `limited: bool`
- `quantity: str`
- `remaining: str`

For Event/Prize plan imports:

1. Read the existing `total`, `codes_per_set`, and `set_count` metadata.
2. Use the same buffered total already calculated for generated reward codes.
3. If the resulting total is a positive integer, set `limited` to `true` and
   set both `quantity` and `remaining` to that total.
4. If no positive total can be read or calculated, set `limited` to `false`
   and leave both count strings empty.

For Pride-style imports:

1. Use `code_count` for server-generated codes.
2. Use `refill_limit` for a fixed master code.
3. A positive value enables the limit and fills both counts; an absent or
   invalid value leaves the Item Code unlimited.

The limit is therefore data-driven. Reaching the Item Code page from Bundle
does not itself enable the limit.

## Manual Draft Rules

- A newly added Item Code starts unlimited.
- Its `quantity` and `remaining` values start empty.
- Its English name uses the supplied handoff name when one exists; a completely
  blank manual draft remains blank.
- Its start time is the current date at `00:00:00` in `Asia/Bangkok`.
- The operator can enable or disable the switch and edit both counts before
  previewing or creating.

## Bundle Handoff Contract

The bundle-preview response includes `itemcode_drafts` when the workspace mode
is `itemcode`. Drafts are filtered to the bundle group keys selected for the
preview, just as Event drafts are filtered today.

The Bundle page keeps `itemcode_drafts` beside the existing `event_drafts` in
local storage. When created Bundle IDs are sent to `/itemcodes`, the handoff
payload contains both the created rows and those complete drafts.

The Item Code page matches a created row to a draft by the internal `group_key`
or `group`, clones the complete draft, and writes the created Bundle ID into
every reward set in that draft that has no Bundle ID. This is required because
one imported Item Code can contain several reward sets backed by the same
created bundle.

Fallback behavior for a bundle without a matching imported draft:

- Use the bundle name for both Thai and English names.
- Generate the server-suffixed slug from that name.
- Set start time to the current Bangkok date at midnight.
- Leave end time empty for operator review.
- Keep the Item Code unlimited.
- Create one reward set containing the handed-off Bundle ID.

## Local Layout

The Local settings panel follows the inspected Aztek v2 structure:

1. Existing type, per-user, start time, and end time fields remain in place.
2. A switch labelled `จำกัดจำนวน` appears after the existing settings.
3. When the switch is off, count inputs are hidden.
4. When it is on, a two-column row appears below it:
   - `จำนวนครั้งที่สามารถใช้งานได้`
   - `จำนวนคงเหลือ`
5. At narrow widths the existing responsive grid may stack the two fields.

The switch and inputs edit the active queue entry and persist with the existing
browser queue storage.

## API and Automation

`ItemCodeSpec` accepts the three new fields with unlimited/empty defaults. The
run endpoint cleans and forwards them without inventing counts.

The Aztek filler:

- sets the top-level switch identified by the label `จำกัดจำนวน`;
- fills `input[name="quantity"]` and `input[name="remaining"]` only when the
  switch is enabled;
- leaves reward-level `จำกัดจำนวน Code` logic untouched;
- continues to lock Item Code type to `ALL`.

## Validation

- When `limited` is false, blank or stale count values are not sent to Aztek.
- When `limited` is true, `quantity` and `remaining` must be positive integer
  strings before a run starts.
- Existing date validation and start-before-end validation remain unchanged.
- Missing end time in an unmatched fallback draft remains visibly incomplete
  and prevents preview/create until the operator fills it.

## Verification

- Unit tests cover limited and unlimited imported plans.
- API tests cover schema defaults, positive-count validation, and cleaned jobs.
- Browser tests cover the switch layout, visibility, persistence, Bangkok
  midnight default, complete draft handoff, English-name fallback, and filling
  all reward-set Bundle IDs.
- Runner tests verify the code-wide switch and top-level selectors separately
  from reward-level limit selectors.
- Run the full automated test suite without clicking the real Aztek create
  button.
