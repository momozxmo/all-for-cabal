# Sheet Picker Search Design

Date: 2026-08-11

## Goal

Add the same immediate sheet-name search to every workbook sheet picker in the
web app: Item Finder, Product, Event, and Item Code. Long sheet names must remain
fully readable.

## User experience

- Each sheet picker shows a search field above the sheet list.
- Filtering runs on every `input` event; there is no Search button.
- Matching is case-insensitive and ignores leading or trailing query spaces.
- A sheet remains visible when its full displayed name contains the query.
- The picker shows `displayed / total` counts while filtering.
- Select All and Clear affect only rows currently visible after filtering.
- Hidden rows keep their previous checkbox state.
- Import Selected includes every checked row, including a checked row hidden by
  the current query.
- Clearing the query restores every row without changing checkbox state.
- Opening a picker for a newly imported file clears the previous query.
- Sheet names wrap onto additional lines and never use ellipsis or horizontal
  clipping.
- When nothing matches, the list shows a clear empty-result message while the
  operator can still clear the query.

## Architecture

Create a small shared static helper used by all four pages. Each page registers
its sheet-list element, search input, result-count element, and existing bulk
buttons. The helper owns only presentation behavior: query normalization, row
visibility, visible-row bulk selection, and count/empty-state rendering.

The existing page-specific import functions remain responsible for building
rows and applying the final selected sheet names. No API payload, parser,
workspace, queue, or Aztek creation behavior changes.

Every generated sheet row carries a normalized searchable value in a data
attribute. The helper reads this value instead of parsing visible count labels,
so Product/Event/Item Code suffix text cannot affect the sheet identity.

## Styling

Use the existing input and dialog colors. Add shared sheet-picker rules for:

- a full-width search input;
- a compact displayed/total status;
- an empty-result row;
- auto-height sheet rows; and
- `white-space: normal` plus safe word wrapping for long names.

The Item Finder page has page-local styles, so it receives the same semantic
rules without changing its overall visual theme.

## State and edge cases

- Filtering changes only row visibility, never checkbox values.
- Bulk actions ignore the empty-result message and hidden rows.
- Reopening the same dialog without a new import retains the current checkbox
  state, but rendering a newly imported workbook resets the search field.
- Sheet names containing Thai, English, spaces, punctuation, or numbers are
  treated as plain text; no regular expression is evaluated.
- The search helper remains client-side because all candidate sheet names are
  already loaded in the dialog.

## Verification

Browser regressions will cover all four pages and assert visible behavior:

1. typing filters immediately without pressing Enter;
2. matching is case-insensitive;
3. Select All and Clear modify only visible matches;
4. hidden selections survive filtering and are included when applying;
5. clearing the query restores all rows;
6. a no-match message and correct count appear; and
7. a long sheet name wraps and its full text remains visible.

Run the focused browser tests first, then the complete test suite. This change
does not authorize creating live Aztek records, building Setup, committing the
implementation, or pushing a release.
