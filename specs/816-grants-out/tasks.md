# Tasks: delete grants; the merge policy alone decides a merge

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at ac5403f.
Parts 9 (#814) and 10 (#815) are done on this branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code.
"Skip if already gone" marks code batches 1 and 2 delete.

## Phase 1: The merge policy alone decides a merge (US1, P1)

- [X] T001 [US1] `tests/test_merge.py`: add `test_an_eligibility_refusal_is_an_owner_block`.
  Set `merge.auto = false` and run `merge.execute`. Expect:
  - exit 1, no merge call;
  - no `decisions/` directory and no `grant.*` event;
  - the last `merge.policy_blocked` has `owner is True`;
  - the reason starts with `merge policy: owner decides:`.

  Parametrize the same test over a tripped breaker, an item outside the approved plan, a risk
  flag, a never-auto path and a diff over `max_changed_lines`. Add `test_quiet_hours_are_a_wait`
  (`owner is False`, reason `merge policy: waits:`). Run: red (the card path).
- [X] T002 [US1] `tests/test_next.py`: add `test_an_owner_merge_block_is_one_park_row`. A
  raised item `A` with PR `org/repo#1`, whose latest `merge.policy_blocked` has
  `owner: true`, gives state `merge`, item `A` and the command
  `wuwei plan park A --reason "the merge policy does not clear org/repo#1"`. With
  `owner: false`, or with a later `merge.intent`, `next` returns the `pr` row. Run: red.
- [X] T003 [US1] Code changes from plan.md:
  - `cli/wuwei/merge.py`: `Owner` and `owner`, no `granted`, no `by_grant` or its fallback,
    the `owner` field in `execute`, the texts;
  - `cli/wuwei/commands/next.py`: `_seen`, the raised row, POSTURES;
  - `cli/wuwei/guards/pr.py:32-33`;
  - `cli/wuwei/pr_actions.py` (106-107, 561).
- [X] T004 [US1] Edit the existing tests:
  - `tests/test_merge.py`, the deletions and conversions plan.md lists;
  - `tests/test_pr_guards.py:238-243`;
  - `tests/test_posture.py:363-368`.

  Run `tests/test_merge.py tests/test_next.py tests/test_pr_guards.py tests/test_posture.py
  tests/test_pr_actions.py`: green.

## Phase 2: Owner-only edges refuse without a grant path (US2, P1)

- [X] T005 [US2] Red tests:
  - `tests/test_deploy.py::test_owner_only_refuses_in_every_posture`: under observe, guarded
    and strict, a `gh release create` from a configured repository is refused with
    `is owner-only: ask the owner to run it in a host terminal`, and no state or decision
    file is written.
  - `tests/test_commit_push.py:931-947`: `test_missing_evidence_refuses_under_guarded`
    returns `(1, MISSING)` and writes no card.
  - `tests/test_shepherd.py:995-1008`: `pr raise` under guarded exits 1 with the gate reason
    and writes no card.

  Run: red.
- [X] T006 [US2] Code changes from plan.md:
  - `guards/deploy.py`: the refusal reason;
  - `guards/commit_push.py`: the comment, the grants call and the `used` loop;
  - `guards/pr.py`: the 214 import, 263 and the `used` loop;
  - `shepherd.py`: the inline posture rule.
- [X] T007 [US2] `tests/test_invariants.py`, the kept wall lint: drop the `grants.py` rows
  from `CALLED` and `EXEMPT` and add the deploy EXEMPT row. Edit
  `.specify/memory/constitution.md` VII with a dated amendment. Edit
  `tests/test_git_hook.py:89-104` before the run.

  Run `tests/test_deploy.py tests/test_commit_push.py tests/test_shepherd.py
  tests/test_invariants.py tests/test_git_hook.py tests/test_vcs_guard.py tests/test_hooks.py`:
  green.

## Phase 3: Planned owner actions are plan lines (US3, P2)

- [X] T008 [US3] `tests/test_plan.py`:
  - replace `test_propose_writes_one_planned_card` and `test_planned_merges_are_gate_cards`
    with `test_owner_actions_are_plan_lines`;
  - delete `test_merge_default_today_writes_no_planned_merge_card` (1006-1017);
  - edit 848-869 and 892-897 to import from `plan`.

  Run: red.
- [X] T009 [US3] Code changes:
  - `plan.py`: move `REPO`, `OWNER_ACTIONS` and `understood`; update `owner_steps`; drop
    `grants.plan` and the planned lines;
  - `commands/plan.py:75-79`;
  - `calibrate.py`: move `_record` into it and point `tests/test_calibrate.py:1305-1312` at
    it.

  Run `tests/test_plan.py tests/test_calibrate.py`: green.

## Phase 4: Nothing names grants (US4, P2)

- [X] T010 [US4] Red tests:
  - `tests/test_workspace.py::test_grant_keys_only_warn`: a `[grants]` standing line and
    `merge.default_tier` load with an unknown-key warning; drop both from the defaults at
    225;
  - `tests/test_cli.py`: `main(['grants'])` raises `SystemExit` 2.

  Run: red.
- [X] T011 [US4] Delete `cli/wuwei/grants.py`, `cli/wuwei/commands/grants.py` and
  `tests/test_grants.py`. Then make the small removals in plan.md:
  - `commands/decision.py`, `report.py`, `state.py`, `signal.py`, `commands/event.py`;
  - `commands/doctor.py`, `workspace.py`, `interview.py`;
  - `dispatch.py:218`, `commands/hook.py`, `decision.py:24`.

  Skip if already gone: `protect_state.py`, `commands/__init__.py`, `__main__.py`,
  `guide.py`, `pace.py`.
- [X] T012 [US4] Test edits that follow:
  - `test_interview.py`, `test_card_confirms.py`: four keys;
  - `test_path_day.py`: `merge.auto` with soak 0, the deploy refusal, no grant asserts;
  - `test_doctor.py`: 505-515;
  - `test_report_retro.py`: 432-447;
  - `test_state_allowlist.py`: 61, 139-141;
  - `test_signal_status.py`: 386;
  - `test_hooks.py`: 280;
  - `test_protect_state.py`: 1055 (skip if gone).

  Run `tests/test_workspace.py tests/test_cli.py tests/test_interview.py
  tests/test_card_confirms.py tests/test_path_day.py tests/test_doctor.py
  tests/test_report_retro.py tests/test_state_allowlist.py tests/test_signal_status.py
  tests/test_decision.py tests/test_protect_state.py`: green.

## Phase 5: Docs, charters

- [X] T013 Docs:
  - design spec 4.6, 4.7, the 5.x mentions, 9.1 and 9.2 (skip the table if gone);
  - `docs/site/concepts.md`, `configuration.md`, `security.md`, `daily.md`, `reference.md`,
    `agent.md`;
  - `tests/test_docs.py`: delete the two grant tests and edit 1550.

  Run `tests/test_docs.py tests/test_tone.py`: green.
- [X] T014 `charters/_common.md:11`, `charters/lead.md:13`, then `bin/wuwei agents build`.
  Run `tests/test_charters.py tests/test_agents.py`: green.

## Phase 6: Close

- [X] T015 Run the SC-002 grep. The only hits left are the ZIRAN role-grant audit, the AUTH
  `'grants*'` heuristic and `outbound.default_tier`.
- [X] T016 Remove unused imports (`PurePosixPath`, `fnmatchcase` in `deploy.py` if only grants
  used them). Run every test file touched in T001 to T014 once more. Leave the changes in the
  working tree. Record the RETIRED-at-rebase keys and the `merge.default_tier` behaviour
  change in the PR body.

## Dependencies

- T001 to T004 come before T011: `merge.py` stops importing grants.
- T005 to T007 come before T011: the guards stop importing grants.
- T008 and T009 come before T011: plan and calibrate stop importing grants.
- T013 and T014 come after T011.

## Implementation notes (lead, after #831)

- No host-terminal text: the deploy guard and `wuwei merge` ask the owner through
  `sessions.needs_owner` (one Owner step card per exact command, and per PR and head for a
  merge). `next` returns a `merge` row that runs `wuwei merge <pr>` for the card; on No the
  planner parks the item. No EXEMPT row was needed in the wall lint.
- `merge.check` collects the owner rules (owner paths included) and checks every
  precondition first; a PR ready but for them is exit 1 with `{'owner': True, ...}`.
- `init --upgrade` maps `merge.default_tier = "today"` to `repos.<n>.merge.auto = true` for
  each repository without its own `merge.auto`; `grants` and `merge.default_tier` are in
  `workspace.RETIRED`.
- `grants.close_merged` (#729) and the `decision.closed` event it alone wrote are deleted.
