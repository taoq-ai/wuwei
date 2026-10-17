# Implementation plan: merge-evidence

**Spec**: specs/merge-evidence/spec.md

## Technical context

Stdlib-only Python 3.11+, `cli/wuwei/evidence.py`. Runtime at 2,976 lines on 86135fa; the item's
budget is +6 lines. No new module, CLI flag, config key or guard route.

## Design

1. `owner_approved`: add `and not row['data'].get('kind')` to the ruling clause.
2. `gaps`: compute `code` (the non-docs, non-spec files) for every PR, and move the generated
   exemption onto the no-test check. The CI not started read becomes `not rollup and code and ...`,
   so a docs-only diff makes no Actions read.
3. The same `try` sets `why`: empty on a good read, ` (Actions host unreadable: <exc>)` on
   `GhError`, `AttributeError` or `TypeError`. The gap text appends `why`.
4. The cached reader is `workflow_paths(pull_request) or workflow_paths(pull_request_target)`, so
   the second read happens only on an empty first answer. No change to `gh.py`.

5. Gate findings at fc27033: a `PROSE` pattern decides the CI read (both names of each file, an empty
   list holds), `gh.pr` carries the previous filename in `renamed` (release() still reads it as
   truthy), and the ruling test is `'kind' not in data` with `head or '-'`. The no-test gap keeps its
   `DOCS` reading and the generated exemption, as on main.

## Constitution check

Stdlib only, test first, shortest diff, no speculative abstraction. Runtime 2,980 after the gate fixes (+4).

## Rollback

Revert the commit.
