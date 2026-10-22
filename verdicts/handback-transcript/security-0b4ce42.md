Verdict: PASS
Gate: security
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:148 blocks: no. json.loads on bytes now accepts a leading UTF-8 BOM (and BOM-led UTF-16/32) on a row, and an undecodable byte on a line without the key no longer voids the whole file. Three planted shapes moved from unconfirmed to attested (a BOM launch row, a BOM report row, invalid UTF-8 on another line). Each needs a raw write into ~/.claude/projects, which the guards refuse, and the control (the same planted launch with no BOM) attests at main and head alike, so they add no capability. A follow-up could decode rows as strict UTF-8 (line.decode('utf-8')) to keep main's byte strictness.
- [low] blocks: no. Probe hygiene, not product code: specs/handback-transcript/route_diff.py (like my earlier attack.py) sits outside tests/, so the autouse `projects` fixture in tests/conftest.py does not apply to it, and it writes into the real /root/.claude/projects/-repo. Stale planted symlinks left there then contaminate later runs. This round's probes redirect ws.PROJECTS themselves. The leftover s0..s109 folders from my earlier round could not be removed: the guard refused rm under .claude/projects, as it should.

## Probes
- Diff read at 0b4ce427 against origin/main 8c38073b: hook.py changes only transcript_rows (bytes splitlines, key.encode() in line, AttributeError caught). The vendored .claude/wuwei copy is byte-identical.
- Separator probe (r2/sep2.py, 110 cases, ws.PROJECTS redirected into scratch), main vs head. Cases: forged rows or launches smuggled on one physical line with CR, CRLF, VT, FF, FS, GS, RS, NEL, LS, PS; the same text written as the harness writes it (inside a JSON string); a lone CR in a string; a non-string or odd meta toolUseId (int, float, true, null, list, dict, lone surrogate, '', NUL); the id present only in another field or on a Bash tool_use; BOM, UTF-16 and invalid UTF-8 rows.
- Separator probe results: every harness-encoded and odd-key case (64 of 64) records seat.unconfirmed at head. Head attests 14 cases and main 40, all planted raw writes or the control. 32 planted smuggles (VT through PS) close at head because one physical line is now one row. 3 planted cases open, which is the low note. CR, CRLF and the control attest at both main and head.
- Lone CR: JSON escapes CR inside a string, and json.loads refuses a raw CR or any control character below 0x20, so a row the harness writes never holds one. A planted lone CR splits the row at both main and head into fragments that fail to parse, so the transcript reads as unreadable.
- key.encode() in line: UTF-8 is self-synchronising, so a byte match equals the old str match on valid UTF-8. The key only filters rows. Structural checks (p.get('id') == use, name Agent/Task) still decide, and an id inside another field stays unconfirmed. A lone-surrogate key raises UnicodeEncodeError, which is caught, so the read is unreadable and fails closed.
- #1244 attack probe re-run (r2/attack2.py, 60 cases, redirected): 0 moved between main and head. Every forged case records seat.unconfirmed. The known residuals are the same at main and head: a hard link needing a refused write, a replayed real stop, and a verdict rewrite after a real FIX.
- Route differential (builder route_diff.py copied with a PROJECTS redirect): corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 is the same at main and head. 0 of 288 routes moved. 2 of 24 hand-back cases moved, both the real security separator seat (Pre: unconfirmed to attest; Stop: block to attest). No forged hand-back attests at head.
- Mutants (each applied to cli/ and the vendored copy, run one at a time, tests/test_hook.py -k separator|forged|launch|unconfirmed|answer):
  - head: 328 passed.
  - m1 (revert to str.splitlines): killed by 3 tests (test_a_transcript_row_holding_a_raw_line_separator_reads_as_one_row and the two attests_once cases).
  - m2 (drop AttributeError): killed by 18 cases of test_a_forged_seat_stop_records_no_stop_no_attestation_and_no_report[a meta file whose tool_use id is no string].
- Supply chain: no dependency, lockfile or workflow change. The ziran audit in CI was not run here (unmeasured). The full suite was not run here; the targeted selection above passed.
- Confidence high: the head reader splits exactly where the harness ends a row. Every input a seat controls through the harness stays unconfirmed. The only widened shapes need a write the guards already refuse.

## Residual risk
A process that can write raw bytes under ~/.claude/projects can still forge, at main and head alike; the guards refusing that write is the boundary. Rows are no longer strict UTF-8 on the first line (BOM) or on lines without the key.
