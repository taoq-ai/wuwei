# Tasks: handback-transcript

## Phase 1: Tests first

- [x] T001 Worktree from origin/main b9522fc7 on `leone/handback-transcript`; hook-transcript (#1172) is on main; runtime 3,448
- [x] T002 `fixtures.py`: the sentinel fixtures from a real session (a sentinel-arch seat that ended with SubagentHandback): `sentinel-launch.jsonl`, `agent-a03dc7ca27072549b.jsonl` and its meta file; the two payloads and their provenance lines; a reconstructed seat transcript for the builder fixture
- [x] T003 [US1] tests/test_hook.py: a forged hand-back with no launch (acceptance 1, with evidence still owing the gate), a launched gate whose transcript holds another report, no hand-back, or is a link out of the folder; a replayed real stop with a forged report, direct and behind a link; the real sentinel flow with a forged report in either payload field
- [x] T004 [US2] the real sentinel flow (acceptance 2) and the fixture replay table with an `attest` column
- [x] T005 Red at b9522fc7's runtime: 8 failed, 263 passed (the real flow tests pass at main, as acceptance 2 asks)

## Phase 2: Implementation

- [x] T006 `transcript` reads through `transcript_rows` and returns every report it saw
- [x] T007 `_report`: the launch check moved out of `subagent_stop`, the seat transcript beside the session's when the payload names none, the reread, `seat.unconfirmed` with its reason; `_settled` goes
- [x] T008 `pre_tool` and `subagent_stop` take the report from `_report`
- [x] T009 tests/conftest.py `launched` hard-links a named seat transcript and writes the payload's message when none is named; two tests updated to the new contract (a stop's message is one its transcript holds; a Codex-shaped stop names no transcript)
- [x] T010 Both runtime copies; runtime 3,455 (+7 against a budget of +16)
- [x] T011 SECURITY.md, docs/design.md section 8 and section 12 (the item leaves Deferred)

## Phase 3: Proof

- [x] T012 Green: the focused tests, then the full suite
- [x] T013 VAL: empty, cut, non-object, blank-line and repeated seat transcripts; a stop with no report text (`''`, whitespace, None, a number)
- [x] T014 `route_diff.py` and `compare.py`: corpus sha256 de377966... at both trees, 288 routes through guards.bash and PreToolUse as planner and as seat, 0 moved; 12 hand-back cases, 7 moved, each from an attest row (or a deny) to `seat.unconfirmed` (`route_diff.txt`)
- [x] T015 11 mutants, both runtime copies, one at a time: 9 killed by behavioural tests, M5 equivalent, M11 survives with its reason (`mutants.txt`)

## Phase 4: Follow-up, a raw line separator (branch leone/handback-timing)

- [x] T016 Red: fixtures from the real security seat adc67fc6fbcf3d857 (`separator.py`); the row read, the hand-back and the stop-only flows fail on main
- [x] T017 `transcript_rows` splits on newlines only; a key that is no string reads as no transcript (a new forged-stop case)
- [x] T018 `route_diff.py` adds the separator seat: corpus sha256 de377966... at both trees, 288 routes, 0 moved; 24 hand-back cases, 2 moved, both the real separator seat from unconfirmed or blocked to attested (`route_diff_separator.txt`)
- [x] T019 Green: the focused tests, then the full suite
