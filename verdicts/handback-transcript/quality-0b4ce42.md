Verdict: PASS
Gate: quality
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: medium
Supersedes: none

## Findings
- [low] tests/test_hook.py:0 blocks: no. Untested: replacing `key.encode() in line` with `key in line.decode()` survives the whole of tests/test_hook.py (598 tests, one run, plus a fresh-copy rerun of the separator, transcript, forged and stop tests). It differs only for a line holding invalid UTF-8 that does not name the key: head skips that line and returns the other rows, the mutant returns None for the whole file. The mutant is stricter, so no harmful input passes; a test with one junk-byte line beside a matching row would pin the head's behaviour.
- [low] cli/wuwei/hook.py:148 blocks: no. Behaviour change worth a note: a non-UTF-8 byte on a line that does not name the key used to make the whole transcript unreadable (None); it now only matters when that line is parsed. The harness writes valid UTF-8, so this is harmless.

## Probes
- Three new tests on main (head's tests and fixtures copied onto a git archive of origin/main): test_a_transcript_row_holding_a_raw_line_separator_reads_as_one_row FAILED, test_the_real_gate_flow_with_a_line_separator_in_its_transcript_attests_once[handback] FAILED, [stop only] FAILED; 3 failed, 2 passed. The 2 that pass on main are the forged-report guard (test_a_forged_report_beside_a_line_separator_attests_nothing x2), which must refuse on both sides. At head: 5 passed (pytest -k "line_separator or raw_line or tool_use_id_is_no").
- Mutant 1, revert to `real.read_text(encoding='utf-8').splitlines() if key in line`, applied to cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py, tests/test_hook.py run in full: killed by the raw_line_separator test and both attests_once params (the stop-only flow included).
- Mutant 2, drop AttributeError, both trees: killed by 8 or more FORGED_STOPS cases 'a meta file whose tool_use id is no string' (test_a_forged_seat_stop_records_no_stop_no_attestation_and_no_report, every launcher spelling); these were added in this diff.
- Mutant 3, `key in line.decode()`, both trees: SURVIVES, see the first finding. Rerun in a fresh copy: still survives; a probe (invalid-UTF-8 line beside two matching rows) gives the two rows at head and None under the mutant.
- Other readers of harness JSONL in cli/wuwei: all go through hook.transcript_rows (hook.py:22, 165, 169, 286, 328, 507; the meta.json read at 165 is one line). No other reader of ~/.claude/projects exists (grep PROJECTS, transcript_path across cli/wuwei). The remaining splitlines/readlines uses read WUWEI's own text: ws.py:152 and :187 (ledger and traces, written by json.dumps with ensure_ascii on, so U+2028 is always escaped), evidence.py:177, 211, 314 (PR body and patch text), sync.py (git ls-tree names), report.py:17, verdict.py:53. None reads harness JSONL. One note only: ledger rows synced from another clone are WUWEI-written by the same writer.
- bytes.splitlines splits only on \n, \r and \r\n; JSON forbids raw control characters in strings, so no other split inside a row.
- Fixture redaction: grepped the three new fixtures for tokens (ghp_, sk-, github_pat, Bearer, xox), emails, URLs, /home, /root, /tmp paths, org names: none. Paths are /repo, the repo is acme/app, the brief is "Item: I-1\nBuild it.", the Write content and hand-back are short replaced text. Only the sandbox branch name leone/elegant-faraday-zwdbow and session id appear; sentinel-launch.jsonl and agent-a03dc7ca27072549b.jsonl carry the same, so it is not new and not a secret. separator.py redacts with the shared fixtures.redact and writes the character raw (ensure_ascii=False) for the seat file.
- cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py are identical at head; runtime total 3581 lines (limit 3600).
- Confidence reason: the three requested mutants were each run one at a time over the whole of tests/test_hook.py only, not the full suite; mutant 3 survives but I found no harmful input.

Simplicity: none to delete. `key.encode()` per line could be hoisted out of the comprehension, but that is a style point on a one-liner and not worth a change.

## Residual risk
A future edit to the byte-matching line could change the invalid-UTF-8 behaviour unnoticed (mutant 3). Rows holding other raw characters the harness may write are covered only for U+2028 and U+3000 in the fixture.
