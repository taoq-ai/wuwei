Verdict: PASS
Gate: quality
Item: ledger-parse
PR: taoq-ai/wuwei
Head: b92ea1e98d4691a73d5333146afb0a6bfefd461c
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/ws.py:148 blocks: no. Closed. My previous blocking finding (hash string guard untested) is resolved: `{"hash": null}` and `{"hash": 5}` are in the chaining test, which now also asserts verify() names exactly the bad lines. With the guard reversed to `'hash' in r`, that test fails.
- [low] cli/wuwei/ws.py:123 blocks: no. Note, unchanged from the previous round: verify() checks only prev and hash, so a validly hashed row with a malformed field and no later record is not named until the next row.
- [low] cli/wuwei/evidence.py:228 blocks: no. Note, unchanged and a follow-up: kept rows with an absent data, kind or ts still raise KeyError in evidence.verdicts, board.andons, report.py:85 and hook.py:102. Present on main.

## Probes
- `git diff 20ee60b b92ea1e -- cli` is empty (0 lines); the delta is tests only (tests/test_hook.py, tests/test_ledger.py).
- Suite at head in a copy: 295 passed; runtime size 2996 lines.
- Mutant, hash guard reversed to `'hash' in r`: tests/test_ledger.py::test_record_chains_past_a_last_line_that_is_not_a_row fails (it survived at the previous head).
- Base ws.py (5d7157b) with the new tests: both parametrized cases of test_pre_tool_deny_holds_when_the_last_ledger_line_is_not_a_row (Write, AskUserQuestion) fail, so the AskUserQuestion door is now covered and shown to fail before the fix.
- Mutant, dict check dropped: the hook test (both cases), the chaining test, test_traces_skip_lines_that_are_not_rows and the doctor test fail.
- Earlier mutants on data, ts, kind and the traces day filter are unaffected by this tests-only delta.
Simplicity: none to delete; the delta only adds test inputs and one parametrization.

## Residual risk
Dataless kept rows still crash readers outside ws (follow-up); verify() does not type-check fields. Not shown end to end through the merge door.
