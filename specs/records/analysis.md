# Specification analysis: records

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise 3 | Which find arguments the matcher reads | Resolved in Clarifications: every argument, so `-path './.wuwei/*'` is read |
| A2 | Ambiguity | LOW | item promise 4 | Whether a redirect counts as a writer after `cd .wuwei` | Resolved: a redirect to a file counts; fd duplicates and `/dev/` do not |
| A3 | Ambiguity | LOW | item promise 5 | What "outside .wuwei" means for a pathspec | Resolved: a normalized pathspec starting with a plain character |
| C1 | Coverage | MEDIUM | spec How this fails 3 | dotglob, symlinks, glued quotes, `cd "$VAR"` and xargs stay holes | Accepted: listed in SECURITY.md as known shapes; outside the promise's spellings |
| S1 | Scope | LOW | spec Clarifications 4 | A session whose directory is inside `.wuwei` is treated as after `cd` | Kept: zero extra lines, closes the two-call form of promise 4 |
| B1 | Breaking | MEDIUM | spec Breaking | Commands that passed on main are refused | Declared with migration notes, `!` and a BREAKING CHANGE line |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 records() replaces LEDGER | yes | T002, T003, T008, T012 | |
| FR-002 cache writes refused, rm passes | yes | T004, T005, T009 | |
| FR-003 find, cd, git clean | yes | T002, T003, T010 | |
| FR-004 routes.json | yes | T014, T018 | |
| FR-005 docs and vendored copy | yes | T015, T016 | |
| FR-006 line budget | yes | T019 | +15 lines |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime under the 3,000 budget.
