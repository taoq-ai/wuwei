Verdict: PASS
Gate: quality
Item: 1208
PR: taoq-ai/wuwei#1217
Head: 23a26e5165589a7d4e3b45e454e0cd7bc4be7e43
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] tests/test_hook.py:1182 blocks: no. Mutant: dedup name filter dropped (rglob '*.md' instead of f'{name}--*.md') survives all of tests/test_hook.py; no test shows that two different seats with the same report text both keep it. The shipped code scopes by session, agent and role, so no input is wrong at the head; the missing test is a note.
- [low] cli/wuwei/hook.py:181 blocks: no. The dedup reads each report file while a planner call may move it from pending to its kept path (deliver, os.replace); a read of the vanished file raises FileNotFoundError in subagent_stop. The window is narrow, I did not reproduce it, and the failure path in handle() returns None; a note only.

## Probes
- Head 23a26e5 archived with git archive into a fresh scratch dir; cli/wuwei/hook.py equals .claude/wuwei/cli/wuwei/hook.py and charters/planner.md equals its vendored copy (diff, no output).
- pytest -q tests/test_hook.py at head: 456 passed. The 10 new tests collect and pass (5 modes denied, 3 pass cases: auto, no mode, unknown mode; the FIX-verdict-outside-auto test; the repeated-report test). No skips.
- Mutants (applied to cli/wuwei and .claude/wuwei/cli/wuwei, run one at a time, tests/test_hook.py with the vendored-copy test deselected). 11 of 12 killed by a behavioural test: drop 'bypassPermissions' (test_a_handback_outside_auto_mode_..._once[bypassPermissions]); drop 'default' (same, [default]); add 'auto' to the list (test_a_handback_in_auto_mode_or_an_unknown_mode_passes[auto]); away forced False (..._once[default]); verdict problem text dropped (test_a_gate_whose_verdict_needs_fixing_outside_auto_mode_is_not_sent_back_to_the_handback); always 'Then hand back again.' (..._once[default]); AWAY plus 'Then hand back again.' (..._once[default]); `problem or away` turned `and` (..._once[default]); dedup off, dedup limited to pending, and dedup text check ignored (test_a_seat_that_stops_again_with_the_same_report_keeps_it_once, test_two_stops_of_one_seat_keep_both_reports). Survivor: dedup name filter ignored (see Findings, untested, not equivalent).
- Route corpus: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, unchanged by the diff and holds 0 SubagentHandback routes; the diff changes only hook.py's SubagentHandback branch and SubagentStop, and guards.py is untouched, so 0 routes move by reading; tests/test_guards.py and tests/test_charters.py (which includes the corpus and the charter-to-agents drift test): 2113 passed. Main-versus-head differential run on the corpus: not run as a separate harness, reason: guards.py is unchanged and no route reaches the new branch.
- Parsing probe: not run, this diff changes no guard parsing.
- Runtime budget: hook.py +9/-3 = net 6 lines, within the promise's 6; cli/wuwei totals 3393 lines, under 3,400.
- Doc claim check: planner.md says `wuwei evidence` names each verdict file that did not count and why; evidence.py:365 emits 'not attested: launch the gate as a Claude Code seat ...' for each such file. Supported.
- Acceptance: scenario 1 (five modes denied, no 'hand back again'), scenario 2 (auto, unknown, absent pass unchanged), scenario 3 (three stops, report once, Stop does not block, one file) are each covered by a test that failed under its mutant.
- Simplicity: none to delete. The `away` expression could share its mode tuple with a named constant, but one use does not justify it; AWAY is a single text used once.
- Unmeasured: whether the real harness sends permission_mode in the PreToolUse payload of a subagent; the tests build the payload by hand. If the field is missing, behaviour equals main (the None case passes), which fails safe.

## Residual risk
Depends on the harness naming permission_mode in subagent PreToolUse payloads (unmeasured here); without it the fix does nothing and main's loop returns. The pending-to-kept read race is narrow.
