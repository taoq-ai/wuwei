# Specification Analysis Report: 604-config-promote-empty

Artifacts: spec.md, plan.md, tasks.md, against `.specify/memory/constitution.md`, the item's
Acceptance section, the orchestrator notes, and the code on main (reproduced both defects).

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Coverage | HIGH | spec FR-001 (first draft), plan item 1 | The first draft recorded only the value a key held when its answer was recorded. An owner who set a key back to that value after promote, the card path or setup wrote the answer was indistinguishable from an unapplied answer, so promote would overwrite the revert: the deploy.deny case of the item. | Resolved: the record is also updated after every calibration write (card write in `_interview`, `config promote`, `setup`), so it holds the value right after calibration last set the key (the item's "what calibration last wrote"). Spec US1.3, plan items 2 to 4, tests T010 (revert after promote and after the card) and T011 (revert after setup). |
| A2 | Inconsistency | HIGH | tasks T011, T012 (first draft) | The setup test came after its implementation task and could pass without the setup change (a hand edit to a new value differs from the pre-write record anyway). | Resolved: the setup test (T011) precedes the implementation (T012) and sets the key back to its pre-setup value, which only the post-write record catches. |
| A3 | Constitution | MEDIUM | spec Edge Cases, FR-001 | A damaged record makes `calibrate --answer` (the planner's record command) exit 2. #530 forbids new refusals under observe and guarded. | Accepted: not a guard refusal; it is the existing fail-closed rule for a damaged CLI record (as `interview.json` today), exit 2 with the shared `DAMAGED` or `SYMLINK` reason, and only the CLI writes the file. Recorded under Assumptions. |
| A4 | Inconsistency | MEDIUM | spec Edge Cases | "exit 2 before writing" overclaimed for `setup`, which writes other files (init, profile) before it records answers. | Resolved: the edge case says before writing `config.toml` or `interview.json`. |
| A5 | Coordination | MEDIUM | plan item 6, FR-008 | Parallel items (#599, #600, #601) may add 9.2 rows; a fixed I28 may collide. | Resolved: the plan takes the next free id at build time and renumbers on rebase; `test_table_matches_the_checks` pins table and dict order. |
| A6 | Performance | MEDIUM | plan item 6 | `test_invariants_hold` asserts the walk under 1.0 s CPU; I28 runs a record and a promote. | Accepted: I28 reads no dimension (`READS` `()`), runs once, in-process, and `--keys` skips the repository survey; the I23 check does a comparable `main` call. T015 runs the file to confirm the budget. |
| A7 | Scope | MEDIUM | spec Deferred | Profile imports can overwrite an owner change made before their first promote. | Accepted and deferred: promote and setup record every key they apply (profile keys included), so the gap is only before the first promote; recording at `calibrate import` is a follow-up issue to file. |
| A8 | Coordination | LOW | plan items 3, 5 | #600 also edits `config set --from-card`; this item edits `setup.merged` (shared by both paths) and the promote parser in `config.py`, not `_from_card`. | Accepted: small, local edits; a rebase unions them. |
| A9 | Ambiguity | LOW | spec Assumptions | The item writes `config set outbound.default_tier ask`; the host-terminal command takes TOML. | Accepted: tests use `'"ask"'`; bare words stay a card-title form (#579). |
| A10 | Ambiguity | LOW | plan item 3 | The `--keys` digest still lists every stored answer under `Interview answers:`. | Accepted: context only; the diff and the write are limited to the named keys (Assumptions). |
| A11 | Interface | LOW | plan item 2 | `proposal` gains a sixth return value. | Accepted: two callers (`promote`, `setup`), both updated; no test calls it directly. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 | T006, T007, T010, T011, T012 |
| FR-002 | T008, T009, T010, T012 |
| FR-003 | T011, T012 |
| FR-004 | T013, T014 |
| FR-005 | T013, T014 |
| FR-006 | T001, T002, T003 |
| FR-007 | T004, T005, T015 |
| FR-008 | T015 |
| FR-009 | T016 |
| SC-001 | T001, T002, T010, T013 |
| SC-002 | T015 |
| SC-003 | T017 |

Item acceptance: scenario 1 is T010 (`test_promote_keeps_a_key_the_owner_set_after_the_answer`);
scenario 2 is T013 (`test_answer_next_line_names_its_keys`); scenario 3 is T001 and T002;
the invariant row is T015.

Every behaviour has a test task before its implementation task (T001 and T002 before T003;
T004 before T005; T006 before T007; T008 before T009; T010 and T011 before T012; T013 before
T014). No guard, posture or refusal rule changes under observe or guarded (#530); the only
guard edit adds one CLI-written day file to the records floor. Every Next line is an exact
command with its reason (#551). The changed rule (promote skips an owner-set key) has its
9.2 row and its check in `tests/test_invariants.py`.

CRITICAL: 0. HIGH: 2, both resolved in the artifacts. MEDIUM: 5. LOW: 4.

Orchestrator override (2026-10-09, ponytail): no per-day interview-keys.json record; promote skips any present key that differs from a stored answer unless `--keys` names it, so A1, A2, A3, A4 and A7 no longer apply and spec, plan and tasks were rewritten to match.
