# Tasks: The loop's remaining joints

Each test task is written and run red before its implementation task, and must fail for
the reason named. Run tests with `python -m pytest -q` from the repository root.

## Joint 1: runtime continue passes the state guard (US1)

- [X] T001 Add failing tests in `tests/test_protect_state.py` (reuse the `workspace`
  fixture and `payload` helper; create `.wuwei/generated/agents/sentinel-quality.md`):
  - through `wuwei hook PreToolUse` in process (as
    `test_discovered_guards_through_hook` does), `bin/wuwei runtime continue '<json>'
    'Recheck Q1.'`, where `<json>` is `json.dumps` of a job whose `prompt` is
    `WUWEI brief: ...\nRead instructions <ws>/.wuwei/generated/agents/sentinel-quality.md
    and brief ...`, quoted with `shlex.quote`, exits 0;
  - `check_bash` returns 0 for `bin/wuwei verdict lint .wuwei/generated/agents/x.md` and
    for `python3 -P -m wuwei runtime continue '<json>' x`;
  - still refused (non-zero): `bin/wuwei state get > .wuwei/config.toml`,
    `cp /dev/null .wuwei/generated/agents/a.md`, `echo x | tee .wuwei/config.toml`.
  Run: the first two groups fail with the state hint (`_write_targets` fallback).
- [X] T002 Implement in `cli/wuwei/guards/protect_state.py`: `_write_targets` returns `[]`
  when `_wuwei_action(argv) is not None` and the program is the real CLI (bare `wuwei`,
  a path `wuwei.shell._launcher` accepts, or `python -P -m wuwei`), with a short comment.
  Any other program named `wuwei` (`./wuwei .wuwei/config.toml`) stays refused. Run T001 green and
  `tests/test_protect_state.py`, `tests/test_owner_actions.py`,
  `tests/test_guard_mutation.py`, `tests/test_seat_command_forms.py` green.

## Joint 2: runtime dispatch accepts gate role names (US2)

- [X] T003 Add failing tests:
  - `tests/test_runtime_cli.py`, fake adapter (pattern of
    `test_runtime_cli_dispatch_and_status`): `runtime.run(action='dispatch', role='arch',
    ...)` passes `sentinel-arch` to `adapter.dispatch`; with
    `seat_policy['sentinel-arch']` set to `codex` (pattern of
    `test_runtime_dispatch_uses_approved_role_policy`), role `arch` selects `codex`.
  - `tests/test_launch_contract.py`, `workspace` fixture: parametrize `arch`, `quality`,
    `security`; write the brief with `brief.write('sentinel-<role>', ...)` as
    `test_runtime_prompt_passes_guard` does, run
    `main(['runtime', 'dispatch', '<role>', relative, 'tree'])`, assert exit 0,
    `agent_type == 'wuwei:sentinel-<role>'`, and `assert_registered` (the PreToolUse
    Agent hook launches the `sentinel-<role>` seat).
  - `tests/test_canary.py`, `secured` fixture (init writes security and generated
    agents): `security.agent_path(root, 'nosuchrole')` returns a path that is not a file
    and does not raise; after deleting `.wuwei/generated/agents/sentinel-arch.md` (chmod
    as needed), `agent_path(root, 'sentinel-arch')` raises naming
    `run wuwei agents build`.
  Run: red (role passed unmapped; unknown role raises the agents build reason).
- [X] T004 Implement in `cli/wuwei/commands/runtime.py`: map the role with
  `dispatch.ROLES` before `registry.runtime_config` and `adapter.dispatch`.
- [X] T005 Implement in `cli/wuwei/security.py`: `agent_path` raises the agents build
  reason only when the plugin charter for the role exists. Run T003 green and
  `tests/test_runtime.py`, `tests/test_adapters.py`, `tests/test_build.py`,
  `tests/test_canary.py` green.

## Joint 3: phases follow raise and merge (US3)

- [X] T006 Add failing tests in `tests/test_state.py`: `state.record_pr(root, 'A', ref,
  raised=True)` moves an approved item in `delta` to `raised`, resets
  `builds['A']['fix_rounds']` to 0, and the `pr.raised` event has
  `phase_changes == {'A': 'raised'}`; from `gate` it also moves; from `fix` it links the
  PR and leaves the phase; `raised=False` (claim) never moves the phase.
