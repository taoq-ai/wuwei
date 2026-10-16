# Tasks: a seat counts as started only when the harness launched it, and once

## Phase 1: Tests first

- [x] T001 [US1] A rejected Agent launch (PreToolUse only) records no seat (tests/test_hook.py)
- [x] T002 [US2] An accepted background launch records its seat with agent 'a1' (tests/test_hook.py)
- [x] T003 [US3] running() counts a1 (three stops and a repeat) and a2 (running) as 1 (tests/test_hook.py)
- [x] T004 The Stop-while-running test launches through PostToolUse (tests/test_hook.py)
- [x] T005 A Codex spawn_agent records its seat at PostToolUse with its agent id (tests/test_codex.py)
- [x] T006 Run the new tests red

## Phase 2: Implementation

- [x] T007 Remove the record from `pre_tool` (cli/wuwei/hook.py)
- [x] T008 Record `seat.started` with `agentId` in `post_tool` (cli/wuwei/hook.py)
- [x] T009 Rewrite `running()` as a set of agent ids (cli/wuwei/hook.py)
- [x] T010 Carry the spawned id in the Codex mapping (cli/wuwei/hook.py)
- [x] T011 Run the full suite green, runtime at 3,000 or fewer

## Phase 3: Checks

- [x] T012 Re-vendor .claude/ with setup.vendor('.')
