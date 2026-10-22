Verdict: PASS
Gate: quality
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: medium

## Findings
- [low] tests/test_hook.py:837 blocks: no. The separator fixture holds only U+2028 (2 raw occurrences); U+2029 and U+0085 are not in a fixture. bytes.splitlines() splits on \n, \r and \r\n only, so the fix covers them by construction; the gap is an untested class, not a defect.
- [low] tests/test_hook.py:1783 blocks: no. The new forged case 'a meta file whose tool_use id is no string' passes on main too (TypeError was already caught there); it guards the new bytes path (key.encode()) and is killed by the AttributeError mutant, so it is a regression guard, not a failed-before test.

## Probes
- Fail before / pass after: git archive of origin/main with the head's tests/test_hook.py and tests/fixtures/transcripts/* copied over (cp, never printed): `pytest -q -k separator` gives 3 failed, 2 passed (the failing: test_a_transcript_row_holding_a_raw_line_separator_reads_as_one_row, test_the_real_gate_flow_with_a_line_separator_in_its_transcript_attests_once[handback] and [stop only]); the 2 forged-report cases pass on main by design (fail closed either way). Git archive of head: 5 passed.
- Fixture check (counts only, no content printed): agent-adc67fc6fbcf3d857.jsonl holds 2 raw U+2028 in 5 rows; sentinel-separator-launch.jsonl holds none.
- Mutant 1 (revert to read_text(...).splitlines() and `key in line`), applied to cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py: killed by the same 3 behavioural tests.
- Mutant 2 (drop AttributeError from the except tuple), both copies: killed by test_a_forged_seat_stop_records_no_stop_no_attestation_and_no_report[... a meta file whose tool_use id is no string] (hook error: 'int' object has no attribute 'encode').
- Other readers of harness JSONL: grep splitlines/readlines in cli/wuwei: only sync.py (git ls-tree output), report.py, gh.py, evidence.py, verdict.py (WUWEI-written text/markdown) and ws.py:152,187 (WUWEI's own ledger, not harness rows). Every harness transcript/meta read in hook.py goes through transcript_rows (lines 22, 165, 169, 286, 328, 507). Other read_bytes calls in hook.py read verdict/report files, not rows.
- Full suite at head archive: 3617 passed, 2 skipped (includes the vendored-plugin match test; the two hook.py copies are identical). Runtime lines 3581 of the 3600 cap.
- Confidence reason: both mutants killed, fail-before shown, readers audited; medium because U+2029/U+0085 are untested and only 19 lines of runtime budget remain.
- Simplicity: none to delete; the change is one expression and one except entry. The encode() of key per call is needed for the byte-wise filter.

## Residual risk
A harness row that holds a lone \r raw would still split (cannot occur in valid JSON strings, so such a row is invalid anyway). Runtime line budget is 19 lines from the cap.
