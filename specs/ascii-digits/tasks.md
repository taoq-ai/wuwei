# Tasks: ascii-digits

## Phase 1: Evidence first

- [x] T001 Re-find every `\d` and `isdigit()` in `cli/wuwei` at 0104d00 with `grep -rn '\\d\|isdigit' cli/wuwei`
- [x] T002 Write the tests for acceptance 1 to 5 and run them red at 0104d00: 7 failed, 254 passed

## Phase 2: Readers

- [x] T003 [US1] [US2] [US4] `\d` to `[0-9]` in evidence, guards, upgrade, verdict and hook (FR-001)
- [x] T004 [US3] `__main__._ref` guards `isdigit()` with `isascii()` (FR-002)
- [x] T005 [US1] `hook._answers` reads owner review and breaking rulings from one `REF` search (FR-003)

## Phase 3: Checks

- [x] T006 [US5] The scan test passes; runtime 2,982 at the item commit, 2,988 after merging #1106 (main 2,992) (FR-004, FR-005)
- [x] T007 `setup.vendor('.')`; `bin/wuwei agents check` matches
- [x] T008 Full suite green after the merge of origin/main 23625f3
- [x] T009 Main versus head probe of each acceptance input in a scratch copy of 0104d00
- [x] T010 No emojis and no em dashes in the diff

## Phase 4: Security fix round at cda89f4

- [x] T011 Two-REF and capitalised cases in the hook test, two-REF and fullwidth cases in the guard shape test; red: 4 failed, 708 passed
- [x] T012 Anchor the REF after the class prefix in `hook._answers` (FR-003) and in the guard's shape rule (FR-006)
- [x] T013 Security probes `rulings.py` and `e2e.py` re-run on head: lib#3 and app#9 both not owner approved
