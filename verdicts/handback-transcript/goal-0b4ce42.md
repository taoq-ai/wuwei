Verdict: PASS
Gate: goal
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] blocks: no. cli/wuwei/report.py and cli/wuwei/board.py: seat.unconfirmed rows carry a reason in the ledger, but no report or board line surfaces them (board.py only uses them to drop a seat from the running list; report.py counts seat.stopped and verdict.missing only). The owner sees a gate missing in evidence, not why. This is an existing gap, outside this item's promise, so a follow-up item, not a block.
- [low] blocks: no. PR body: seat a93700c1f0c4af7e4's PASS on #1245 stays uncounted until a new hand-back is made after the merge (the PR states this). The restored path is shown on a recorded fixture, not yet on a live post-merge gate; it is unmeasured against the real harness until the next real security gate attests.

## Probes
- Trace: G-1 outcome "every change goes through gates ... attested" (goals.md lines 5-10); item promise "both attestation paths read the report from the seat's own transcript; a report the transcript does not hold records seat.unconfirmed and no attest row"; PR 1250 root cause: hook.transcript_rows used str.splitlines(), which splits on U+2028, so json.loads raised and the whole seat transcript read as None. Diff: read_bytes().splitlines() (LF/CR/CRLF only), key.encode(), AttributeError added to the caught errors. The same diff is in cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py (vendored copy identical at the head).
- Explain-back (spec.md follow-up section) matches the item and the PR: real seat attests once at hand-back, stop alone attests from the transcript, every forged shape attests nothing. No claim beyond the requirement; spec FR-005 adds the row-split rule.
- Fixture is the real failing transcript: tests/fixtures/transcripts/agent-adc67fc6fbcf3d857.jsonl (built by specs/handback-transcript/separator.py from the real seat, redacted). Checked escaped: 2 raw U+2028, 0 U+2029, 0 U+0085, 6 newline-split lines.
- Ran in git archive copies under scratchpad (pytest -q, tests/test_hook.py -k separator): head 5 passed; origin/main hook.py with the same tests and fixtures: 3 failed (row read, real flow [handback], real flow [stop only]), 2 passed (the two forged-beside-separator cases, which attest nothing on both trees). So the new tests are red on main and green at the head. Full suite not run, as instructed.
- Forged side: test_a_forged_report_beside_a_line_separator_attests_nothing (2 cases) passes at the head: no attest or seat.stopped row, seat.unconfirmed reason "does not hold". The new forged-stop case (meta toolUseId not a string) covers the AttributeError path.
- Route differential (specs/handback-transcript/route_diff_separator.txt, read): corpus sha256 de377966... same at both trees, 288 routes, 0 move; 24 hand-back cases, exactly 2 move (separator real at PreToolUse: seat.unconfirmed to attest; at SubagentStop: block to attest), all 10 forged shapes stay seat.unconfirmed. I did not re-run the differential.
- Complement check, other splitlines on harness-written JSON: grep of cli/wuwei shows only hook.py:148 read a transcript this way. ws.py:187 (ledger verify) reads ledger files written with json.dumps default ensure_ascii, so a separator is escaped there. Other splitlines uses read git output, specs or verdict markdown, not JSONL from the harness.
- bytes.splitlines splits only on LF and CR; JSON requires CR and LF escaped inside strings, so a real row never splits (spec failure scenario 3).
- Count check in PR body (the "5 passed"/"3 red" tests list) matches what I ran; the "3617 passed" suite figure and the 3,581-line runtime figure were not re-derived (unmeasured by me).
- Owner visibility: the failure left seat.unconfirmed ("does not hold the report its payload carries") for the hand-back and a block for the stop in the ledger, so a recurrence is recorded with a reason; surfacing is the low finding above.

## Residual risk
Verified on a recorded fixture and the differential, not on a live post-merge gate; a different raw character class or encoding in a real harness row would still read as unreadable, and would show only as seat.unconfirmed in the ledger.
