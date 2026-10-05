# Tasks: A disposed item never blocks the close through a measurement

Test first: each test task runs and fails before its implementation task.
Fixtures are neutral (items `DIV-1`..`DIV-4`), with a real git repository in `tmp_path`.

## Phase 1: close does not gate on disposed items (US1, US2)

- [X] T001 Test in `tests/test_close_parked.py`: three items parked with `plan park --reason`,
  worktree directories deleted, branches without commits; `closing.unresolved(...,
  notes=notes)` returns code 0 and `notes` holds `DIV-n: parked (<reason>), unmeasured:
  worktree missing` for each.
- [X] T002 Test in `tests/test_close_parked.py`: a carried item whose branch read raises
  (fake vcs) gives a `carried, unmeasured:` note and code 0; the same failure on an open
  item still gives code 2.
- [X] T003 Test in `tests/test_close_parked.py`: a carried item with a pushed branch and no
  PR still yields `pushed branch <b> has no raised or claimed PR`.
- [X] T004 Implement in `cli/wuwei/closing.py` (`unresolved`): dispositions dict with reason,
  `disposed` per item, `notes` parameter, missing-directory and caught-failure facts.
- [X] T005 Test in `tests/test_close_parked.py`: `close.run` on the T001 workspace (other
  obligations satisfied by the fixture) exits 0, prints each note and `steward_launch`;
  with `steward.run` stubbed, a disposed-but-unmeasurable day still calls it; an open item
  exits 1 naming `plan carry DIV-4` and `plan park DIV-4` and does not call it.
- [X] T006 Implement in `cli/wuwei/commands/close.py` (`run`): pass `open_items` and
  `notes`, launch the steward when `not names and code < 2`, print notes.

## Phase 2: close --why (US3)

- [X] T007 Test in `tests/test_close_parked.py`: `close --why` on the open-item workspace
  exits 1, prints one line per item, and leaves `state.json` and `events.jsonl` unchanged;
  on an all-disposed day it exits 0.
- [X] T008 Implement `--why` in `cli/wuwei/commands/close.py` (`register`, `run`).

## Phase 3: gone worktree records (US4)

Deferred to a follow-up issue: the owner asked to cut this run short (weekly limit). Phases 1 and 2 fix the close gate; the stale worktree path stays in state.json until this phase lands.

- [ ] T009 Test in the git adapter test file: `branch_head` returns the tip SHA for an
  existing branch and `None` for a missing one; `worktree_remove` removes a worktree.
- [ ] T010 Implement `branch_head` and `worktree_remove` in `adapters/vcs/git.py` and the
  fakes in `tests/fakes/vcs.py`.
- [ ] T011 Test in `tests/test_close_parked.py`: `workspace.mark_worktree_gone` sets
  `worktree: None` and `worktree_gone {path, branch, last_commit}` and writes one
  `worktree.gone` event; `wuwei event` refuses `worktree.gone` as a reserved kind.
- [ ] T012 Implement `mark_worktree_gone` in `cli/wuwei/workspace.py` and reserve the kind
  in `cli/wuwei/commands/event.py`.
- [ ] T013 Test in the doctor test file: the `worktrees` warn row with apply
  `worktree-gone`; `doctor --fix --apply worktree-gone` marks the three items gone and
  `next` output names none of the old paths; a changed preview applies nothing and exits 1;
  update the FIXES allow-list pin.
- [ ] T014 Implement `_gone_worktrees`, the `_day` row, `_gone_preview`, `_gone` and the
  `FIXES` entry in `cli/wuwei/commands/doctor.py`.
- [ ] T015 Test in the worktree command test file: `wuwei worktree remove DIV-1` removes the
  directory and writes the gone record; an unknown item exits 1.
- [ ] T016 Implement `remove` in `cli/wuwei/commands/worktree.py`.

## Phase 4: polish

- [X] T017 Add `close --why` and `worktree remove` to the command reference where `close`
  and `worktree add` are listed (guide text and docs page); update any test that pins it.
- [X] T018 Run `python -m pytest -q`; check written files for em-dashes, emojis and absolute
  local paths.
