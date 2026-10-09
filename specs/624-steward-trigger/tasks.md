# Tasks: steward trigger

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process: no runtime adapter launch (`registry.load` faked or asserted
unused), no network, no git. Run only the touched test files, then the full suite with
`python -m pytest -q` from the repository root.

## Phase 1: the default interval (FR-001, US1)

- [X] T001 Test in `tests/test_steward.py`: with an empty config, calling
  `steward.maybe_run_for_tool_calls(count, root)` for count 1 to 250 and appending a
  `steward.run` with `tool_calls` equal to the due count after each new `steward.due` (as
  `wuwei next` would) gives exactly one `steward.due`, at 250; with `[steward]
  every_tool_calls = 100` it gives two, at 100 and 200. Update the defaults table in
  `tests/test_workspace.py` to `every_tool_calls: 250`. Both fail on 50.
- [X] T002 Change the default in `cli/wuwei/workspace.py` (`SCHEMA['steward']`) to 250 and
  bump `CONFIG_CACHE_VERSION` to 15 so a parsed copy cached with 50 goes stale (test in
  `tests/test_workspace.py` fails on 14).

## Phase 2: the steward run waits mid-round (FR-002, FR-003, US2.3, US2.4)

- [X] T003 Test in `tests/test_steward.py`: item `A` in `fix`, then in `delta`;
  `steward.run(root, trigger=...)` for `sweep` and `tool-calls` returns 0, prints
  `steward: waits for A to finish the fix round`, writes no `briefs/steward-*.md`, appends no
  `steward.run` and never calls `registry.load` (monkeypatched to raise). With `A` in `fix`,
  `trigger='close'` still records a `steward.run` with trigger `close` (fake runtime as in the
  existing close tests). Fails: `run` writes a brief today.
- [X] T004 Add `state.mid_round(data)` in `cli/wuwei/state.py` and the early return in
  `steward.run` in `cli/wuwei/steward.py`.

## Phase 3: wuwei next holds the steward rows mid-round (FR-004, US2.1, US2.2)

- [X] T005 Test in `tests/test_next.py`: `approved(root, {'A': ('fix', {...})})` with a running
  builder seat for `A` and a pending `steward.due`: `coarse(root)['state'] != 'steward'`; with
  `A` in `delta`, a running gate seat and an unlaunched `steward.run` brief: no steward launch
  row; after `A` is `merged`, the due row (`wuwei steward run --trigger tool-calls`) returns.
  Fails: next offers the due row today (reproduced).
- [X] T006 Add `not state.mid_round(data)` to the steward block condition in
  `cli/wuwei/commands/next.py` `step` and name #624 in its comment.

## Phase 4: the watch sweep waits mid-round (FR-005, US2.5)

- [X] T007 Test in `tests/test_quiet_sweeps.py`: with an item in `fix`, `watch.sweep(root)`
  does not call `wuwei.steward.run` (monkeypatched to record calls) and leaves
  `saved(root).get('steward_at')` unset; after the item moves out of `fix` and `delta`, the
  next `watch.sweep(root)` calls it once. Fails: the sweep runs the steward today.
- [X] T008 Guard the steward call and the `steward_at` save with `state.mid_round` in
  `cli/wuwei/watch.py` `sweep`.

## Phase 5: the report counts steward runs (FR-006, US3)

- [X] T009 Test in `tests/test_steward.py`: with one `tool-calls`, two `sweep` and one `close`
  `steward.run` event today, `report.build(root)` contains `## Steward runs`, `- close: 1`,
  `- sweep: 2`, `- tool-calls: 1` and
  `Settings: steward.every_tool_calls = 250, watch.sweep_seconds = 7200`; with no run it shows
  `none` under the heading and the settings line; with `[owner.verbosity] report = "brief"` the
  section is present. Fails: no such section.
- [X] T010 Add the section to `cli/wuwei/report.py` `build`, before the brief return.

## Phase 6: docs (FR-007)

- [X] T011 Test in `tests/test_docs.py`: configuration.md has the `steward.every_tool_calls`
  row with `` `250` `` and the words "waits for the round to end"; reference.md has
  `steward: waits for <items> to finish the fix round`; daily.md has `## Steward runs`.
  Fails on the current pages.
- [X] T012 Update `docs/site/configuration.md`, `docs/site/reference.md` and
  `docs/site/daily.md`.

## Phase 7: verify

- [ ] T013 Full suite; grep the changed files for em-dashes, emojis and absolute local paths;
  the pull request body carries the design spec 5.5 proposed text from spec.md.
