Verdict: PASS
Gate: goal
Item: session-context-cap
PR: taoq-ai/wuwei#1149
Head: 3fab3cb650f206a9bf7834fd2dcb83cb8722778d
Confidence: medium

## Findings
- [low] blocks: no. The measure table in the PR body is path dependent, as the body says. Read at the head under a longer scratch path the rows are empty 5,332 (body 5,298), 40 items 9,949 (9,915), 200 items 9,950 (9,916), main empty 16,098 (16,092). The items shown and left out (28 and 12, 28 and 172) match exactly. Under a short path (/tmp/g/h) 40 items gave 9,840 with 30 shown and 10 left out. The cap holds in every run, so this is a note only.
- [low] blocks: no. The goals and standards are no longer inlined. The promise names the charters and the board but not goals and standards. The PR body and spec A1 record this as an assumption, and skills/wuwei-run/SKILL.md line 13 (step 2) reads both files. The drift is disclosed and goes the safe way.
- [low] blocks: no. The 10,000 cap is the harness's, from docs read 2026-10-18, and no live SessionStart was observed. The promise's own assumption holds until a live run overturns it.
- [low] blocks: no. Residual risks the body states are real, from reading the code. Trimming stops at a last line that does not start with "- ". Then the final cut at 10,000 holds the cap but can drop the left-out count (tested for the cap with 30 andon lines). Items drop from the end of the board, so across repositories the last repository's items go first. The message reads "1 more items left out" for a count of 1.

## Probes
- Promise to code. hook.session_start at the head: WUWEI CLI line first, _way.md in full, the Decisions and Done sections of _common.md, and a line giving the absolute path of planner.md and _common.md and the .wuwei folder. The board follows, trimmed from its last "- " lines, with "<n> more items left out; `wuwei status` lists them all.", and a final [:10000] cut. This matches the promise (cut charters, pointer naming the charter files, board kept, fitness test).
- Acceptance 1, empty workspace: measure.py at the head gave 5,332 characters (at most 10,000). The test asserts the CLI path and the planner.md path are in the text. Pass.
- Acceptance 2, 40 items: 9,949 characters, 28 shown, 12 left out, and the left-out line is in the text. With 3,000-character goals and standards the figure is the same, and with 200 items 9,950 with 172 left out. Pass.
- Body counts from live output at the head (git archive copy, pytest at /root/.local/bin/pytest). Suite 1780 passed, 2 skipped (matches). Runtime lines `cat cli/wuwei/*.py | wc -l`: 2,995 at the head and 2,992 at main, so +3, within budget 6 (matches). Red run, head's tests/test_charters.py on a main copy with -k session_start: 3 failed (16,101, 28,647 and 29,171 characters, which are the body's figures plus the path offset). Green at the head: 3 passed (matches). Mutants.py at 3fab3cb: 8 mutants, 8 killed, 0 holes (matches). hook.py is identical from cf75707 to 3fab3cb (git diff cf75707 3fab3cb touches only plan.md), so the body's cf75707 figures cover the head.
- Route differential (route_diff.py main b28a3dc against head, corpus sha256 12725ace... on both): 251 routes, 511 cases. guards 251 cases and bash 251 cases, 0 moved; payload 7 cases, 0 moved; session 2 cases, 2 moved (15,987 to 4,877 and 20,456 to 9,346), all as the body says. No guard parsing changed, so no combinatorial probe applies.
- Vendored copy .claude/wuwei/cli/wuwei/hook.py is identical to cli/wuwei/hook.py at the head (diff).
- Docs (design.md, hooks.md, getting-started.md) now describe the new session start; no claim beyond what the code does. No other charter or skill text assumes the planner charter is inlined (grep).
- CI at the head via REST check-runs: CodeQL, ZIRAN, Analyze (actions), Analyze (python), test 3.11/3.12/3.13 and ziran-audit all completed with success. The combined status endpoint lists no statuses (state "pending"); I read it once and did not poll.
- Confidence is medium. Every count reproduced from live output, but I did not run the plan against a live Claude Code SessionStart.

## Residual risk
A planner that ignores the pointer line misses planner.md's rules (disclosed). The harness cap is taken from documentation, not observed live.
