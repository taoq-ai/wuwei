# Specification analysis: forge-door

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance, the lead's scope and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Scope | MEDIUM | spec.md promise, acceptance 1 | The item's promise names "a script file under the workspace that imports wuwei" and acceptance 1 counts 7 shapes; the lead's scope keeps the 2 script-file shapes open | Accepted by the lead's scope: recorded under Assumptions in the spec and the PR body, and in SECURITY.md; owned by hook-transcript or an owner scope decision |
| A2 | Coverage | MEDIUM | spec.md How this fails 2 | A wrapper in front of a program word sh fills in (`env "$W" hook Stop`) and runners outside the wrapper list (`setsid`, `find -exec`, `eval`) pass | Accepted as open: the wrapper rule is unchanged, and SECURITY.md already lists both the wrapper case and a variable as the program name for every door |
| A3 | Coverage | LOW | probe nameless class | A command naming neither wuwei nor hook (`"$W" "$SUB"` from the environment) passes, 960 probe commands | Accepted: the guard lets through a command that names no door; counted on its own in the probe |
| A4 | Ambiguity | LOW | spec.md Clarifications | What "naming the module" means | Resolved: a bare `wuwei` word, not a path; `-mwuwei hook` is read by the CLI rule |
| A5 | Performance | LOW | plan.md Design | Two drafts were quadratic (a filled word read at every position; FORGE read per segment) | Resolved: possessive, word-anchored FILLED; one read per command; tests hold both |
| C1 | Consistency | LOW | tasks.md, plan.md | Runtime grows by 8, the whole budget | Accepted: within the item's budget; no other runtime change |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 the readable shapes are refused | yes | T001, T005, T007, T010 | |
| FR-002 legitimate commands and routes pass | yes | T002, T007, T012 | 5 routes move, all added by this item |
| FR-003 the generated probe has no holes | yes | T009, T010 | 33,528 in scope, 0 holes at the head |
| FR-004 the docs name the open case and the new shapes | yes | T008 | |
| FR-005 budget, copies and agents | yes | T006, T015 | |

## Constitution alignment

No conflict: stdlib only, an auditor that refuses and writes nothing, test first, runtime held at
the item's budget.
