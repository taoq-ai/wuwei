Verdict: PASS
Gate: goal
Item: breaking-proceed
PR: taoq-ai/wuwei
Head: ddbe122cc7d0209daf2931abdfd4810b8652bc66
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:243 blocks: no. Builder's residual risk holds but is inside the promise ("The rule is shared by every class, as today"): a plan: answer starting "Proceed with these changes" now runs plan.approve and approves every open item instead of recording plan.change. The planner charter offers only Approve or Change, so this needs free text, and "Yes, but change X" already approves today. The answer is kept in the plan.approved row. A per-class yes rule, or a plan: test that looks for "change", would be a separate item.
- [low] tests/test_breaking.py:89 blocks: no. Spacing: three blank lines before the new test and one after it (pycodestyle E303/E302). Cosmetic only.

## Probes
- Replay of today's failure: took the real ledger ruling row (taoq-ai/wuwei#1077 at ea1833f, answer "Proceed", approved false) from .wuwei/ledger/*.jsonl with grep. Sent the same question and answer as a PostToolUse AskUserQuestion payload through hook.handle, in a new scratch workspace (scratchpad/goal-breaking-proceed/replay.py). Head tree: ruling kind breaking, approved true. origin/main tree: approved false, which reproduces the bug.
- In the same scratch workspace, evidence.breaking_gaps for a declared breaking PR with an Announcement line at head ea1833f... returns [] on head, so the confirmation gap clears. On main it returns the "needs the owner's confirmation" gap. At a different head (bbbbbbb) the gap still shows on head, so the confirmation stays bound to its head.
- Acceptance 1 and 2 traced to tests/test_breaking.py test_a_proceed_answer_to_the_breaking_question_approves (Proceed, proceed. -> true; Do not proceed, No -> false). Acceptance 3: the full suite at head passes (466 passed, /root/.local/bin/pytest -q tests), and wc -l cli/wuwei/*.py gives 2999 total, under 3,000.
- Mutant: removed 'proceed' from the yes tuple in a copy of the tree. The two true cases of the new test fail. Killed.
- Vendored parity: diff cli/wuwei/hook.py .claude/wuwei/cli/wuwei/hook.py shows they are identical. grep finds no other yes test in cli/wuwei/*.py, so the fix covers the only decision point.
- Explain-back (specs/breaking-proceed/spec.md) matches the plan's promise and acceptance: one shared tuple, no "ok"/"go", no template rewording. No drift either way. Goal G-2 fits (a bug found running WUWEI on itself).
- Confidence high: the real failing input was replayed end to end through hook and evidence on both trees.

## Residual risk
"proceed" is a prefix rule shared by every class, so free-text answers starting with "proceed" to plan:, exception: or owner review: questions now count as yes. This is the accepted scope of the promise; the answer text is always recorded.
