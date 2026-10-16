Verdict: FIX
Gate: quality
Item: ledger-parse
PR: taoq-ai/wuwei
Head: 20ee60b966d72331a720c16e2622b13c6fcfa710
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/ws.py:148 blocks: yes. Failure: the guard `isinstance(r.get('hash'), str)` in record has no test. Reversed to `'hash' in r`, the whole suite stays green (294 passed). With a last line `{"hash": null}` (or `{"hash": 5}`) the reversed code writes the new row with prev=None and verify() then names two lines (:2 and :3), so the honest row is falsely flagged; with the guard the new row chains to the last real hash and only the bad line :2 is named. Fix: add `{"hash": null}` and `{"hash": 5}` to the bad lines in test_record_chains_past_a_last_line_that_is_not_a_row (a one-line test change, no code change).
- [low] cli/wuwei/ws.py:123 blocks: no. Note: verify() checks only prev and hash, not field types. A row whose hash is valid but whose ts, kind or data is malformed (a forger who recomputes the hash) is dropped by every reader yet verify() reports clean while it is the last line; it is flagged only at the next honest row (line n+1), never at the forged row. Probed: forged last row, verify [], after next record verify [file:3]. So the builder's claim holds (tampering is detected, at the following row), with the limit that a trailing forged row is silent until another record. Not a regression: the row was kept and unflagged before.
- [low] cli/wuwei/evidence.py:228 blocks: no. Note, a follow-up and not this item: a kept row with the field absent still raises. `{"kind":"attest"}` makes evidence.verdicts raise KeyError 'data' (probed); `{"kind":"andon.raised"}` makes board.andons raise KeyError (probed); report.py:85 `row['kind']` and hook.py:102 `r['ts']` read absent fields the same way. The promise keeps rows with absent fields ("where present"), these KeyErrors exist on main too, and a hand-written dataless row is the only source (ws.record always writes ts, kind and a dict data). Through the hook the one merge-door run I tried (attest and sent dataless rows) still denied, so the fail-open is not shown end to end. Suggest a follow-up item: either require kind and data in _parse for rows with a hash, or read with .get in those readers.

## Probes
- Suite at head in a copy: 294 passed; runtime size 2996 lines (limit 3000, 4 to spare).
- Doors: for each last line in `[1]`, `5`, `null`, `{"a": 1}`, `"s"`, `{"hash": 5}`, `{"hash":"zz","ts":5}`, `{"hash":"zz"}` and each PreToolUse door (Write to the ledger, AskUserQuestion unclassed, Agent launch, create_pull_request) there is no hook.error row and the Write and AskUserQuestion denials hold (32 cases). All doors reach ws.record through hook.pre_tool, so the one fix covers them; only the Write door has a test in the diff.
- Rows ws.record writes: every caller passes a str kind and a dict data (grep of ws.record callers; hook.py:79 kind is from a fixed map), and ts is isoformat, so _parse never drops a row ws.record itself wrote.
- Mutants, each in a scratch copy: drop the isinstance dict check, test_pre_tool_deny_holds_when_the_last_ledger_line_is_not_a_row fails; drop data check, drop ts check, drop kind check, each fails test_readers_skip_rows_with_malformed_fields_and_verify_names_them; record back to mine[-1]['hash'], test_record_chains_past_a_last_line_that_is_not_a_row fails; traces day filter removed, test_traces_skip_lines_that_are_not_rows fails; hash str guard reversed, SURVIVES (the finding above). doctor's removed isinstance filter is covered by test_doctor_finishes_on_ledger_rows_with_malformed_fields.
- Tests fail before the change: the new tests exercise paths that raised on main (mine[-1]['hash'] on `[1]`); I did not re-run them on main.
- Traces: trace rows carry no kind or data keys, so sharing _parse does not drop real traces.
Simplicity: none to delete. The traces rewrite already removes the duplicated parse loop (net fewer lines); the `t()` default in the all(...) check is terse but replaces four isinstance clauses.

## Residual risk
Rows with absent fields still crash readers outside ws (follow-up above); verify() does not type-check fields. Confidence is medium: the hook end to end with a dataless attest row at the merge door was not shown to fail open.
