# Aztek locator policy — ID-first

Approved: 2026-10-01, Q1–Q4 plus the user's requirement that all future Aztek functions follow this policy.
Applies to new and modified Aztek automation, including shared helpers and future New Item work.
It does not authorize implementation, real Aztek writes, or resuming paused tasks.

## Required behavior

- Use a verified, developer-maintained HTML element ID as the primary locator whenever available.
  New functions must follow this rule from their first implementation, not wait for another migration.
  A business record ID or option value is not an HTML element ID.
- Verify the target's expected role/type, active form/dialog/row, readiness and uniqueness before interaction.
  Wait for mounting and visibility within the normal timeout; an ID absent before mounting is not yet proof of a broken contract.
- Give ID lookup actual priority. A CSS union of ID and fallback followed by first-match does not guarantee ID-first behavior.
- If a known stable ID is absent after readiness checks, duplicated within the intended scope, or points to the wrong control, stop that affected operation and report the control.
  Keep drafts, queue checkpoints and creation/recheck outcomes. Do not guess another field or submit/re-submit to recover.

## Controls without stable IDs

- Use only an explicitly documented, evidence-backed exception for controls known not to have stable IDs.
  Scope the semantic locator to the correct form, row, active tab or dialog; require an unambiguous target.
  Record the control and missing ID for the DEV gap list.
- Do not use a no-ID exception to mask a broken stable-ID contract. Unsupported or ambiguous layouts stop safely.
- Do not treat framework-generated IDs such as radix/tiny-react as developer-maintained stable IDs, or inject IDs in Tools and claim they satisfy the DEV contract.
- Indexed row IDs require correct row mapping; literal IDs containing punctuation require safe attribute lookup or CSS escaping.
  Preserve tab sequencing, widget interaction, option business IDs and readback checks.

## Verification

- Prefer existing public API/runner tests with synthetic Aztek pages. Test that changes to text, class and nesting/reordering do not break a stable-ID control.
- Test missing/duplicate/wrong-type IDs, misleading fallback controls, repeated rows and lazy-mounted controls; verify safe stopping and unchanged submit counts/checkpoints.
- Preserve existing date/time, Currency, EXP, rate-zero, creation-confirmation and recheck behavior. Live inspections are read-only unless the user explicitly authorizes real writes.

When planning or implementing the migration, read the [ID-first spec](../aztek-id-selector-spec.md) for coverage, acceptance criteria and unverified game/page states. Findings and field inventories are evidence, not a blanket promise that all DOM elements have stable IDs.
