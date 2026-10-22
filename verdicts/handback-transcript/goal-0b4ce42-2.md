Verdict: PASS
Gate: goal
Item: handback-transcript
PR: taoq-ai/wuwei#1250
Head: 0b4ce42790dc324b0b9d52da0415e279cc37bc3e
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/verdict.py:53 blocks: no. A raw U+2028 inside a single Findings line of a verdict file still splits that line (str.splitlines), so a finding quoting the separator would fail the finding-shape check; outside this PR's failure (the real separator sat in the Probes prose) and outside the item's promise, so a note for a later item.
- [low] blocks: no. Unmeasured: no live gate was run through the real harness at this head; the evidence is the recorded real transcript fixture plus replayed hooks, so the first real security gate after merge is the confirming run.

## Probes
- Trace: promise "a real gate's report attests from its own transcript; a forged one never does" (wuwei plan show handback-transcript). Failure seen: transcript_rows used str.splitlines(), which splits on U+2028, so the whole seat transcript read as unreadable, the hand-back recorded seat.unconfirmed and the real PASS went uncounted. Diff at the head (git diff origin/main...0b4ce427 -- cli/wuwei): transcript_rows reads bytes and uses bytes.splitlines() (splits only on LF, CR, CRLF), filters on key.encode(), and AttributeError is caught so a non-string key reads as no transcript. The vendored copy carries the same 6-line change. Forged-payload guards (resolve under ws.PROJECTS, regular file, launch confirmation, report must be in the transcript) are untouched.
- Fixture is the real failing transcript: tests/fixtures/transcripts/agent-adc67fc6fbcf3d857.jsonl (read only through python ascii() and od, never raw): 6806 bytes, 5 rows, 2 raw U+2028 and 0 U+2029 or U+0085, both inside the Write tool_use content for the seat's own verdict file (its tool_use and its tool-input echo), real message and tool ids, agentType sentinel-security, meta toolUseId matches the launch row in sentinel-separator-launch.jsonl. Only the item, path and head are anonymised (I-1, aaaaaaa).
- pytest -q tests/test_hook.py -k separator in a git archive of the head (scratch folder goal-hb): 5 passed, 605 deselected. Full tests/test_hook.py: 610 passed (118s). These cover: real handback attests once, real stop alone attests, a forged last_assistant_message and a forged tool_input beside the separator transcript attest nothing and record seat.unconfirmed with 'does not hold', and a row with the separator reads as one row equal to the JSON-parsed row.
- Route differential (specs/handback-transcript/route_diff_separator.txt, read with cat -v): 288 guard routes, 0 moved, corpus sha256 de377966...; handback cases 24, exactly 2 moved: PreToolUse (and, by the same listing, the stop) of 'security separator real' went from seat.unconfirmed to attest. Every forged or off-path separator case is unchanged at seat.unconfirmed. This is the intended move only.
- Other splitlines in cli/wuwei: ws.py ledger reads are safe (rows are written with json.dumps, ensure_ascii default, so no raw separator); evidence.py and report.py read PR/checklist text, not seat transcripts. A verdict file with the separator in Probes parses clean (own probe, chr(0x2028)); only a separator inside a Findings line fails (finding above, a note).
- Explain-back check: spec.md FR-005 and the follow-up section state the same promise (real seat's hand-back attests once, a stop alone attests, forged shapes still attest nothing); no claim beyond it, no required outcome missing. analysis.md R3 matches.
- Mutant check: reverting bytes.splitlines to str.splitlines is exactly the pre-fix code and the separator tests fail on main per the route differential (main: seat.unconfirmed); not re-run as a separate mutant.

## Residual risk
The fix restores the promise for the failure seen, shown on the recorded real transcript, but a live harness run at this head is unmeasured. A verdict whose Findings line holds a raw separator would still be uncounted.
