# Tasks: The scripted day runs every call through the hooks with the real launcher

Each test task is written and run red before its implementation task. Run tests with
`python -m pytest -q` from the repository root. Only `tests/fakes/day.py` and
`tests/test_e2e_day.py` change.

## US1: every planner call through PreToolUse with the launcher, owner calls refused

- [X] T001 In `tests/test_e2e_day.py`, add `test_day_names_the_reintroduced_bug`
  parametrized over `launcher` (a `Guard('PreToolUse', 'Bash', ...)` appended to
  `wuwei.guards.deploy.GUARDS` that returns exit 2 for any command containing
  `str(LAUNCHER)`; expect `AssertionError` matching `wuwei rank`) and `close_trap`
  (`wuwei.guards.stop.GUARDS` replaced by a guard calling `stop.check` with
  `stop_hook_active` forced to False; expect `AssertionError` matching
  `'stop_hook_active': True`), each running `test_scripted_day(day)` in `pytest.raises`.
  In `test_scripted_day`, after the first Stop block add `day.hook('Stop',
  stop_hook_active=True)`; add the owner decision steps: write `decisions/D-1.md` from
  `test_decision.VALID` (one-way, `Decided-by: owner`), `day.run('decision', 'route',
  'D-1')` before the first close, assert `'D-1: pending owner decision'` in the first close
  output, after `close --check retro` patch `wuwei.integrity._host_confirm` through
  `day.patch` and call `day.owner('decision', 'outcome', 'D-1', 'A')`, assert `D-1` absent
  from the second close output and `'- D-1: A'` in `report.md`. Run: red (`Day` has no
  `owner`; the launcher mutation does not raise because `Day.run` skips the hook).
- [X] T002 In `tests/fakes/day.py`, add `LAUNCHER` and `shlex`; split `Day.run` into
  `_main(args, expected, stdin, step)` (assertion message `(step, code, out, err)`), `run`
  (PreToolUse Bash through `bash(args)` must exit 0, then `_main`), `owner` (`bash(args,
  expected=2)`, then `_main`) and `bash(args, expected=0)`; make `hook` call `_main` with
  step `('hook', event, fields)`. Run T001 and the whole file: green.

## US2: the delta round continues the same sentinel

- [X] T003 In `tests/test_e2e_day.py` `test_scripted_day`, after the delta gate assert
  `'quality-delta' not in day.data['seats']` and that `quality-initial` is stopped. Run:
  red (the helper still launches a fresh `quality-delta` seat).
- [X] T004 In `tests/fakes/day.py`, add `resume=None` to `Runtime.dispatch` (put it in the
  Agent `tool_input` when set), add `Runtime.continue_job(job, feedback, *, root=None)`
  that re-dispatches the stopped seat from `data['seats'][job['id']]` with
  `resume=job['id']`, and make `Day.gate` with `round_name='delta'` run `runtime continue`
  with `{"id": "<role>-initial"}` and receive that seat name with `--round delta`. Run:
  green.

## US2: solo-owner raise

- [X] T005 In `tests/test_e2e_day.py`, add `test_solo_owner_raise(tmp_path, monkeypatch)`
  building `Day(tmp_path / 'workspace', monkeypatch, solo=True)`, running plan, approve,
  `plan session planner`, build, three PASS gates, asserting `next()` is `raise`, raising
  with exit 0 and asserting `pr_reviewers[ref] == []`, one `create_pr`, no
  `request_reviewers` call and no chat call. Run: red (`solo` is not a `Day` argument).
- [X] T006 In `tests/fakes/day.py`, add `solo=False` to `Day.__init__`: the solo config has
  `[shepherd] min_reviewers = 0` and `[adapters] chat = "none"` in place of the reviewer
  channel, lead and authors, and the vcs authorship row is the owner's
  `builder@example.test`. Run: green.

## US2: dead-watch page

- [X] T007 In `tests/test_e2e_day.py` `test_scripted_day`, after `pr ping`: append a
  `watch: clock` event, set `WUWEI_NOW` to `2026-09-29T12:30:00Z` through `day.patch`,
  assert `nudges` lists one `watch: health` page, append a fresh clock event and assert
  `nudges` lists no `watch: health` row. Run: green on main (shipped by #210; the step is
  coverage, the hook wrapper from T002 already routes `nudges` through PreToolUse). If a
  later step depends on the clock, apply the fallback in `plan.md` Risks.

## Polish

- [X] T008 Run `python -m pytest -q tests/test_e2e_day.py` and confirm the file runs in
  under 30 s; then the full suite `python -m pytest -q`: all green.
- [X] T009 Check `tests/fakes/day.py`, `tests/test_e2e_day.py` and this feature directory
  for em-dashes, emojis and absolute local paths; remove any.
