# Specification analysis: door-hardening

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | promise, NETWORK | The promise lists five network programs; guards.NETWORK also holds gh, http and https | Resolved in Clarifications: the whole set is read as program words, so a URL does not match |
| I1 | Inconsistency | LOW | tests/test_hook.py | The old test held an MCP read tool open on a guard error; the promise makes every mcp__ tool a door | Resolved: the test moved to the door list, Read and Glob hold the open side |
| U1 | Underspecification | LOW | acceptance 3 | "codex() raising" does not name the payload | Resolved: a non-dict tool_input on apply_patch, recorded as an assumption |
| C1 | Coverage | LOW | acceptance 6 | tests/fixtures/routes.json is not on main 1620583 | Runtime held by the size test; route check runs when the fixture lands |

| I2 | Inconsistency | HIGH | acceptance 4 | env runs no program in `env /opt/a=b/git ...`; the NAME=value rule opened wrapper bypasses | Resolved in the fix round: acceptance withdrawn by the planner, main's rule restored, nine shapes pinned |
| U2 | Underspecification | MEDIUM | hook.pre_tool | The #1091 hook-seen stamp could abort pre_tool and refuse every MCP call | Resolved: the stamp runs in its own try; test T014 |

No open finding above LOW; I2 and U2 are resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 DOORS table read by both | yes | T003, T007, T009 | |
| FR-002 stripped DOOR_WORDS match | yes | T001, T009 | |
| FR-003 network and MCP doors | yes | T001, T002, T009 | |
| FR-004 codex inside try | yes | T004, T009 | |
| FR-005 main's _unwrap rule kept | yes | T005, T013, T016 | acceptance 4 withdrawn by the planner |
| FR-007 hook-seen stamp cannot decide | yes | T014, T016 | |
| FR-006 budget and routes | yes | T012 | size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
