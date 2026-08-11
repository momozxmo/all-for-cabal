# Sheet Picker Real Tab Names Design

## Goal

Make every workbook import picker display and search the exact worksheet tab name so operators can match each option to the tab shown in Excel.

## Behavior

- Item Finder, Event, Item Code, and Product pickers display `sheet.name` only.
- Search matches `sheet.name` only.
- Checkbox values remain `sheet.name`, preserving the existing import key.
- Content-derived `display_name` remains in API responses for compatibility, but picker UIs do not use it.
- Excel's 31-character worksheet-name limit is accepted as the authoritative imported tab name; Event/Product titles must not replace it.

## Data flow

The parser and API continue returning the stable worksheet `name`. Each picker uses that value for its label, searchable data attribute, and submitted checkbox value. No parser or workspace persistence behavior changes.

## Error handling

Empty or missing names retain the existing API/parser handling. This change does not invent a fallback title from sheet content.

## Verification

- Browser contracts cover Item Finder, Event, Item Code, and Product.
- A fixture where `name` and `display_name` differ must visibly show and search only `name` while submitting the same name.
- Existing auto-search, visible-only select-all/clear, and long-name wrapping tests remain green.
