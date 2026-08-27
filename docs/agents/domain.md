# Domain Docs

This repository uses a single domain context. Engineering skills should consume the domain documentation as follows.

## Before exploring

- Read `CONTEXT.md` at the repository root.
- Read ADRs under `docs/adr/` that touch the area being changed.
- If either location does not exist, proceed silently.

## File structure

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── web/
```

`CONTEXT.md` is the glossary. ADRs record implementation decisions only when they are hard to reverse, surprising without context, and the result of a real trade-off.

## Use the glossary vocabulary

When an issue, specification, test, or implementation names a domain concept, use the term defined in `CONTEXT.md`. Avoid synonyms that the glossary marks under `_Avoid_`.

If a required concept is absent, reconsider whether new language is necessary. Record genuine domain gaps through the domain-modeling workflow rather than inventing competing terms in implementation documents.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly rather than silently overriding the decision.
