# Tasks: a message to the owner records outward.to_owner under every connector mode

Test first. The behaviour already holds on the base (spec Root cause), so the test task is a
regression guard: it is written and run before anything else, and the implementation task
runs only if it fails.

## Phase 1: one test per mode (US1)

- [X] T001 Test in `tests/test_outward.py`: `test_guard_to_owner_every_mode`, parametrized
  over `send`, `draft` and `refuse` (plan, Changes). Run
  `python -m pytest -q tests/test_outward.py -k to_owner_every_mode`. Expected on the base:
  three passes (US1 scenarios 1 to 3). Record the result.
- [X] T001a See it fail for the right reason (constitution IV): temporarily remove the
  `state.append_event('outward.to_owner', ...)` call in `cli/wuwei/outward.py`
  (`check_tier`), rerun T001's command, confirm all three cases fail on the event list
  (`[] == [{'channel': 'slack'}]`), then restore the line exactly. The diff after this task
  touches only `tests/test_outward.py`.
- [X] T002 Implement, only if T001 fails for a mode: in `cli/wuwei/guards/outward.py`
  (`_check`) or `cli/wuwei/outward.py` (`check_tier`), make that mode's path reach the one
  shared owner check that appends `outward.to_owner` (plan, Contingency). Otherwise mark it
  done as not needed.

## Phase 2: verification

- [X] T003 Run `python -m pytest -q tests/test_outward.py -k to_owner` and the full suite
  `python -m pytest -q`; all green. Check the changed files for em-dashes, emojis and
  absolute local paths.
