# Event Warning Highlight Design

## Goal

Make the imported-plan warning beneath the **แก้ Event** heading clearly visible as a general warning without presenting it as a blocking error.

## Visual design

- Keep the existing warning text and warning icon.
- Use a translucent amber background, amber border, and stronger amber left accent.
- Use a light amber foreground color with sufficient contrast against the dark page.
- Keep the existing spacing and responsive Event layout unchanged.

## Scope

- Apply the highlight only to `#planWarnings` on the Event page.
- Do not change shared `.summary`, `.warning`, buttons, logs, or warnings on other pages.
- Preserve the existing `hidden` behavior when an Event has no warning.

## Verification

- Add a static regression test asserting that the Event warning has its own class and scoped visual rule.
- Run the Event/UI regression tests after the change.
