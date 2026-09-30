# Tasks: The delivery journey is the release criterion

Each test task is written and run red before its implementation task, and must fail for
the reason named. Run tests with `python -m pytest -q` from the repository root.

## Part 1: the product moves `gate` to `fix` (US1)

- [X] T001 Add failing tests in `tests/test_dispatch.py` (reuse the `root` fixture and
  `record` helper):
  - arch PASS, security PASS, then quality FIX: after the third `record`, the item phase
    is `fix`, and the last `gate.received` event in `events.jsonl` carries
    `phase_changes == {'A': 'fix'}`;
  - three PASS: phase stays `gate`, `next_step` returns `raise`;
  - FIX plus PARK (quality FIX, security `Verdict: PARK`): phase stays `gate`,
    `next_step` returns `escalate`;
  - FIX recorded with security still missing: phase stays `gate`, `next_step` returns
    `gates` for `security`.
  Run: the first case fails (phase is `gate`, no `phase_changes`).
  Superseded on rebase onto #238: the first case now asserts the item stays in `gate`
  with no `phase_changes` on `gate.received`, and `dispatch next` moves it to `fix`.
- [X] T002 Change the scripted day to assert instead of repair: in
  `tests/test_e2e_day.py:34` replace `day.transition('fix')` with
  `assert day.data['items']['A']['phase'] == 'fix'`. Run: fails at that assertion (phase
  `gate`).
- [X] T003 Implement FR-001 in `cli/wuwei/dispatch.py` `receive`, inside `update(fresh)`
  after the verdict is stored: for `round_name == 'initial'`, when all three
  `_record(fresh, item, role, 'initial')` exist, one is FIX and none is PARK or ESCALATE,
  `state._move(fresh, item, 'fix')`. Run T001 and T002 green.
  Superseded on rebase onto #238: the move was removed from `receive`; `dispatch next`
  owns it through `build.open_fix`.
- [X] T004 In `tests/test_dispatch.py`, replace the now-illegal
  `state.transition('A', 'fix', root)` after the last initial receipt (lines 74, 92, 140,
  158, 325, 514) with `assert state.read_state(root)['items']['A']['phase'] == 'fix'`;
  keep lines 79 and 147 (from `delta`). Run `tests/test_dispatch.py` green.
  Superseded on rebase onto #238: unit tests without a build keep
  `state.transition('A', 'fix', root)` as setup; tests that call `dispatch next` assert
  the phase.
- [X] T005 Remove `Day.transition` from `tests/fakes/day.py`; in `Day.gate`, store the
  `runtime dispatch` stdout per seat name in `self.jobs` and pass it to `runtime continue`
  for the delta. Run `tests/test_e2e_day.py` green and confirm
  `grep -n "transition" tests/test_e2e_day.py` shows only the `phase_changes` read.
  Superseded on rebase onto #238: `Day.gate` runs the seat actions from `dispatch next`
  (a `continue` action with `resume` for the delta) and `self.jobs` is gone.
- [X] T006 Update `skills/wuwei-plan/SKILL.md` line 48 and `docs/site/reference.md` line 95
  as the plan states (text only, no behaviour; `tests/test_docs.py` is the only test that
  reads either file). Run `tests/test_docs.py` green.

## Part 2: skips are unmeasured (US3)

- [X] T007 In `tests/test_headless_e2e.py`, change
  `test_no_key_skips_before_any_external_call` to expect `runner.main([]) == 2` and
  `'headless e2e unmeasured: ANTHROPIC_API_KEY is not set'` in stdout. Run: fails (exit 0,
  "skipping").
- [X] T008 Implement in `scripts/headless_e2e.py` `main`. Run T007 green; run
  `test_paid_job_and_local_run_are_documented` green (the workflow text is unchanged).

## Part 3: the rehearsal (US2)

- [X] T009 Add failing tests in `tests/test_headless_e2e.py` for bounds:
  `adapter.claude_command(plugin)` is unchanged (existing test stays green) and
  `claude_command(plugin, turns=150, budget=15, resume='s1')` carries `--max-turns 150`,
  `--max-budget-usd 15` and `--resume s1`. Run: fails (unexpected keyword).
- [X] T010 Implement the keyword parameters in `scripts/headless_adapter.py`
  `claude_command`. Run T009 green.
- [X] T011 Add failing tests for preconditions: `main(['--rehearsal'])` with
  `exercise`, `prepare` and `adapter.run` patched to `pytest.fail`, and in turn no
  `ANTHROPIC_API_KEY`, no `WUWEI_REHEARSAL_REPO` (and an invalid `not-a-repo` value), no
  `GH_TOKEN`, no host terminal (patch the tty probe), returns 2, prints
  `rehearsal unmeasured: <reason naming the variable or terminal>`, and the last stdout
  line parses as JSON with `verdict == 'unmeasured'`, `cost_usd is None` and all seven
  keys. Run: fails (no `--rehearsal`).
