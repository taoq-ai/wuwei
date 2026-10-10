# Tasks: the status line never waits on the network, and doctor names a slow probe

Test first: each test task runs and fails for the expected reason before its
implementation task, except T001, a regression pin that passes on main by design (spec,
Root cause 1). No test reaches the network or waits on a fake's hang. Run only the touched
test file after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the status line and SessionStart stay offline (US1, FR-001, FR-002)

- [X] T001 Test in `tests/test_heartbeat.py`:
  `test_status_line_and_session_start_make_no_port_call(ws, capsys)`. Write
  `[adapters]\ncode_host = "github"\ncalendar = "ics"\n` with the file's `config` helper. Wrap
  the fixture's `registry.load` again with `monkeypatch`: for a kind in
  `('code_host', 'tracker', 'calendar', 'chat', 'inbound', 'review_bot')` return a fake whose
  `__getattr__` returns a function that appends the operation name to a `calls` list and then
  `time.sleep(5)`; every other kind goes to the previous `registry.load`. Save
  `watch.save(root, {'status_line': 'cached line · as of 12:00'})`. Then:
  (a) `status.run(line_args())` returns 0 within 1 s (`time.monotonic`) and prints one line;
  (b) `lifecycle.session_start({'session_id': 's1', 'transcript_path': os.devnull,
  'cwd': str(root), 'hook_event_name': 'SessionStart', 'source': 'startup'})` returns a
  `(code, text)` tuple; (c) `calls == []`. Run it: it passes on main. Confirm it is not
  vacuous by temporarily calling `registry.load('code_host', workspace.load_config(root)).pr('x')`
  at the top of `status.snapshot` and seeing it fail on (a) or (c); revert that edit. No
  implementation task follows. Acceptance scenario US1-3 is already pinned by
  `test_launcher_probe_outcomes` (`status_line` `201 ms over 200 ms`); no new test.

## Phase 2: doctor names a slow probe without reinstall advice (US2, FR-003, FR-004)

- [X] T002 Test in `tests/test_doctor.py`: `test_slow_probe_fix_names_the_cause(ws)`, cases
  on `ws.probes` (reset each case from a copy of the fixture's ok probes):
  1. `status_line` `{'result': 'failed', 'value': '6600 ms over 200 ms'}`, and `refused`,
     `allowed`, `state_write`, `read_loop` ok with `ms` 7100, 5865, 7020, 6490: the
     `status_line` row is `fail`, value `6600 ms over 200 ms`, fix contains
     `fastest hook probe allowed 5865 ms` and `the host is busy`, and `reinstall` is not in it.
  2. Same `status_line`, the four hook probes ok with `ms` 40: fix contains
     `only status --line was slow` and `watch row`; no `reinstall`.
  3. `allowed` `{'result': 'unmeasured', 'value': 'timeout'}` and `refused`, `state_write`,
     `read_loop` also `timeout`: the `allowed` row's fix contains `every hook probe timed out`;
     no `reinstall`.
  4. `allowed` `timeout`, the other three ok with `ms` 40: fix contains
     `only this probe timed out`; no `reinstall`.
  Run it: fails (every case gets the reinstall text).
- [X] T003 Implement in `cli/wuwei/commands/doctor.py`: `TIMED` and `_probe_fix` as
  `plan.md` gives them, and `_guards` calling `_probe_fix(name, probes)`. T002 passes, and
  `test_guards_rows` still passes unchanged (its `refused` `exit 0` case keeps `reinstall`,
  its `plugin integrity` case keeps `fix the integrity row first`).

## Phase 3: docs (FR-005)

- [X] T004 Edit `docs/site/reference.md`: the heartbeat bullet from `plan.md`, after the
  `watch.status_line` bullet. Run the docs tests (`python -m pytest -q tests -k "docs or
  reference"`) and then the full suite.

## Phase 4: finish

- [ ] T005 Full suite `python -m pytest -q` passes. Check the files touched for em-dashes,
  emojis and absolute local paths, and remove any.
