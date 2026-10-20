# Tasks: an owner answer and a seat stop are recorded only when the session transcript shows them

## Phase 1: Evidence and fixtures

- [x] T001 Read the real flow's timing in this session's transcript: the answer row is stamped 11 ms after the PostToolUse hook returned (spec: What the real flow showed)
- [x] T002 Build tests/fixtures/transcripts from the real rows, redacted (specs/hook-transcript/fixtures.py), and the payloads claude-ask-post.json and claude-seat-stop.json with their provenance lines
- [x] T003 conftest: every test gets its own projects folder; `answered()` and `launched()` write the rows a real flow has

## Phase 2: Tests first

- [x] T004 [US2] The real flow in the measured order records the ruling on the planner's next call, once (tests/test_hook.py)
- [x] T005 [US1] The forge class: 18 forge-door shapes x 7 transcript cases as hook.handle payloads record no ruling and an answer.unconfirmed row naming why (tests/test_hook.py)
- [x] T006 [US4] The forge class: 18 shapes x 5 seat-stop cases record no seat.stopped, attestation or report (tests/test_hook.py)
- [x] T007 [US3] Writes under the projects folder refused in 16 spellings x 15 writers, 8 working-directory forms, a session inside it and 6 edit forms; 12 reads and 3 edits beside it pass (tests/test_guards.py)
- [x] T008 Run red: 223 failed in test_hook.py and 255 in test_guards.py at base code
- [x] T009 Update the tests of the old contract: the owner-answer and seat-stop tests in test_hook, test_breaking, test_plan, test_report, test_view and test_models write a transcript; the Codex tests assert unconfirmed rows

## Phase 3: Implementation

- [x] T010 `ws.PROJECTS` from the password database (cli/wuwei/ws.py)
- [x] T011 `transcript_rows`, `parts`, the kept answer at PostToolUse, `_shown`, `_unconfirmed`, `_confirm` and its call from `deliver` (cli/wuwei/hook.py)
- [x] T012 The seat launch check in `subagent_stop`; `running` subtracts `seat.unconfirmed` (cli/wuwei/hook.py)
- [x] T013 `records(..., name)`, `harness()`, the Bash and edit refusals, `HARNESS` (cli/wuwei/guards.py)
- [x] T014 Route corpus rows (4 refusals, 2 passes); re-vendor `.claude/wuwei/cli`
- [x] T015 design.md sections 7, 8 and 12, SECURITY.md, docs/site concepts (hooks, doors, codex)

## Phase 4: Checks

- [x] T016 Route corpus differential at main and the head with its sha256, and the checks without door words
- [x] T017 Write probe under real bash at main and the head; its hole class (find after a wrapper) closed by `find` in READ, with a test (T018)
- [x] T018 [US3] find -delete or -exec after five wrappers refused for the transcripts, the ledger and the cache (tests/test_guards.py)
- [x] T019 Real-entry probe: every forge shape run under bash against the hook entry at main and the head; the entry reads no projects folder its caller names (tests/test_hook.py, HOME and CLAUDE_CONFIG_DIR)
- [x] T020 Mutants of each new condition, both copies, one at a time, wall-clock tests deselected (mutants.py), with tests added for the last answer row, the tool name and a row written within the wait
- [x] T021 Full suite green; runtime under the 3,400 cap
- [x] T022 Tests that kill the survivors: a FIFO under the projects folder (H3), a row written from inside the Stop's wait (H11), the agent-id case with the real type (H14)
- [x] T023 Merge origin/main f63c804 and dc9aad9 (merge commits); differential and full suite at the merged head

## Phase 5: Fix round 1 (the four gates at 018548a)

- [x] T024 Merge origin/main d4a803f (merge commit)
- [x] T025 Pending answers are confirmed before the handler on PreToolUse and Stop, after it on PostToolUse, inside handle's try; a merge as the next call passes with the ruling (tests/test_hook.py)
- [x] T026 PostToolUse records `answer.pending`; an error while recording is a hook.error after it; a refused call carries the notes (tests/test_hook.py)
- [x] T027 ws.PROJECTS falls back to `/dev/null/.claude/projects` when the uid has no passwd entry; the real entry still refuses a ledger write (tests/test_hook.py)
- [x] T028 The Stop-wait test replaces hook.time with a namespace; the wall-clock test keeps only its lower bound; H11 run 10 times
- [x] T029 A traversal tool_use_id lands nothing outside .wuwei/cache (X1); a replayed answer records once (prompt rows carry the id)
- [x] T030 Docs: the two attestation paths that still read payload text, the quoting and eval holes, the pending row; codex.md names the break