- [X] T007 Add a failing test in `tests/test_shepherd.py` (on the `case` fixture of
  `test_raise_checks_gates_then_requests_recent_authors`, item in `delta`): after
  `pr raise` exits 0 the item phase is `raised`.
- [X] T008 Implement in `cli/wuwei/state.py`: extract `_move(data, item, phase)` from
  `transition`; call it from `record_pr` when raising from `gate` or `delta`. Run T006,
  T007 and `tests/test_state.py`, `tests/test_state_allowlist.py` green.
- [X] T009 Add failing tests in `tests/test_pr_actions.py` (use `linked`, which leaves item
  `A` in `raised` with `pr == REF`): set the fake PR to
  `state='closed', merged=True` (plus `merged_at` and `merge_commit` where the fake needs
  them), run `main(['pr', 'state'])`; item `A` is `merged`, the last `pr.action` event
  has `phase_changes == {'A': 'merged'}`, and `main(['report'])` writes a report whose
  Merged section lists `A`. Second case: item moved to `fix` first; observing merged
  leaves `fix` and `pr state` does not exit 2.
- [X] T010 Implement in `cli/wuwei/pr_actions.py`: in `observe`'s `update`, move each item
  linked to `ref` from `raised` to `merged` with `state._move` when the observed state is
  `merged`. Run T009 green.
- [X] T011 Update `tests/test_e2e_day.py::test_scripted_day`: drop
  `day.transition('raised')` and `day.transition('merged')`, assert the phase is `raised`
  after `day.raise_pr()` and `merged` after the merged `pr state`, and read the phase
  sequence from `phase_changes` (see plan.md). Run it green.

## Joint 4: decisions from pr act reach the owner (US4)

- [X] T012 Add failing tests in `tests/test_pr_actions.py`, extending the
  `test_scope_disagreement_creates_decision` setup, with no `decision route` call:
  after `pr act` returns `owner_decision`, `state.read_state(root)['decision_routes']`
  holds the new id and a `decision.routed` event exists; `main(['nudges'])` prints a row
  with `source == 'decision.pending'`, `lane == 'Decisions'`, `tier == 'nudge'` naming
  the id; `main(['status', '--line'])` shows `nudges 1` or more; with
  `wuwei.integrity._host_confirm` patched to confirm, `main(['decision', 'outcome', id,
  'defer'])` exits 0; the next `nudges` has no row for the id. Keep
  `test_answered_scope_decision_routes_by_option` unchanged (its explicit
  `decision route` must stay a no-op exit 0).
- [X] T013 Add failing tests in `tests/test_signal_status.py` (use `day` and `cli`):
  a state with `decision_routes: {'D-2': {...}}` and no outcome lists one
  `decision.pending` nudge and the status line counts it; with
  `decision_outcomes['D-2'] = {'decided_by': 'owner', 'option': 'A', ...}` it is gone;
  `decision_routes` set to a list makes `nudges` exit 2 and `status --line` print
  `WUWEI ? unmeasured`.
- [X] T014 Implement in `cli/wuwei/decision.py`: `route_owner(identifier, fields, root)`
  moved from `commands/decision.decide`; update `cli/wuwei/commands/decision.py` to call
  it. Run `tests/test_decision.py` green (routing behaviour unchanged).
- [X] T015 Implement in `cli/wuwei/pr_actions.py`: `_thread` routes the decision it writes
  with `decision.route_owner` before the `pr.action.decision` write.
- [X] T016 Implement in `cli/wuwei/commands/status.py`: `scan` adds a
  `decision.pending` nudge per routed decision without an owner answer, and raises
  `ValueError` for a non-dict ledger. Run T012 and T013 green.

## Docs and full run

- [X] T017 Update `docs/site/reference.md`: the "Automatic phases" row (raise and merge
  moves), the "Charter names" row (gate aliases for `runtime dispatch`), and the decision
  paragraph (`pr act` routes what it creates). Run `tests/test_docs.py` green.
- [X] T018 Run the full suite with `python -m pytest -q`; everything passes. Check every
  file written for em-dashes, emojis and absolute local paths and remove any.
