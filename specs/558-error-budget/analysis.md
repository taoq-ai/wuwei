# Specification Analysis Report: 558-error-budget

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`,
design 5.6, 5.8.1 and 9.2, and the code on the worktree base (352e621).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Correctness | HIGH | spec Root cause, FR-005; plan `cruise.py` | The 5.8.1 promotion condition "no reversal" holds today only because every reversal lowered the class and reset its `changed` stamp, which `agreements` counts from. Deleting the single triggers without a replacement would let a class with reversals and 10 agreements get a raise card. | Make the check explicit in `propose`: no budget event of the class after its last change within `promote_days`, besides the spent check the issue asks for. | Resolved in spec US4 scenario 2 and FR-005, plan `propose`, tasks T021 and T022. |
| H2 | Test first | HIGH | tasks.md T002 and T015/T016 (first draft) | The docs key test was extended inside the implementation task, and the `tests/test_signal_status.py` map entry came after the writer, so neither would be seen failing first. | Extend `test_cruise_mode_ships` in T001; add the `cruise.burn` map entry in T015 before the writer in T016 (the map entry fails while the kind is not emitted). | Resolved in tasks.md T001, T015, T016. |
| H3 | Design | HIGH | spec US2, plan design amendment | The restore lands a level raise through `promotion.cruise_level` without the morning-gate approval 5.8.1 requires for every raise; read silently it contradicts the design. | The issue asks for it explicitly; the amendment states the restore is the one raise without a card and only back to the held level, never above it or the ceiling. The hold is written only by the budget lowering. | Resolved in plan (design spec bullet) and spec FR-003. |
| M1 | Spend rule | MEDIUM | spec Assumptions 1, FR-002 | "At least two events before the budget can be spent" could also mean an allowance floor of two (three events to spend). Acceptance 3 (2 events, allowance 2, not spent) fits both readings. | Take the reading that changes least: spent needs more events than the allowance and at least two. A small class (5 answers) is spent at two events. | Accepted; recorded as an assumption. |
| M2 | Trust | MEDIUM | spec FR-001 | Answered is the denominator, and cruise answers come from records seats write; many trivial records could dilute a class's share. | Cruise answers are capped by `max_per_day` (20) and listed in the digest; the weekly sample still re-asks the owner. No new trust: every counted event is a CLI-written kind already reserved. | Accepted. |
| M3 | Cost | MEDIUM | plan `steward.py` | `steward.review` runs on every `dispatch next`, so the budget reads 14 days of event streams per planner step; `propose` reads the window twice (table and promotion events). | Same call site and failure surface as `cruise.escaped`, never on a hook path. If it shows in timing, `propose` can call `select` once with the longer window and filter. | Accepted. |
| M4 | Timing | MEDIUM | spec Assumptions 4 | An escaped defect is dated at its cruise answer's time; `metrics._escaped` has no detection time, so an escape found late about an old answer is not counted, and a fresh one can enter the 48-hour burn. | Keep the ponytail ceiling and its comment; a detection timestamp belongs to the 5.6 metric, not this item. | Accepted. |
| L1 | Status line | LOW | spec FR-007 | Only held classes appear in the status line; a spent class at L0 has nothing to lower and shows only in `wuwei cruise budget`. | Matches "runs one level lower"; L0 already asks the owner. | Accepted. |
| L2 | Wording | LOW | spec FR-007 | The status part uses the middle dot from the issue (`cruise L2 · budget defer spent`), the only non-ASCII character in the line. | Follow the issue text; the builder checks no test pins the line to ASCII. | Accepted. |
| L3 | Ordering | LOW | tasks.md T024 | The `bin/wuwei cruise` row in `docs/site/reference.md` lands with the command, since `test_reference_lists_every_cli_command` is red from the moment the command registers. | Transient inside one task; the existing test is the failing test. | Accepted. |
| L4 | Parallel work | LOW | plan design and invariants | Other items add 9.2 rows the same day; `I11` may be taken on the base the builder starts from. | Use the next free id and keep the table and `INVARIANTS` in the same order. | Noted. |
| L5 | Workflow | LOW | constitution Workflow | `clarify` and `checklist` are not part of this stage; the orchestrator scopes this run to specify, plan, tasks and analyze. | Run them before implement as the pipeline schedules. | Noted. |

No CRITICAL findings. No absolute local path, owner name, client name, emoji or em-dash in
the artifacts. `tests/test_invariants.py` exists on the base, so the decision rule gets its
row (`I11`) in design 9.2 and its check in the test (T027, T028).

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 window reader shared with #559 | T005, T006 |
| FR-002 allowance, spent, burn, state | T003, T004, T007, T008 |
| FR-003 steward lowers, restores, nudges; hold in `cruise.json` | T009 to T018 |
| FR-004 single triggers removed | T019, T020 |
| FR-005 promotion gate | T021, T022 |
| FR-006 `wuwei cruise budget` | T023, T024 |
| FR-007 status line part | T025, T026 |
| FR-008 config keys and check | T001, T002 |
| FR-009 `cruise.burn` reserved, nudge tier | T013, T015, T016 |
| FR-010 design, invariant, docs | T027 to T029 |
| #558 acceptance 1 to 4 | T011, T012, T013, T021 |
| SC-004 full suite | T030 |

## Constitution

- I stdlib only: one new module on `datetime`, `pathlib` and existing helpers.
- II exits: a damaged stream or `cruise.json` raises `ValueError`; `wuwei steward` and
  `wuwei cruise budget` exit 2 with the reason; a class is never reported clean when its
  window could not be read.
- III one behaviour, one function: `select`, `measure`, `evaluate`; level writes only through
  `promotion.cruise_level`.
- IV: every behaviour task has its failing test before it (H2 resolved).
- V: no new state file, class or abstraction; four functions deleted for one module added.
- VII and #530: no new refusal; a lowered class sends its records to the owner as a card.
  `cruise.burn` is reserved to `wuwei steward run`; `cruise.json` stays seat-protected.
- #551: the burn nudge names its command (`wuwei cruise budget`); a lowering or restore
  needs no planner step.
