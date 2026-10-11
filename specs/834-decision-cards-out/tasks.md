# Tasks: delete decision cards, decide and steward steering; owner decisions come from next on one card

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 9639dd8.
Parts 12 (#832) and 13 (#833) are done on this branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: Keep the Owner step recording and the hook refusal (US5, P1)

- [X] T001 [US5] Move the `record_gate` cases of `tests/test_decision.py` (Owner step, D-n
  hash, Draft) into a new `tests/test_answers.py` importing `wuwei.guards.answers`; point
  `tests/fakes/owner.py` there. Run: red (no module).
- [X] T002 [US5] `git mv cli/wuwei/guards/decision.py cli/wuwei/guards/answers.py`; trim it to
  `record_gate` and its helpers (plan.md); update `guards/__init__.py` `MODULES` and `AREAS`,
  `telemetry.GUARDS` and the `tests/test_hooks.py` pins. Run `tests/test_answers.py
  tests/test_hooks.py tests/test_protect_state.py tests/test_card_confirms.py`: green; the
  `wuwei hook` refusal cases pass unchanged.

## Phase 2: Owner answers and the owner decision rows (US1, US2, US3, P1)

- [X] T003 [US1, US2, US3] Red tests: `tests/test_sessions.py` (`owner_answer`),
  `tests/test_dispatch.py` (PARK and ESCALATE card, Yes, No, a new round, the cap park),
  `tests/test_plan.py` (`plan resume`, a disposition without a record),
  `tests/test_pr_actions.py` (scope card, Yes and No), `tests/test_build.py` (park line),
  `tests/test_next.py` (`verdicts` row with `THEN['owner-step']`). Run: red.
- [X] T004 Add `sessions.owner_answer`, and build `needs_owner` on it. Run
  `tests/test_sessions.py tests/test_card_confirms.py`: green.
- [X] T005 Code changes from plan.md:
  - `dispatch.py`: no `CARD`, `_card` or `_waiting`; the owner card; `_parked` through
    `plan.park`;
  - `plan.py`: `dispose` without a record, `park`, `resume`;
  - `commands/plan.py`: `resume`;
  - `commands/build.py`: `_park`, `parked_line`, `run`;
  - `commands/next.py`: THEN, `approved`, the rows;
  - `pr_actions.py`: the scope card and dispositions;
  - `commands/pr.py`, `closing.py`, `scanner.py`.

  Run `tests/test_dispatch.py tests/test_plan.py tests/test_pr_actions.py tests/test_build.py
  tests/test_build_next.py tests/test_next.py tests/test_stop.py tests/test_close_parked.py
  tests/test_pr_ownership.py tests/test_ziran.py`: green.

## Phase 3: Delete decide, decision and the record producers (US4, P1)

- [X] T006 [US4] Red: `tests/test_outbound_learn.py` answers through `wuwei outbound answer`.
  Then:
  - move the learning card's answer to `wuwei outbound answer`;
  - delete `commands/decide.py`, `commands/decision.py`, `config._from_card` and its helpers;
  - delete the `decide` cases in `tests/test_mcp.py`, `tests/test_card_confirms.py` and
    `tests/test_decision.py`;
  - trim `decision.py` to the record library (plan.md);
  - delete `tests/test_decision_classes.py`.

  Run `tests/test_outbound_learn.py tests/test_mcp.py tests/test_decision.py
  tests/test_card_confirms.py tests/test_config_set.py tests/test_cli.py`: green.
- [X] T007 [US4] Red: `tests/test_brief.py`, the three fixed mandate lines. Then
  `brief.mandate`. Run `tests/test_brief.py tests/test_launch_contract.py`: green.

## Phase 4: Steward steering, the trigger, waits and the digest (US4, P1)

- [X] T008 [US4] Red: no `steward.due` after the interval (`tests/test_traces.py`), and a third
  fix round dispatches without a note (`tests/test_dispatch.py`). Then:
  - edit `steward.py`, `commands/steward.py`, `guards/traces.py`, and `watch.py` (digest,
    waits);
  - delete `tests/test_decision_digest.py`;
  - delete the notes, ack, negotiation, queue, digest and waits cases in
    `tests/test_steward.py` and `tests/test_watch.py`.

  Run `tests/test_steward.py tests/test_traces.py tests/test_watch.py tests/test_dispatch.py
  tests/test_next.py`: green.

## Phase 5: Readers, config and texts (FR-009, FR-010)

- [X] T009 Edit these and their tests (plan.md list): `report.py`, `retro.py`,
  `commands/why.py`, `commands/status.py`, `memory.py`, `sessions.py` (take-over),
  `commands/doctor.py`, `signal.py`, `commands/event.py`, `state.py`, `outward.py`. Run
  `tests/test_report_retro.py tests/test_why.py tests/test_signal_status.py tests/test_memory.py
  tests/test_sessions.py tests/test_doctor.py tests/test_state_allowlist.py
  tests/test_records_after_dryrun4.py tests/test_operator_records.py tests/test_outward.py
  tests/test_tracker.py tests/test_metrics.py tests/test_telemetry.py`: green.
- [X] T010 Red: `init --upgrade` removes `[autonomy]`, `[decisions]`, `[steward]` and
  `owner.verbosity.digest`. Then edit `workspace.py` and the template. Run
  `tests/test_workspace.py tests/test_config_transition.py tests/test_templates_errors.py
  tests/test_docs.py`: green.
- [X] T011 Rewrite `tests/test_path_day.py` and `tests/test_e2e_day.py` to answer the owner
  cards with `tests/fakes/owner.py` and assert no `D-*.md` (SC-002). Delete
  `scripts/headless_e2e.py` and `tests/test_headless_e2e.py`. Run those files and
  `tests/test_process_depth.py tests/test_posture.py tests/test_merge.py tests/test_drafts.py
  tests/test_who.py tests/test_headless_shepherd.py tests/test_shepherd.py
  tests/test_commit_push.py tests/test_guard_mutation.py tests/test_parser_warns.py
  tests/test_shell.py`: green.
- [X] T012 `tests/test_reasons.py`: delete the part 14 LEFT rows and relabel the
  `decision.py` `at the host terminal` row to 18. `tests/test_invariants.py`: drop the rows
  naming deleted functions. Run both: green, with no new LEFT or KEEP row.

## Phase 6: Governance and docs

- [X] T013 Edit the charters (plan.md), then run `bin/wuwei agents build`. Edit the three
  skills, the design spec, the docs pages and README. Run `tests/test_charters.py
  tests/test_agents.py tests/test_skill_evals.py tests/test_docs.py tests/test_tone.py
  tests/test_owner_records_lint.py`: green; re-measure the tone budgets without raising them.
- [X] T014 Run the SC-003 grep; every hit is in `mcp.py` or `commands/outbound.py`.
- [X] T015 Final: run every test file touched above once more. PR body for this part:
  "Closes #834", the owner decision table, the process control table, RETIRED, Handoff and
  Risks.