- [X] T012 Implement `preconditions`, `report`, the `--rehearsal` flag and the early
  return in `rehearse` in `scripts/headless_e2e.py`. Run T011 green.
- [X] T013 Add failing tests for the oracle: a `rehearsal_evidence()` helper (pattern of
  `evidence()`) returning state, events and hook rows for a complete journey (build next
  `continue` result, quality initial FIX and delta PASS, `pr.raised`, `decision.decided`
  for `D-1`, `merge.auto`, `phase_changes` sequence ending `merged`, close requested,
  seats stopped); `rehearsal_findings` returns `[]`; parametrized mutations (no-continue,
  no-fix, no-delta, no-raise, no-decision, no-merge, not-merged, no-close, live-seat,
  manual `state transition A fix` observer row) each return a finding naming the step.
  Run: fails (`rehearsal_findings` missing).
- [X] T014 Implement `rehearsal_findings` in `scripts/headless_e2e.py`. Run T013 green.
- [X] T015 Add failing tests for `measure` and `report`: two `hook.refusal` events and one
  observer `cli` row exiting 2 give three `refusals`; a manual `state set` row and the
  planned decision give two `interventions`; results with `total_cost_usd` 1.5 and 2.25
  give `cost_usd == 3.75`, one missing gives `None` and `cost unmeasured` in the verdict
  line; `report` returns 0, 1, 2 for pass, fail, unmeasured and ends with the JSON line.
  Run: fails (functions missing).
- [X] T016 Implement `measure` and complete `report`. Run T015 green.
- [X] T017 Add a failing test for the repository fixture: with `GH_TOKEN` set, a local
  bare repository as `url` (one commit on `main`, `HEAD` pointing at it) and
  `checked`/`adapter.run` for `gh api user` patched to return a login,
  `prepare(tmp_path, repo='acme/rehearsal', url=<bare>)` returns a workspace whose
  `config.toml` loads through `wuwei.workspace.load_config` with `code_host == 'github'`,
  the repo `merge.auto` true, `merge_deploys` false, `soak_minutes == 0`, `remote ==
  'origin'`, `owner.handles == [login]`; the clone keeps `origin`; `env` has `GH_TOKEN`,
  no `WUWEI_NOW`, and `GIT_CONFIG_GLOBAL` names a file under the scratch HOME; running the
  fast check in the clone exits 1 and prints the `checked:` line, and exits 0 after that
  line is added to `REHEARSAL.md`. Run: fails (unexpected keyword `repo`).
- [X] T018 Implement the `repo`/`url` branch of `prepare` in `scripts/headless_e2e.py`.
  Run T017 green and `test_scratch_build_and_observer_preserve_hook_results` green.
- [X] T019 Add a failing test for the owner answer and the session flow: with
  `adapter.run` recorded and returning canned Claude results (session one with
  `session_id` and `total_cost_usd`, session two likewise), a canned `D-1.md` with
  `Recommendation: B`, and `rehearsal_findings` fed recorded evidence, `rehearse` calls
  `decision outcome D-1 B` with `own_group=False`, calls session two with `--resume
  <session one id>`, passes the rehearsal bounds, and returns 0 with the JSON line's
  `interventions == ['decision outcome D-1 (planned, host terminal)']`; a non-zero
  `decision outcome` returns 1 without starting session two; a session result with
  `is_error: true` returns 2. Run: fails.
- [X] T020 Implement `rehearsal_prompt`, `owner_decision` and the body of `rehearse`, and
  make `check_result` return the parsed dict. Run T019 green and the whole of
  `tests/test_headless_e2e.py` green.

## Part 4: documentation (US4)

- [X] T021 Add failing assertions in `tests/test_docs.py`: add `'rehearsal'` to the
  `pages` tuple of `test_site_pages_and_links`, and a test that `docs/site/rehearsal.md`
  contains `python3 scripts/headless_e2e.py --rehearsal`, `WUWEI_REHEARSAL_REPO`,
  `GH_TOKEN`, `ANTHROPIC_API_KEY`, `--local-login`, `decision outcome`, `unmeasured`,
  `exit 2` and `before a release`; and that `docs/headless-e2e.md` no longer says
  `credential skip`. Run: fails (page missing).
- [X] T022 Write `docs/site/rehearsal.md`, link it from `docs/site/index.md`, update
  `docs/headless-e2e.md`. Run T021 green.

## Finish

- [X] T023 Run the full suite `python -m pytest -q`; all green. Check every file written
  for em-dashes, emojis and absolute local paths and remove any.
