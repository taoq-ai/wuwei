# Tasks: pr-draft-text

## Phase 1: Test first

- [x] T001 [US1] `tests/test_guards.py`: the PR standard note for `gh pr create --draft` holds the three draft-route sentences whole, refuses "request a reviewer" and "before it opened", and shows once per session
- [x] T002 [US1] Run it against the old charter: `pytest -q tests/test_guards.py -k pr_standard_note` gives `1 failed, 1 passed, 1192 deselected`

## Phase 2: Charter

- [x] T003 [US1] `charters/_pr.md` lines 20 to 22: the PR opens as a draft so CI runs, the gates read the draft head, it turns ready once they pass and the shepherd requests the reviewer then, before merge CI is green and every thread answered; the delta sentence kept
- [x] T004 [US2] `setup.vendor('.')` re-vendors `.claude/wuwei/charters/_pr.md`; `bin/wuwei agents build` reports "agents match the charters"

## Phase 3: Verification

- [x] T005 Focused test green: `2 passed, 1192 deselected`
- [x] T006 Mutants in a `git archive` copy of the head under the scratch folder: negate the draft sentence, drop the shepherd clause, restore "Request a reviewer", drop "CI is green", leave the vendored copy stale; each gives `1 failed, 1 passed` on the two acceptance tests, the control `2 passed`
- [x] T007 Full suite: `pytest -q -W error` gives `1685 passed, 2 skipped`; runtime 2,976 lines (`wc -l cli/wuwei/*.py`)
