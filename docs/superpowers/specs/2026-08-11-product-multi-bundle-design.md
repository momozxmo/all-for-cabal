# Product Multi-Bundle Design

## Goal

Allow one Product draft to contain up to 20 Bundle IDs, including IDs imported from a workbook and IDs entered manually, and fill all of them into Aztek with one selected Primary Bundle.

## Confirmed Aztek behavior

The current Product form supports multiple Bundle selections directly. After one selection it shows `1/20 Bundles`, after two it shows `2/20 Bundles`, and each selected Bundle has a `Primary` control. One Bundle is Primary; the first selection becomes Primary automatically.

## Local Product editor

- Replace the single editable Bundle ID input with a list of Bundle rows.
- Each row contains an editable numeric Bundle ID, a Primary radio control, and a remove button.
- An **เพิ่ม Bundle** button appends an empty row until the 20-row limit.
- Imported IDs populate one row per ID in source order.
- When the first ID is added, it becomes Primary automatically.
- Operators can change Primary before preview or create.
- Removing the Primary row makes the first remaining row Primary.
- Duplicate IDs, empty rows at submission, non-numeric IDs, and more than 20 IDs block preview/create with a clear message.
- A draft with no Bundle remains editable but cannot be submitted.

## Data model and compatibility

- `bundle_ids: list[str]` is the ordered final Bundle list attached to Aztek.
- `primary_bundle_id: str` identifies one value from `bundle_ids`.
- Legacy `bundle_id: str` remains accepted when loading old queue entries or API payloads; it normalizes to a one-item `bundle_ids` list and becomes Primary.
- New UI/API payloads send `bundle_ids` and `primary_bundle_id`. A scalar `bundle_id` may mirror the Primary ID for compatibility while consumers migrate.
- Multiple imported Bundle IDs no longer imply `composite_required`; the direct Aztek multi-Bundle flow replaces that requirement.
- Existing saved queue fields unrelated to Bundle selection remain unchanged.

## Aztek runner

- Open the Bundle picker once per ordered Bundle ID and search by exact numeric ID.
- Select one exact result per ID and reject missing or ambiguous matches.
- After each selection, verify that the selected Bundle is visible in the Product Bundle section.
- Verify the final selected count equals `len(bundle_ids)` and does not exceed 20.
- Mark the row matching `primary_bundle_id` as Primary and read the checked state back.
- Any selection or Primary failure marks the fill incomplete; preview remains open for inspection and real create must not run.
- Preview/fill never creates a real Product. Real creation remains behind the existing explicit create controls.

## UI state and handoffs

- Workbook imports and existing Bundle handoffs merge IDs in stable order without duplicates.
- Manually edited rows are preserved across queue switching and reloads.
- Existing Composite Bundle notices/actions are removed from the normal Product path because Aztek accepts multiple Bundle selections directly.

## Verification

- Unit tests cover normalization, legacy scalar input, ordering, duplicates, Primary fallback, invalid input, and the 20-ID limit.
- Browser tests cover adding/removing rows, manual editing, changing Primary, import prefill, queue persistence, and payload order.
- Runner tests model the current Aztek multi-Bundle section and assert exact selection order, count verification, and Primary read-back.
- A fail-closed regression proves that one missing Bundle prevents real save.
- No test or verification step creates a real Aztek Product.
