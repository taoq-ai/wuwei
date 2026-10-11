# Tasks: exact argv only on the irreversible edges; one edges module; integrity warns at session start

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at d60253b8.
Part 16 (#838) is merged into the base first; locate its code by name.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: Moves with no behaviour change

- [X] T001 `git mv cli/wuwei/guards/commit_push.py cli/wuwei/commit_push.py`. In the same step
  delete its tool guard (`check`, `git_command`, `commit_options`, `push_options`, `GUARDS`,
  the `shell` and `Guard` imports, the constants only they read), the `commit_push` row of
  `guards.MODULES`, and every `guard().check(...)` case and the `UNPARSED` import of
  `tests/test_commit_push.py`. Change the eight importers (plan.md) and the test imports and
  monkeypatch paths (`tests/test_commit_push.py`, `tests/test_doctor.py:403`,
  `tests/test_vcs.py:498`, `tests/test_pr_actions.py:57-59`). The force push refusal returns in
  T004. Run `tests/test_commit_push.py tests/test_git_hook.py tests/test_fast_checks.py
  tests/test_vcs_guard.py tests/test_vcs.py tests/test_pr_actions.py tests/test_doctor.py`:
  green.
- [X] T002 Move `GATES`, `_recorded_gates` and `gate_check` from `guards/pr.py` to
  `cli/wuwei/merge.py`; `guards/pr.py` imports them back for now; `shepherd.py:282` and
  `merge.py:390` import from `wuwei.merge`. Point `tests/test_shepherd.py`,
  `tests/test_templates_errors.py:106`, `tests/test_process_depth.py:251` at `wuwei.merge`;
  move the gate cases of `tests/test_pr_guards.py` (115, 141, 163, 667, 726) to
  `tests/test_merge.py` calling `merge.gate_check`. Run those four files and
  `tests/test_pr_guards.py`: green.

## Phase 2: The edges module (US1, US3, P1)

- [X] T003 [US1] [US3] Write `tests/test_edges.py` (plan.md, tests): the segment splitter
  table, then one table per edge (merge, approve, admin and protection, force push, deploy,
  PR raise) with refused rows (reason text asserted: `bin/wuwei merge`,
  `git push origin HEAD:refs/heads/`, `publish: `, `pr raise: `), allowed near misses, the
  quoted, here-doc and commit-message rows, the heartbeat probe `git push --force origin main`
  refused through `hook.run` in the `wuwei-heartbeat` session, and an enforce-off row per edge through
  `hook.enforce` (floor edges block, force push and PR raise log). Move the deploy table rows
  of `tests/test_deploy.py` and the `gh` body canary rows of `tests/test_canary.py:478,543`
  here. Run: red (no module).
- [X] T004 [US1] `git mv cli/wuwei/guards/deploy.py cli/wuwei/guards/edges.py`; trim it and add
  `segments`, `_git`, `_forced`, `_recorded`, `check_bash`, `check_deploy` (plan.md, Design).
  Run `tests/test_edges.py`: green for every table but outward send.
- [X] T005 [US1] Move part 16's `check_send` into `edges.py` (plan.md, `guards/outward.py`);
  point part 16's send tests (`tests/test_outward.py`, `tests/test_stop.py`,
  `tests/test_profiles.py`, `tests/test_canary.py`) and the outward table of
  `tests/test_edges.py` at `guards.edges.check_send`. Run those files: green.
- [X] T006 [US1] Update the importers of the old deploy module: `commands/init.py:16`
  (`PERMISSIONS_DENY`), `calibrate.py:16` (`VERBS`). Run `tests/test_init.py
  tests/test_calibrate.py`: green.

## Phase 3: The old guards go (US1, US2)

- [X] T007 Delete `tests/test_deploy.py` and `tests/test_pr_guards.py` (their kept rows moved in
  T002 and T003) and `cli/wuwei/guards/pr.py`. Run `tests/test_edges.py tests/test_merge.py
  tests/test_shepherd.py`: green.
