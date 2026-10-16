# Tasks: the manifest signing code moves out of the runtime into the release script

## Phase 1: Tests first

- [x] T001 Verify no runtime caller (`git grep -n integrity`: only scripts/build-release.py)
- [x] T002 [US1] Build and verify a signed archive with a throwaway key (tests/test_release.py)
- [x] T003 [US1] A file changed after signing is named (tests/test_release.py)
- [x] T004 [US2] The inventory refuses a symlink (tests/test_release.py)
- [x] T005 [US3] No runtime module is or imports integrity (tests/test_release.py)
- [x] T006 Run the new tests red

## Phase 2: Implementation

- [x] T007 [US1] [US2] Move the integrity code into scripts/build-release.py
- [x] T008 [US3] Delete cli/wuwei/integrity.py
- [x] T009 [US3] Re-vendor .claude/ with setup.vendor('.')
- [x] T010 Run the new tests green with ssh-keygen, the full suite, and `bin/wuwei agents check`
- [x] T011 Confirm CI has ssh-keygen (tests job on ubuntu-latest)
