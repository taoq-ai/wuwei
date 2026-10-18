# Specification analysis: wide-specs

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise (2) | Whether a contract file pattern (OpenAPI, `.proto`) inside `specs/` also takes arch | Resolved in Clarifications and Assumptions: yes, the contract rule applies to spec files too |
| A2 | Ambiguity | LOW | promise (1) | Whether a code file under `specs/` counts twice | Resolved: one filter, each file once |
| C1 | Coverage | MEDIUM | `gate_gaps` | The delta rule changes through `needed` with no test of its own | Resolved: T003 pins a long docs delta, a 200 and a 201-line spec delta, and a spec contract delta |
| C3 | Coverage | LOW | `CONTRACT` | Mutants (no `re.I`, no `^` anchor) survived at a7654a8 | Resolved: a mixed-case spec contract row and a top-level `contracts/` code row |
| B1 | Inconsistency | MEDIUM | PR title, spec | Declared not breaking; arch found new holds | Resolved: `!`, `BREAKING CHANGE:`, a Breaking section with migration |
| U2 | Inconsistency | MEDIUM | `TEXT` | A second prose test read every `.txt` as prose, so `requirements/prod.txt` and `CMakeLists.txt` lost arch (security at 4b535bd) | Resolved: `wide` reads the one `PROSE` regex; rows pin both and the seat-loaded files |
| C2 | Coverage | LOW | acceptance 1 | Holds on main already, so it cannot run red | Pinned anyway; noted in SC-001 |
| U1 | Inconsistency | MEDIUM | code under `docs/`, `LICENSE`/`NOTICE` prefixes | `wide` built from `code` dropped non-prose files under `docs/` and paths starting `LICENSE` or `NOTICE`, and the contract check missed `docs/openapi.yaml` (security and arch at a7654a8) | Resolved in the fix round: `wide` reads a narrow prose test (`TEXT`), the contract check reads every file; five tests pin it |

No open finding: A1, B1, C1, U1 and U2 (MEDIUM) are resolved; A2, C2 and C3 are LOW and resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 wide counts code and specs | yes | T001, T002, T006 | |
| FR-002 spec contract takes arch | yes | T001, T007 | |
| FR-003 delta rule follows | yes | T003 | |
| FR-004 rules, agents, vendor, runtime | yes | T004, T008, T009, T010 | |

## Constitution alignment

Stdlib only, test first, no config key, no new door, runtime within the cap. No violation.

## Metrics

- Requirements: 4; tasks: 16; coverage 100 percent
- Critical issues: 0; high: 0
