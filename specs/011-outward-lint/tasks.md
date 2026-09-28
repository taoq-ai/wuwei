# Tasks: Outward-text guard

## Setup

- [X] T001 Read existing contracts and produce spec.md, plan.md and contracts/outward.md in specs/011-outward-lint/.

## US1: Outward lint

- [X] T002 [US1] Write and run failing lint/config tables in tests/test_outward.py; update defaults expectation in tests/test_workspace.py.
- [X] T003 [US1] Implement shared lint in cli/wuwei/outward.py and config defaults in cli/wuwei/workspace.py and templates/workspace/config.toml.

## US2: Owner-sent drafts

- [X] T004 [US2] Write and run failing send/draft and forged-approval tables in tests/test_outward.py.
- [X] T005 [US2] Implement shared send/draft classification in cli/wuwei/outward.py and draft-only refusal in cli/wuwei/guards/outward.py.

## US3: PreToolUse routing

- [X] T006 [US3] Write and run failing tool-routing, alias, bypass, profile and hook tables in tests/test_outward.py; update discovery expectation in tests/test_hooks.py.
- [X] T007 [US3] Complete configured routing and fail-closed extraction in cli/wuwei/guards/outward.py.

## Verification

- [X] T008 Run full pytest, inspect diff and scan all authored files; record results in specs/011-outward-lint/tasks.md.

## Dependencies and strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
Each story uses in-process table tests, with 0/1/2 coverage and adversarial cases.
US1 is independently reusable; the complete issue requires all three stories. Test data
for different stories can be prepared independently, but edits here run sequentially.

## Earlier adversarial review fixes

- [X] T009 [F1] Initial approval implementation, superseded by T015 and T016 below.
- [X] T010 [F2/F3] Test real MCP write names, unknown writes and workspace/native-tool scope red; correct routing and fail-closed defaults.
- [X] T011 [F4/F5/F10] Test all four text-bearing ports red; enforce shared policy at the port and remove dead/textless tool defaults.
- [X] T012 [F6/F7/F9] Test Unicode obfuscation, owner handles, internal-state phrases and character corrections red; update normalization and defaults.
- [X] T013 [F8] Test unknown commit claims red; resolve through the VCS port across configured repositories.
- [X] T014 Run the complete suite with the requested interpreter and inspect the final diff.

## Current review fixes

- [X] T015 [D1/D2] Observe regressions red, delete local approval creation and lookup, expose shared send/draft classifier, and refuse non-mechanical sends with the owner-draft hint. Update spec, plan and contract, including Bash-level send scope.
- [X] T016 [D7] Restore gate_verdicts state test, keep the generic reserved-namespace mechanism with an empty set, and test opt-in reservations.
- [X] T017 [D3] Test ports without workspaces and hooks with invalid explicit overrides red, then make both return 2 without sending.
- [X] T018 [D4] Test uncovered MCP names red, then allow only configured tools or unmatched read prefixes.
- [X] T019 [D5] Test default-family payloads red, support requested metadata and integer issue/pull numbers, and enforce channel_id limits.
- [X] T020 [D6] Test emoji presentation selectors and additional internal-state terms red, then update defaults.
- [X] T021 Run the complete suite with the requested interpreter and inspect the final diff.

## End-to-end review fixes

- [X] T022 [E1] Observe service-prefixed read regressions red; recognize exact read verbs
  with an optional matching service prefix, preserving refusal of writes and unknown tools.
- [X] T023 [E2] Observe event/state and adapter regressions red; require an existing
  .wuwei directory and create only days/ and the day directory. Audit test write paths
  for tmp_path isolation and verify missing-workspace CLI exits are 2 without writes.
- [X] T024 Run the full suite with the requested interpreter and inspect the final diff.

- E1/E2 regressions failed before fixes: 13 failed, 6 passed. A further read-verb/server
  overlap regression also failed before correction.
- Test write-path audit: workspace files and subprocess replay output stay under tmp_path;
  hard-coded external paths in payloads are parsed or handled by fakes, never written.
- Full suite with the requested interpreter: `1192 passed in 13.41s`.
- `git diff --check` passed. Changes remain uncommitted.

## Earlier validation results

- Current correctness regressions were observed failing before their fixes.
- Focused D1/D2 and D7 checks: 239 passed. D3: 7 passed. D4: 36 passed.
- Focused D5 checks: 9 passed. D6: 19 passed.
- The first full run exposed three transport tests relying on the old no-workspace bypass.
  Transport tests now remove only the policy decorator, preserving the result/error wrapper;
  wrapped ports remain covered separately. The focused transport suite passed all 93 tests.
- No commits, pushes or gh commands run.
- Final full-suite result with the requested interpreter: `1172 passed in 12.54s`.
- `git diff --check` and authored-file style/whitespace checks passed.
