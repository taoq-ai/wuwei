# Tasks: The daily path runs without operator repairs

Each test task is written and run red before its implementation task, and must fail for
the reason named. Run tests with `python -m pytest -q` from the repository root.

## Shared helpers (no behaviour change)

- [X] T001 Baseline: run `tests/test_build_next.py`, `tests/test_launch_contract.py` and
  `tests/test_pr_actions.py` green. They are the tests for T002.
- [X] T002 Refactor in `cli/wuwei/brief.py` and `cli/wuwei/commands/build.py`: move the
  event read of `build.next_action` (lines 116 to 119) into `brief.events(root)` and the
  builder launch dict (lines 138 to 142) into `brief.seat_action(role, path, tree, root)`;
  `next_action` calls both. Keep the `invalid build event record` message. Run T001 green.

## US1: the gate flow hands out every seat action

- [X] T003 Add failing tests in `tests/test_dispatch.py` for the fix round (FR-001 to
  FR-003). Setup: the `root` fixture, a worktree directory, and
  `test_pr_actions.completed_build(root, tree)` with the phase still `gate`; record arch
  PASS, quality FIX, security PASS with `record`. Assert `next_step('A', root)` returns
  `{'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}`, the item
  phase is `fix`, `builds.A.action` is `continue` with `resume == 'old-builder'` and
  feedback naming `.../decisions/gate-quality-1.md`, the last event is `build.fix_opened`
  with `phase_changes: {'A': 'fix'}`, and a second `next_step` returns the same dict and
  appends no event. Also: with the build record removed, `main(['dispatch', 'next', 'A'])`
  exits 2 and the phase stays `gate`. In `tests/test_pr_actions.py` (or next to it): a
  `completed_build` without `agent_id` opened from `gate` launches a brief named
  `A-gate-fix`. Update `test_fix_pass_then_only_quality_delta` and
  `test_agent_surface_delta_rescans_and_keeps_manual_findings` to add `completed_build`
  and drop the `state.transition('A', 'fix', root)` right after the `fix` result.
  Run: fails on the missing `command` key and the phase still `gate`.
- [X] T004 Implement FR-001 to FR-003: in `cli/wuwei/dispatch.py`, `next_step` resolves
  `root` first, the gate-phase FIX calls `build.open_fix(item, feedback, root=root)` and
  both fix returns go through `_fix(item, roles)`; in `cli/wuwei/commands/build.py`,
  `open_fix` accepts `gate` and names the gate feedback brief `<item>-gate-fix`; in
  `cli/wuwei/commands/event.py`, the `build.fix_opened` producer hint names both callers.
  Run T003 green and `tests/test_dispatch.py`, `tests/test_pr_actions.py`,
  `tests/test_steward.py` green.
- [X] T005 Add failing tests in `tests/test_dispatch.py` for initial gate launches
  (FR-004, FR-005): in a workspace whose briefs are written by `brief.write` (reuse the
  `tests/test_launch_contract.py` `workspace` setup or the scripted-day `Day` driver), log
  `brief arch A arch-1 --gate --worktree <tree>`; `next_step` returns `gates` with
  `seats == [action]` where `action` equals `brief.seat_action('sentinel-arch', <brief>,
  <tree>, root)` plus `receive == 'wuwei dispatch receive A arch arch-1'`; roles without a
  logged brief have no entry; after the seat is reserved (`seats.arch-1` present) the
  entry is gone. Update the exact-dict asserts at lines 34 and 76 to include
  `'seats': []`. Run: fails on the missing `seats` key.
- [X] T006 Implement `_seats` for the initial round in `cli/wuwei/dispatch.py` and add
  `seats` to every `gates` result. Run T005 green.
- [X] T007 Add failing tests in `tests/test_dispatch.py` for the delta continuation
  (FR-004): with the item in `delta`, the initial quality FIX recorded by seat
  `quality-1` whose seat record is stopped with `agent_id: 'agent-quality-1'` and `head`
  equal to the verdict HEAD, `next_step` returns `seats` with one `continue` action:
  `resume == 'agent-quality-1'`, `agent_type == 'wuwei:sentinel-quality'`, `prompt`
  starting with the seat brief's `launch_prompt` and ending with the feedback, feedback
  naming the first HEAD and `gate-quality-1.md`, and `receive == 'wuwei dispatch receive A
  quality quality-1 --round delta'`. With the seat `head` moved to another sha (the
  continuation ran) or without `agent_id`, `seats == []` and `roles == ['quality']`.
  Run: fails with `seats == []` for the ready seat.
- [X] T008 Implement `_seats` for the delta round in `cli/wuwei/dispatch.py`. Run T007
  green and all of `tests/test_dispatch.py`.

## US2: a merged PR is merged everywhere

