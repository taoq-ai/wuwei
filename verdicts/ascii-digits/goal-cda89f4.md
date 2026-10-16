Verdict: PASS
Gate: goal
Item: ascii-digits
PR: taoq-ai/wuwei#1107
Head: cda89f41f7dae59165e7dddac94ba50e2a6a6be9
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:245 blocks: no. The merged ruling reader reads the class prefix (strip, lower case) instead of main's case-sensitive substring: on head 'Owner review: o/r#7 at abc1234' and ' Breaking: ...' now record, 'Please answer. owner review: o/r#7 at abc1234?' no longer records. Spec Assumptions and How this fails 1 record this, and charters/_common.md Decisions 2 tells every seat to start the question with its class. The spec's claim that the guard refuses a question with text before the class is loose: guards.pre_tool only checks questions that start with a class, so such a question would pass the guard and record nothing.
- [low] cli/wuwei/hook.py:273 blocks: no. REF ends in \b, so 'owner review: o/r#7 at abc1234x?' recorded head abc1234 on main and records nothing on head. The spec does not mention this. It is a stricter read of a malformed sha.
- [low] blocks: no. The spec's Clarifications give line numbers at 0104d00 and the plan's at fe5bc0b; neither is head, and both are informational.

## Probes
Trees: git archive of 23625f3 (main) and cda89f4 (head), each into its own folder under scratchpad/goal-ascii-digits.
Builder probe p.py, run by me on both trees: main gives refs ['o/r#７'], verdict errors [] with pr 7, evidence calls gh api repos/o/r/pulls/7, ruling ('o/r#７','abc1234'). Head gives refs [], the PR line error, exit 'wuwei: name the PR as owner/repo#number' with gh calls [], no ruling. o/r#7 records ('o/r#7','abc1234') on both trees (acceptance rows 1 to 4).
Head suite (pytest -q): 964 passed, 2 skipped. Main suite: 952 passed, 2 skipped.
Head's test_hook/test_evidence/test_verdict/test_setup copied onto main: 7 failed, all of them new cases (the ruling rows for ７ and ٧, refs, evidence ７ and ٧, the verdict PR ７ row, the scan). Each acceptance row has a test that is red on main and green on head.
Row 5: grep '\\d|isdigit|isdecimal|isnumeric' cli/wuwei/*.py on head finds only three isdigit calls, each after isascii() (__main__:19, guards:161, guards:360). Runtime lines (cat cli/wuwei/*.py | wc -l): main 2992, head 2988.
Outside the promise: in git diff 23625f3 cda89f4 -- cli, no message string changes and every [\w.-] repository class is kept. re.A sits only on VERSION_LINE, where it already was on main. diff -r cli/wuwei .claude/wuwei/cli/wuwei shows the mirror matches.
Ruling edge cases (scratch q.py, both trees): canonical owner review and breaking forms give the same fields as main, and owner review still carries no kind key. Differences only for the forms named in the findings.
Spec: spec.md restates the promise, the 5 acceptance rows, Outside and Rollback in line with plan.json, and names the test for each US. FR-001 to FR-005 match the diff.
Confidence is high because every row was run on both trees and the populations were counted by grep.

## Residual risk
Other int() readers that do not use a pattern (plan.owe within, the __main__ score floats) are outside the promise and still accept Unicode digits. None of them reads a PR number.
