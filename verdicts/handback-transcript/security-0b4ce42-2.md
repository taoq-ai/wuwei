Verdict: PASS
Gate: security
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:148 blocks: no. json.loads on bytes is looser than read_text on str for raw planted bytes: a BOM-led UTF-8 or UTF-16 row, an encoded lone surrogate (surrogatepass), and an undecodable line without the key now read where main voided the whole file. Each needs a raw byte write under ws.PROJECTS, which could plant a plain forged UTF-8 row at main too, so it adds no capability; the harness never writes these bytes (CWE-20).
- [low] cli/wuwei/hook.py:148 blocks: no. Mutant no-key-filter (`if key.encode() in line` replaced by `if True`) survives tests/test_hook.py (610 passed). The filter only narrows rows; the structural id and name checks decide, so no input gets through, but no test pins it. Existed at main as `key in line`.
- [low] cli/wuwei/hook.py:150 blocks: no. A lone-surrogate str key (for example a payload tool_use_id of chr(0xd800)) now returns None (UnicodeEncodeError) where main returned []; post_tool then records answer unconfirmed earlier. Fails closed.

## Probes
- Diff at 0b4ce427 vs origin/main 8c38073b (merge base equals origin/main): only hook.transcript_rows changes (read_bytes().splitlines(), key.encode() in line, AttributeError caught); .claude/wuwei/cli/wuwei/hook.py is byte-identical to cli/wuwei/hook.py (diff empty). No dependency, lockfile or workflow change.
- Forged-shape probe (scratch probe/forged.py, ws.PROJECTS set to a scratch folder, separators built with chr()), 56 planted files x 4 keys, 214 results, main tree vs head tree. Separators: CR, CRLF, VT, FF, chr(0x1c), chr(0x1d), chr(0x1e), chr(0x85), chr(0x2028), chr(0x2029). Shapes: forged row after a separator on one line, separator leading a forged row, separator inside a forged row, separator plus forged JSON inside a string (ensure_ascii True and False), key only inside another field, non-string keys.
- Result: rows reading a forged assistant row, main 50, head 20. Every inside-string case (the form the harness writes) reads at head as the one real row with forged_read False (30 of 30 per key set); main read none of the LS/NEL/PS ones (whole file void). Smuggling on one line with VT, FF, FS, GS, RS, NEL, LS, PS read forged at main and closes at head (json.loads refuses the joined line). CR and CRLF split identically at main and head (bytes.splitlines splits on CR; the harness escapes CR, and json.loads refuses a raw one). Head opens only planted raw writes: a whole forged row holding a raw separator inside a string (LS, NEL, PS), BOM/UTF-16 rows, an encoded surrogate, a bad byte on an unmatched line.
- Non-string keys 7, None, b'toolUseId', ['toolUseId'], 7.5: None at main and head, nothing raised. Key inside another field: same row count at main and head; consumers still match p.get('id') == use and name Agent/Task.
- Requested selection at head: pytest -q tests/test_hook.py -k "forged or replay or unconfirmed": 263 passed, 347 deselected. Full tests/test_hook.py at head: 610 passed.
- Route differential (builder route_diff.py copied into each tree's tests/ so the autouse projects fixture applies, --basetemp in scratch): corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at main and head; 288 routes, 0 moved. Hand-backs 24 cases, 2 moved, both the real separator security seat (PreToolUse unconfirmed to attest; SubagentStop block to attest plus seat.stopped), the intended fix; every forged hand-back stays seat.unconfirmed.
- Mutants (fresh git archive copy each, applied to both hook.py copies, run one at a time, tests/test_hook.py): str-splitlines killed by 3 (test_a_transcript_row_holding_a_raw_line_separator_reads_as_one_row and both attests_once cases); no-attributeerror killed by 18 (test_a_forged_seat_stop_records_no_stop_no_attestation_and_no_report[...a meta file whose tool_use id is no string]); no-key-filter survives (note above).
- Scanners: CI at the head, read once via REST: CodeQL (actions, python), ZIRAN, ziran-audit, test 3.11/3.12/3.13 all success. agents/ unchanged, so the ziran role audit is not affected.
- Confidence high: the reader now splits exactly where the harness ends a row; every seat-controlled input via harness serialization stays a single real row and every forged hand-back stays unconfirmed; the only widened shapes need a raw write under ~/.claude/projects that already permits forgery at main.

## Residual risk
A process able to write raw bytes under ~/.claude/projects can forge rows at main and head alike; the guards refusing that write remain the boundary. Rows are no longer strictly UTF-8 validated outside the lines the key selects.