- [X] T009 Add failing tests:
  - `tests/test_pr_actions.py` with `linked` (item `raised`): move the item to `fix`, then
    to `delta` (`state.transition`), set the fake PR `state='closed', merged=True` with
    `merged_at` and `merge_commit` (as the scripted day does), run
    `main(['pr', 'state'])`; the phase is `merged`, the last `pr.action` event has
    `phase_changes: {'A': 'merged'}`, `report.build(root)` contains
    `## Merged\n- A (<REF>)`, and `status --line` output contains `merged 1/` and no
    `delta`. Parametrize the start phase over `raised`, `fix`, `delta`. An unmerged PR
    moves nothing.
  - `tests/test_state.py` `test_all_transition_edges`: `fix: ['delta', 'merged']`,
    `delta: ['raised', 'fix', 'merged']`.
  Run: `fix` and `delta` stay put; the edge test refuses `fix -> merged`.
- [X] T010 Implement FR-006: `cli/wuwei/state.py` `PHASES['fix']` and `PHASES['delta']`
  gain `merged`; `cli/wuwei/pr_actions.py` `observe` moves linked items in `raised`,
  `fix` or `delta`; update the `docs/site/reference.md` phase table rows for `fix` and
  `delta` (checked by `tests/test_docs.py::test_reference_verdict_example_and_phase_table`).
  Run T009 green and `tests/test_state.py`, `tests/test_pr_actions.py`, `tests/test_docs.py`.

## US3: one documented daily path, tested

- [X] T011 Add failing tests in `tests/test_docs.py`:
  - `daily` and `recovery` join the page list of `test_site_pages_and_links` (front
    matter, linked from `index.md`).
  - `daily.md` names `/wuwei plan`, `wuwei.tar.gz`, `plan approve`, `build next`,
    `dispatch next`, `pr raise`, `pr state`, `decision outcome`, `close`, and does not
    contain `state transition`, `runtime dispatch`, `runtime continue` or
    `integrity reconfirm`.
  - `recovery.md` names each of those four with the word `recovery`.
  - No line in `docs/site/*.md`, `README.md` or `docs/*.md` matches `\bplanned\b`
    (case-insensitive) together with `manifest`, `canar` or `honeytoken`;
    `concepts.md` contains no `Planned:`.
  - `skills/wuwei-plan/SKILL.md` no longer says to transition the item to `fix` and names
    `seats` and `receive`.
  Run: fails on the missing pages and the planned lines.
- [X] T012 Update the driver `tests/fakes/day.py`: `bash` appends each argv to
  `self.calls`; `Day.gate` writes the brief with the gate role name (`self.brief(role,
  name)`), reads `self.next()['seats']`, executes the matching action with
  `self.runtime.dispatch(action['agent_type'].removeprefix('wuwei:'), action['brief'],
  action['worktree'], False, root=self.root, resume=action.get('resume'))`, then runs
  `shlex.split(action['receive'])[1:]`; add `Day.fix()` that runs `self.next()['command']`
  (split), executes the builder `continue` the same way with `resume`, then `build next`,
  `build check`, `build next` until `done`. In `tests/test_e2e_day.py`
  `test_scripted_day`: replace `day.transition('fix')` and `day.build('builder-fix')` with
  `day.fix()`; compare `day.next()` results by `action` and `roles`; assert no
  `('state', 'transition')` and no `runtime` call in `day.calls`. Run
  `tests/test_e2e_day.py` green (US1 and US2 are in place).
- [X] T013 Add the fourth dry run as a failing test in `tests/test_e2e_day.py`, extending
  `test_solo_owner_raise` (rename to `test_solo_daily_path`): plan, approve, session,
  build, gates with quality FIX, `day.fix()`, the quality delta, raise, `pr state`
  waiting, fake host merged, `pr state` merged; then `report` contains `- A (acme/widget#7)`
  under Merged and `status --line` contains `merged 1/1`; `retro`, `close --check retro`,
  `close` and the Stop hook exit 0. Keep its existing reviewer and chat asserts. Assert the
  `phase_changes` sequence `implement, gate, fix, delta, raised, merged`, no
  `state transition` or `runtime` call, and that for every call in `day.calls` the text
  `wuwei <argv[0]>` (and `wuwei <argv[0]> <argv[1]>` when `argv[1]` is a subcommand
  word, not an item, path or option) appears in `docs/site/daily.md`. Run: fails on the
  missing daily page.
- [X] T014 Write `docs/site/daily.md` and `docs/site/recovery.md`, and edit
  `docs/site/index.md`, `docs/site/concepts.md` (lines 11 and 58, move the "Seat launch
  contract" section to recovery), `docs/site/security.md` (line 50) and
  `docs/site/reference.md` ("Automatic phases", "Delta continuation", "Item phase order"
  intro), as `plan.md` describes. Run T011 (docs parts) and T013 green.
- [X] T015 Edit `skills/wuwei-plan/SKILL.md` (lines 26 and 44 to 48) and
  `charters/planner.md` (line 14) for the new actions; regenerate `agents/planner.md` with
  `bin/wuwei agents build` from the repository root. Run T011 green and
  `tests/test_agents.py`, `tests/test_docs.py`, `tests/test_charters.py` green.

## Finish

- [X] T016 Run the full suite with `python -m pytest -q`; everything passes. Check every
  file written for em-dashes, emojis and absolute local paths; remove any.
- [X] T017 Record the fourth dry run's findings in `specs/238-daily-path/quickstart.md`
  (Findings section): the commands `day.calls` recorded in `test_solo_daily_path`, owner
  interventions, commands the page had to gain, and any remaining seam.
