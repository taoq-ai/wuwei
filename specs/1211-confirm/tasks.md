# Tasks: an owner answer the transcript shows late, or beside a differing answer in its batch, is still recorded

## Phase 1: Evidence and fixtures

- [x] T001 Read this session's two AskUserQuestion flows and their ledger rows: answer.pending in the same second as each tool_result row, prompt 7 s and 3 s later (spec: What the real data shows)
- [x] T002 Build tests/fixtures/transcripts/ask-late.jsonl and payloads/claude-ask-post-plan.json from the real rows, and the reconstructed payloads/claude-ask-post-free-text.json (specs/1211-confirm/fixtures.py, rows piped in by grep); provenance lines in tests/fixtures/payloads/README.md
- [x] T003 Search for a real free-text answer (none) and a compacted transcript (none); record both under Assumptions and Compaction

## Phase 2: Tests first (1211)

- [x] T004 [US1-US4] Tests for the late row, the differing batch, the bound, the truncated values, a forged first answer, a replayed batch, a payload answer the transcript lacks, and the 7-minute trust flow; the forged-answer class and the Stop-wait test moved to the new contract. Red on base code: 137 failed in tests/test_hook.py (and 3 more for the empty-answer cases, added after)
- [x] T005 [US1-US4] Per-question match in `_shown`, the pending state and `BOUND` in `_confirm`, the narrowed note in `_unconfirmed` (cli/wuwei/hook.py and the vendored copy)
- [x] T006 design.md section 8 and docs/site/concepts/hooks.md

## Phase 3: Tests first (#1231, folded in)

- [x] T014 [US5] Tests for each record shape (toolUseResult missing, a string, a list; text as a string or parts; text that answers otherwise; no text), no tool_use row, the forged-pairs class against the text, a batch read by its text, a Stop that finds a differing answer, and a Stop that finds the answer beside a compact_boundary row. Red on the 1211 code: 47 failed in tests/test_hook.py
- [x] T015 [US5] The tool_use check, the text match anchored by the asked questions, the shape reasons, and the Stop deferral (cli/wuwei/hook.py and the vendored copy)
- [x] T016 Fixture payload replay table (NOTED) and the tests whose ids now read as no tool_use; design.md and the hooks page

## Phase 4: Checks

- [x] T020 Route corpus differential at main and the head with its sha256: 0 of 590 cases moved
- [x] T021 Generated answer probe at main and the head: 1,755 cases, holes main 1,365, head 0
- [x] T022 Mutants of each new condition in both copies, one at a time (mutants.py)
- [x] T023 Full suite; runtime at 3,406, over the cap until free-lines-6 merges (stated in the spec)
