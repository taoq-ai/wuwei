# Tasks: `wuwei listen` process, inbox and service templates

Test first: every implementation task follows the test task that must fail before it.
Run tests with `python -m pytest -q <file>` from the repository root. New listener tests
go in `tests/test_listen.py` (fixture described in plan.md, Test plan).

## Setup

- [X] T001 Probe read-only on main: `bin/wuwei listen` is `invalid choice`; `inbox.store`
  has no dedup; health, unit, install, loop and wake are watch-only (spec, Root cause).
- [X] T002 Write spec.md, plan.md and tasks.md.
- [X] T003 Run the full suite and confirm it is green before any change.

## US1: events land in the inbox exactly once, across restarts

- [X] T004 Test in `tests/test_listen.py`: `inbox.store` with one event already stored
  and one id repeated inside the batch stores only the new one, returns its count, and
  leaves one inbox line per `(source, id)`; a corrupt inbox line is exit 2 and stores
  nothing. See both fail.
- [X] T005 Implement `inbox.read(root)` and the dedup step in `inbox.store` in
  `cli/wuwei/inbox.py` (plan section 1). T004 and `tests/test_inbox.py` pass.
- [X] T006 Test in `tests/test_listen.py`: config defaults `listen.poll_seconds == 60`,
  `listen.dead_seconds == 300`, `responder.enabled is True`; add the same to the expected
  map in `tests/test_workspace.py::test_config_defaults_and_independence`. See it fail.
- [X] T007 Implement the `listen` and `responder` entries in `SCHEMA` in
  `cli/wuwei/workspace.py`. T006 passes.
- [X] T008 Test in `tests/test_listen.py`: cursor behaviour through `listen.tick` with the
  fake inbound: first `since == ''`; after a batch the next `since` is the last `ts`,
  also after re-reading `.wuwei/inbox/cursor.json`; an empty poll leaves it; a source
  returning `Result(2, None, 'down')` and a store returning exit 2 leave it and the tick
  returns 2; a corrupt cursor file raises `ValueError`; tick returns 1 when events were
  stored and 0 when none were new. See it fail (no `wuwei.listen`).
- [X] T009 Test in `tests/test_listen.py` (issue acceptance 1): restart mid-batch. Patch
  `state.append_jsonl` to raise `KeyboardInterrupt` on the second inbox line, run
  `listen.tick` (it raises), unpatch, tick again with the same batch: the inbox holds each
  batch id exactly once and the cursor is the batch's last `ts`. See it fail.
- [X] T010 Implement `cli/wuwei/listen.py` `cursor`, `_save` and `tick` without the wake
  block yet (plan section 4). T008 and T009 pass.

## US2: new events wake the planner, unless the kill switch is off

- [X] T011 Test in `tests/test_listen.py`: marker merge through `watch.mark_wake`: a
  pending unseen PR wake plus `inbox=3` gives one marker with the PR and `inbox: 3`; a
  later PR `mark_wake` keeps `inbox: 3` while unseen; `mark_wake(inbox=3)` when the
  marker already covers 3 leaves `at` unchanged; `watch.wake` renders `inbox to line 3`,
  raises on a negative or non-int count, and a PR-only notice is unchanged. See it fail.
- [X] T012 Implement `watch.mark_wake`, switch `watch.poll` to it, and extend
  `watch.wake` in `cli/wuwei/watch.py` (plan section 2b, 2c). T011 and
  `tests/test_watch.py` pass.
- [X] T013 Test in `tests/test_listen.py`: with `responder.enabled` true a tick that
  stores a batch writes one `listen: wake` event and a marker with `inbox` equal to the
  inbox line count; `lifecycle.session_start` shows `planner wake` and `inbox to line`;
  after `main(['plan', 'session', 'planner'])`, `lifecycle.stop` for that session
  consumes it once; a second tick with no new events writes no wake event.
- [X] T014 Test in `tests/test_listen.py` (issue acceptance 2): `[responder]
  enabled = false` stores the batch, writes no `listen: wake` event, `watch.wake(root)`
  is `''` and `woken` stays 0; switching it back to true, one tick wakes once.
- [X] T015 Test in `tests/test_listen.py`: crash between wake and `woken`. Patch
  `listen._save` to raise when the saved `woken` is above 0; the tick raises after the
  wake was marked; unpatch; the next tick leaves the marker's `at` unchanged and a
  planner that consumed the first notice sees none. See T013 to T015 fail.
- [X] T016 Implement the `responder.enabled` wake block in `listen.tick` in
  `cli/wuwei/listen.py` (plan section 4). T013 to T015 pass.

