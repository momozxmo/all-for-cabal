# Event Web Result Default Design

## Goal

When Item Finder is in Event mode, make “ไม่มี” the default value for “แสดงผลบนเว็บ” while keeping all three choices editable.

## Behavior

- Event uses `web_mode: no` and `web_locked: false`.
- Switching to Event selects “ไม่มี” automatically.
- The operator can still change Event to “ทั้งหมด” or “มี”.
- Item Code remains `web_mode: no` and locked.
- Shop remains `web_mode: no` and editable.
- Existing imported workspaces and search result data are not rewritten; this changes only the default selected when applying Event mode.

## Implementation Boundary

- Update the shared Event mode policy in `web/item_service.py` so the `/api/modes` response and Item Finder UI agree.
- Add service coverage for the Event policy.
- Extend the Item Finder browser regression test to assert that Event selects `webNo` without disabling the choices.
- Do not change search execution, Event import, Event creation, Item Code, Shop behavior, Product behavior, or Setup/release files.

## Verification

- Run the focused mode-policy and Item Finder browser tests.
- Run the complete `tests/` suite.
- Confirm the diff is limited to the shared mode policy, its tests, and this documentation.
