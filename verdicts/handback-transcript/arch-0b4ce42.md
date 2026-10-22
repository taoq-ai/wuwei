Verdict: PASS
Gate: arch
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: high
Breaking: no (patch: a fix; transcript_rows is internal, no documented API, exit code or ledger shape moves)

## Findings
- [low] tests/test_hook.py:803 blocks: no. The installed() helper still splits the session fixtures with str.splitlines(), against the proposed standards line; harmless today (no session fixture holds a separator, counted by byte scan) but a future session fixture holding U+2028 would be split by the test itself; split on '\n' there too.
- [low] cli/wuwei/hook.py:148 blocks: no. Keyed reads are now more lenient: a line of invalid UTF-8 that does not hold the key no longer makes the whole transcript unreadable (main None, head the matching rows). Only the harness writes these files and a forging writer is already the open SECURITY.md residual, so no new trust gap; worth one line under the spec's How this fails.
- [low] cli/wuwei/hook.py:146 blocks: no. The comment and the proposed standards line say "newlines only", but bytes.splitlines() also splits on CR and CRLF; correct for JSON (a raw CR cannot stand in a string, spec How this fails 3), so the standards line could read "on ASCII line ends only (bytes.splitlines or split on \n), never str.splitlines()".
- [low] blocks: no. The session-transcript path (spec How this fails 2) has no fixture whose session file holds a raw separator; it is covered structurally because every harness JSONL read goes through the one function transcript_rows, and my probe below exercises the function directly.

## Probes
- Conformance: docs/design.md section 8 says a seat stop and report count "only as that seat transcript holds it"; main broke that for any transcript quoting U+2028, U+2029 or U+0085 (read as unreadable, so seat.unconfirmed or a stop block). The fix restores the documented behaviour; no design text needed to change. Spec FR-005 and the follow-up section match the code both ways.
- One reader: grep of cli/wuwei for PROJECTS, transcript_rows, splitlines, jsonl at the head: transcript_rows (hook.py:145) is the only reader of harness JSONL (callers hook.py:22, 165, 169, 286, 328, 507); guards.py:85 only matches a memory path. ws._parse and ws.verify split the WUWEI ledger with str.splitlines, but the ledger is written with json.dumps default ensure_ascii (ws.py:178, 223), so it never holds a raw separator; not harness JSONL.
- Dependencies: no new import; hook.py still reads ws only. No coupling change.
- Vendored copy: diff -q cli/wuwei/hook.py .claude/wuwei/cli/wuwei/hook.py in the worktree: identical.
- Budget: cat cli/wuwei/*.py | wc -l = 3581 at the head and 3581 at origin/main (+0), under 3,600 (AGENTS.md) and the brief's 3,800.
- Differential probe (scratch probe.py, separators built with chr(), run with python3 -I on git archive copies of the merge base and the head): rows holding raw U+2028, U+2029, U+0085: main (False, False) for all three (whole read and keyed read), head (True, True). VT, FF, FS, GS, RS (JSON escapes these): equal at both. CRLF file: equal. int and None key: None at both. Non-ASCII key: equal. Invalid UTF-8 on a non-matching line: main None, head the matching row (finding 2).
- Mutant 1 (revert to read_text().splitlines() and str key, both runtime copies): killed by test_a_transcript_row_holding_a_raw_line_separator_reads_as_one_row and both test_the_real_gate_flow_with_a_line_separator_in_its_transcript_attests_once cases.
- Mutant 2 (drop AttributeError from the except, both copies): killed by 18 cases of test_a_forged_seat_stop_records_no_stop_no_attestation_and_no_report[...a meta file whose tool_use id is no string].
- Focused tests at the head (pytest -q tests/test_hook.py -k "separator or forged_stop or real_gate_flow or transcript"): 140 passed. Full suite not run, per the brief.
- Fixture approach: separator.py rebuilds a real security seat transcript, redacted (brief, Write input, hand-back message, local paths replaced; serverClassifierContext dropped), reading rows split on '\n' and writing the character raw; a byte scan shows agent-adc67fc6fbcf3d857.jsonl holds 2 raw U+2028, no other fixture holds one, no fixture holds a raw CR. route_diff_separator.txt: corpus sha256 de377966..., 288 routes 0 moved; 24 hand-back cases, 2 moved, both the real separator seat moving to an attest row; every forged shape stays seat.unconfirmed.
- PR read once (REST): head 0b4ce42790dc324b0b9d52da0415e279cc37bc3e, draft, open.
- Breaking: transcript_rows is internal; the only outward change is that more real transcripts read as readable, which is what design section 8 already documents. Patch.
- Confidence high: two mutants killed by behavioural tests, the differential shows only the intended moves plus one benign leniency, budget unchanged.

## Residual risk
A future harness JSONL reader added outside transcript_rows could reintroduce str.splitlines(); the proposed standards line is the guard against that. Codex transcripts remain unread, as documented.
