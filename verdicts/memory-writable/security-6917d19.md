Verdict: ESCALATE
Gate: security
Item: memory-writable
PR: taoq-ai/wuwei#1197
Head: 6917d199c1a47b21b8ee5c7b7ae71508d33ff1a0
Confidence: low

## Findings
- [high] cli/wuwei/guards.py:80 blocks: yes. Failure: the new memory exception in harness() narrows the transcript guard that #1172's owner-answer and seat-stop confirmation rests on (trust boundary, CWE-284 class), and this seat's review of it was stopped by a safety classifier before any probe ran, so a write that reaches a transcript through the exception is unmeasured, not ruled out; the owner decides who reviews this trust path (another security seat, a person, or the sandbox item).

## Probes
Read: wuwei plan show memory-writable (tier full, four acceptance scenarios), gh pr view 1197 once, git diff 59f153f6..6917d199 (9 runtime lines in each guards.py copy, 8 new routes.json rows, SECURITY.md and doors.md text).
CI as read once: CodeQL actions and python, test (3.11), test (3.13), ziran-audit, ZIRAN SUCCESS; test (3.12) IN_PROGRESS, so CI green is not confirmed.
Not run: route corpus differential at main and head with sha256, specs/memory-writable/probe.py and its three counts, added probe classes, normalisation round per path class and wrapper, checks without door words, mutants, pytest. All unmeasured.
Confidence low: only the diff and the check list were read; no behaviour of the change was measured.

## Residual risk
The whole security surface of the memory exception is unreviewed by this gate. The builder's own probe and mutant counts in the PR body are claims this gate did not reproduce.
