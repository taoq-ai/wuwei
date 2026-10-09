# Specification Analysis Report: 600-checks-none

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against
`.specify/memory/constitution.md` (1.5.0) and design 4.1, 5.2, 5.8 and 9.2.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Inconsistency | HIGH | spec US3, US4; plan 4 | The first draft titled the detected option `Recommended`; `decision.record_widget` appends ` (Recommended)` to the recommended title, so the owner would read `Recommended (Recommended)`. | Resolved: the option is titled `Detected`; the Assumption says why. |
| A2 | Constitution (VII, #529) | HIGH | spec FR-010; plan 6 | Correcting config records to two-way and `approach` makes `mandate` take them under autonomous; `config set --from-card` then refuses (no owner answer) and the planner loops, and letting a mandate outcome write config would let a seat-written record change any key (I5, I8, I18). | Resolved: `mandate` returns None for a record that sets a config key (FR-010, T017, T018); only the CLI's own calibrate record is taken under the mandate, with values computed in the same process. |
| A3 | Security (forgeable trust) | HIGH | spec FR-001; tasks T023 | The strict launch clearance could read a seat-writable decision file (`Decided-by: owner`). | Resolved: `checks_answered` requires an owner outcome in that day's CLI-written state; T023 asserts a forged file does not clear it. |
| A4 | Task order | HIGH | tasks Phase 1 | The strict refusal test needed `checks_answered` before the helper existed. | Resolved: strict test and implementation moved to T023 and T024, after T021 and T022. |
| A5 | Coverage gap | MEDIUM | tasks T014 | `config set --from-card D-n` without KEY and VALUE must pass `protect_state` from the planner (I8); the hook is unchanged but the short form was untested. | Resolved: T014 pins it from the planner and refuses it from a seat. |
| A6 | Inconsistency with docs | MEDIUM | spec Assumptions; `docs/site/configuration.md:346` | The card recommends an unmeasured test runner (`make test`), while the docs say a test runner is CI only unless measured. | Accepted: the issue's acceptance requires it; the record is two-way; T028 updates the docs paragraph; a `ponytail:` comment names the ceiling. |
| A7 | Underspecification | MEDIUM | spec Assumptions; plan 4 | "Already proposed" reads live days only, so an archived record lets the repository be proposed again. | Accepted with a `ponytail:` comment and a Deferred line (memory file upgrade). |
| A8 | Compatibility | MEDIUM | plan 5 | Adding `Value` and `Previous` to the field names makes a Context continuation line that starts with `Value:` or `Previous:` in an older record a field. | Accepted: history reads only carry the field; only the new-record lint validates it. T012 keeps a history read unchanged. |
| A9 | Invariant text | MEDIUM | design 9.2 I22 | I22 says a two-way door needs a rehearsed undo; the `config` kind needs none. | Resolved: T028 adds the #600 note to I22; the I22 check (Class and Context only) is unchanged; `undo.REGISTRY` and `undo.missing` stay as they are. |
| A10 | Scope | LOW | plan 4 | A seat may run `calibrate --questions`. | Accepted: detection and the record are deterministic CLI output; the same run from the planner gives the same result. |
| A11 | Edge case | LOW | spec Edge Cases | A fast-check command with `|` cannot sit in a Value cell. | Accepted: the lint rejects the row; a host terminal sets it. |
| A12 | Coordination | LOW | spec FR-011 | Parallel items may also add I25 and up. | Accepted: renumber at merge; `test_table_matches_the_checks` catches a mismatch. |
| A13 | Workflow | LOW | constitution Workflow | Clarify and checklist are separate steps. | Clarifications are answered under Assumptions (AGENTS.md); the checklist runs before implement in the pipeline. |

No CRITICAL findings. All HIGH findings are resolved in the artifacts.

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 no wall below strict, strict asks once | T001, T002, T005, T023, T024, T027 (I25) |
| FR-002 build record and event | T001, T003, T005 |
| FR-003 builder brief line | T006, T007 |
| FR-004 status and doctor | T008 to T011 |
| FR-005 detection | T019, T020 |
| FR-006 the proposal | T021, T022, T025, T026 |
| FR-007 Value and Previous fields | T012, T013 |
| FR-008 `config set --from-card` reads the Value row | T014, T015, T027 (I26) |
| FR-009 two-way config record | T016 to T018, T027 (I27) |
| FR-010 mandate leaves config records to the owner | T017, T018 |
| FR-011 invariants | T027, T028 |
| FR-012 nothing new on a hook path | T004, T014 |

Every behaviour task has a test task before it. No task without a requirement.

## Constitution alignment

- I stdlib: yes. II exits: named in plan. III one function per behaviour: the none state is
  `fast_checks.commands(...) == []`, the config rule is `undo.config_write`. IV test first:
  task order. V ponytail: no new state key, event kind, config key or hook code; reuses
  `grants._record`, `card_write`, `route_owner`, `record_widget`, `watch.days`. VII: one
  refusal removed below strict, none added; strict keeps its refusal; invariants I25 to
  I27 added.

## Metrics

- Requirements: 12 functional; user stories: 5; tasks: 29.
- Coverage: 12 of 12 requirements have at least one test task.
- Critical issues: 0. High: 4, all resolved.