- [X] T008 `guards/__init__.py`: `MODULES`, `FLOOR`, `MERGE`, `NO_REVIEWER` and `floor`
  (plan.md). First update `tests/test_hooks.py` (`MODULES` pin, `BASH_GUARDS`, discover
  assert), `tests/test_enforce.py` (edge rows), `tests/test_guard_mutation.py` (edge rows),
  `tests/test_scope_first.py:35`, `tests/test_dispatch.py:2229`, `tests/test_merge.py:507`;
  run them red, then make the change. Run them and `tests/test_telemetry.py`: green after
  T011.

## Phase 4: An unreadable call is logged (US2, P1)

- [X] T009 [US2] Tests first: `tests/test_hooks.py` (an unbalanced-quote `gh` call logs one
  `UNPARSED` `guard.would_refuse` and passes in both settings; no `resolved:` line; no opaque
  warning), `tests/test_protect_state.py` (the `classify` cases become: an unparsed call naming
  a state file returns `UNPARSED` and the hook passes it; a parsed state write still refuses).
  Run: red.
- [X] T010 [US2] `commands/hook.py` (plan.md); `guards/protect_state.py:307-322`;
  `guards/verdict.py:70-72`; `security.py:171-177`. Then delete the `shell.py` functions
  (plan.md table) with their cases in `tests/test_shell.py`, `tests/test_parser_warns.py`
  (keep the three named cases) and `tests/test_seat_command_forms.py` (opaque rows). Run
  `tests/test_hooks.py tests/test_protect_state.py tests/test_verdict.py tests/test_shell.py
  tests/test_parser_warns.py tests/test_seat_command_forms.py tests/test_canary.py
  tests/test_traces.py tests/test_sessions.py`: green.
- [X] T011 `telemetry.py`: `GUARDS` follows `MODULES`, `RETIRED_GUARDS` in `INNER`. Run
  `tests/test_telemetry.py`: green.

## Phase 5: Integrity warns at session start (US4, P1)

- [X] T012 [US4] Tests first in `tests/test_integrity.py`: a failing cached verdict gives no
  PreToolUse refusal for Bash, Write and an MCP tool; SessionStart exits 0 and prints the
  reason in context and stderr; the reconfirm card case stays. Delete the PreToolUse guard
  cases (659, 737, and the hook runs at 250-260, 826-828, 1098-1107 that expect a refusal).
  Run: red.
- [X] T013 [US4] `guards/integrity.py`: delete `check`; `MODULES['integrity']` is
  `{'SessionStart': None}` (already set in T008 if done together). `tests/test_records_after_dryrun4.py:116`
  runs the SessionStart guard. Run `tests/test_integrity.py tests/test_records_after_dryrun4.py
  tests/test_hooks.py tests/test_guard_mutation.py`: green.

## Phase 6: The launch contract (US5, P2)

- [X] T014 [US5] `tests/test_enforce.py`: rows for CAP, host seat ceiling, free memory below the
  floor, free memory unmeasured and a missing ticket (logged with enforce on) and a brief
  mismatch (blocks). Run: expected green with no code change (part 15). If one is red, fix it in
  `guards/__init__.py` `CAPACITY`, not in the guard.

## Phase 7: Corpus, governance, sweep

- [X] T015 Grep (plan.md, Risks) and fix every hit; `doctor.py:336` text; `tests/test_doctor.py`
  for that text.
- [X] T016 `tests/test_invariants.py`: `CALLED`, `EXEMPT`, the integrity row, and the reason
  count (plan.md). Run `tests/test_invariants.py tests/test_reasons.py tests/test_tone.py`: green.
- [X] T017 Design spec 4.1, 4.5, 4.7, 9.1, 9.2 (plan.md). Run `tests/test_docs.py`.
- [X] T018 `docs/site/security.md:66-68`: one paragraph. Run `tests/test_docs.py`.
- [X] T019 Constitution II amendment, version bump, dated line.
- [X] T020 Run every test file touched above once more, together; leave the changes in the
  working tree (no commit).

## Dependencies

T001 and T002 before T007. T003 before T004 and T005. T004 to T006 before T007 and T008. T009
before T010. T012 before T013. T015 and T016 after T010 and T013. T017 to T019 any time after
T008.
