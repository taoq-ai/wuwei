# Tasks: a gate's verdict is linted before its hand-back

## Phase 1: Tests first

- [x] T001 [US1] A malformed verdict denies the hand-back with the bad line and the format (tests/test_hook.py)
- [x] T002 [US2] A well-formed verdict is attested at the hand-back and once after SubagentStop (tests/test_hook.py)
- [x] T003 [US2] A builder, another gate's seat and an unknown seat attest nothing; only sentinels are linted (tests/test_hook.py)
- [x] T004 [US3] A problem after a hand-back ended the run records verdict.missing (tests/test_hook.py)
- [x] T005 [US4] A note without a place parses; a blocking finding without one is rejected (tests/test_verdict.py)
- [x] T006 Remove the post_tool hand-back test the change retires (tests/test_hook.py)
- [x] T007 Run the new tests red

## Phase 2: Implementation

- [x] T008 `transcript` reports a run ended by hand-back (cli/wuwei/hook.py)
- [x] T009 The hand-back check in `pre_tool` (cli/wuwei/hook.py)
- [x] T010 `verdict.missing` on an ended run in `subagent_stop` (cli/wuwei/hook.py)
- [x] T011 Remove the post_tool re-read (cli/wuwei/hook.py)
- [x] T012 FINDING, the blocking check and FORMAT (cli/wuwei/verdict.py)
- [x] T013 Run the full suite green, runtime at 3,000 or fewer

## Phase 3: Docs and checks

- [x] T014 charters/_gate.md, then `bin/wuwei agents build`
- [x] T015 docs/design.md hook table names the hand-back lint and verdict.missing
- [x] T016 Mutants of each new condition, run in a scratch copy, each fail a test
- [x] T017 Re-vendor .claude/ with setup.vendor('.')
