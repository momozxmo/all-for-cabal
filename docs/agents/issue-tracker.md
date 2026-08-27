# Issue tracker: GitHub

Issues and specs for this repo live in GitHub Issues at `momozxmo/all-for-cabal`. Use the `gh` CLI with `--repo momozxmo/all-for-cabal` for all operations so the `local-release` remote cannot be selected accidentally.

## Conventions

- **Create an issue**: `gh issue create --repo momozxmo/all-for-cabal --title "..." --body-file <path>`.
- **Read an issue**: `gh issue view <number> --repo momozxmo/all-for-cabal --comments` and fetch its labels.
- **List issues**: `gh issue list --repo momozxmo/all-for-cabal --state open --json number,title,body,labels,comments` with the appropriate label and state filters.
- **Comment on an issue**: `gh issue comment <number> --repo momozxmo/all-for-cabal --body-file <path>`.
- **Apply or remove labels**: `gh issue edit <number> --repo momozxmo/all-for-cabal --add-label "..."` or `--remove-label "..."`.
- **Close an issue**: `gh issue close <number> --repo momozxmo/all-for-cabal --comment "..."`.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub shares one number space across issues and pull requests. Resolve an ambiguous `#<number>` by checking the pull request first and falling back to the issue, always against `momozxmo/all-for-cabal`.

## Skill operations

When a skill says **publish to the issue tracker**, create a GitHub issue in `momozxmo/all-for-cabal`.

When a skill says **fetch the relevant ticket**, read the GitHub issue and its comments from `momozxmo/all-for-cabal`.

## Wayfinding operations

- **Map**: one issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- **Child ticket**: an issue linked as a GitHub sub-issue. If sub-issues are unavailable, add it to a task list in the map and put `Part of #<map>` at the top. Use a `wayfinder:<type>` label such as `research`, `prototype`, `grilling`, or `task`.
- **Blocking**: use GitHub native issue dependencies. If unavailable, use a `Blocked by: #<number>` line.
- **Frontier query**: consider open children in map order, excluding assigned tickets and tickets with open blockers.
- **Claim**: assign the selected issue to the authenticated user; this is the session's first write.
- **Resolve**: comment with the answer, close the issue, and append a durable context pointer to the map's Decisions-so-far.