## US3: a dead listener is reported at session start

- [X] T017 Test in `tests/test_listen.py` (issue acceptance 3): `watch.health(root,
  name='listen')` after a `listen: clock` event and 299 s is `(0, '')`, at 300 s is exit 1
  with `listen dead`; with no clock and no unit it is off; with the unit file present at
  `workspace.watch_unit(root, name='listen')[1]` and no clock it is dead;
  `lifecycle.session_start` exits 1 with `listen dead` in the dead case and mentions no
  `listen` in the off and alive cases; `workspace.watch_unit(root)` label is unchanged
  and the listen label starts with `wuwei-listen-`. See it fail.
- [X] T018 Implement `name` in `watch.health` (`cli/wuwei/watch.py`, plan 2a) and in
  `workspace.watch_unit` (`cli/wuwei/workspace.py`, plan 3), and the listener lines in
  `session_start` (`cli/wuwei/guards/lifecycle.py`, plan 8). T017,
  `tests/test_watch.py` and `tests/test_quiet_sweeps.py` pass.

## US4: service install, clean shutdown, one listener per workspace

- [X] T019 Test in `tests/test_listen.py`: holding `.wuwei/listen.lock` makes
  `listen.run(root, once=True)` return 2; a `sleep` raising `KeyboardInterrupt` returns
  0; SIGTERM raised inside the tick (patch `signal.signal` as
  `tests/test_watch.py::test_sigterm_finishes_tick_before_stopping` does) finishes the
  tick and returns 0 without sleeping; the loop sleeps `min(listen.poll_seconds, 120)`.
  See it fail.
- [X] T020 Implement `watch.serve`, rewrite `watch.run` on it (`cli/wuwei/watch.py`,
  plan 2d) and add `listen.run` (`cli/wuwei/listen.py`). T019 and `tests/test_watch.py`
  pass.
- [X] T021 Test in `tests/test_listen.py`: `main(['listen', 'install', '--dry-run'])`
  prints a unit that runs `listen` under a `wuwei-listen-` label and writes nothing;
  `listen install` then `listen uninstall` with a fake `registry.watch_service` on
  `linux` write, load, stop and remove the unit; `main(['watch', 'install',
  '--dry-run'])` output still runs `watch` under a label without `listen`; with
  `inbound = "none"`, `listen --once` and `listen install --dry-run` return 2 with the
  reason and `listen uninstall` returns 0; `main(['listen', '--once'])` with the fake
  inbound returns the tick's code. See it fail.
- [X] T022 Implement `add`, `service` and the thin `register`/`run` in
  `cli/wuwei/commands/watch.py` (plan 5), `@COMMAND@` in `templates/wuwei-watch.plist`
  and `templates/wuwei-watch.service` (plan 6), and `cli/wuwei/commands/listen.py`
  (plan 7). T021, `tests/test_quiet_sweeps.py` and `tests/test_env_credentials.py` pass.
- [X] T023 Test: add `('bin/wuwei listen uninstall', 1)` to the parametrized table of
  `tests/test_quiet_sweeps.py::test_seat_cannot_uninstall_the_watch`; in
  `tests/test_listen.py` assert `main(['event', 'listen: clock']) == 1` and the same for
  `listen: wake`, and that `signal.classify` returns silent for both. See the guard row
  and the tier assertions fail.
- [X] T024 Implement the `('listen', 'uninstall')` row in `_OWNER_ACTIONS`
  (`cli/wuwei/guards/protect_state.py`), the two `EVENT_PRODUCERS` rows
  (`cli/wuwei/commands/event.py`), the two `SILENT` kinds (`cli/wuwei/signal.py`) and the
  `STATE_PRODUCERS['watch']` text (`cli/wuwei/state.py`). T023 and
  `tests/test_signal_status.py` pass.

## Docs

- [X] T025 Test: add `'listen uninstall'` to the command tuple in
  `tests/test_docs.py::test_host_terminal_actions_and_morning_references`. See it fail.
- [X] T026 Implement the docs (plan 10): `docs/site/concepts.md` and
  `docs/site/reference.md` owner-only commands; `docs/site/configuration.md` rows for
  `listen.poll_seconds`, `listen.dead_seconds`, `responder.enabled` and the "Running the
  listener" section. T025 and `tests/test_docs.py` pass.

## Finish

- [X] T027 Run `python -m pytest -q`; everything passes. Check every changed file for
  em-dashes, emojis and absolute local paths and remove any.
