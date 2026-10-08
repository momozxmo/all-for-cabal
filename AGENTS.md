# Project Instructions

## Resume and machine handoff

When resuming work or moving to another computer, read `docs/HANDOFF.md`, then verify the checkout, branch and dirty files before editing. For new-machine setup and Git transfer steps, use `docs/MULTI_COMPUTER_DEV.md`.

## Aztek automation locators

Before adding or modifying any Aztek automation function, read `docs/agents/aztek-locators.md`. All new functions must use verified stable HTML element IDs wherever available; the policy defines scoped exceptions for controls without IDs and safe stopping when an ID contract breaks.

## Agent skills

### Issue tracker

Issues and specs are tracked in GitHub Issues at `momozxmo/all-for-cabal`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default labels `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.
