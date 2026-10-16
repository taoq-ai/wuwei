Verdict: PASS
Gate: quality
Item: plan-accuracy
PR: taoq-ai/wuwei
Head: 43b518df9ce5cbcfc6e151281f35355e0762e8fd
Confidence: medium

## Findings
- [low] blocks: no. Runtime is +8 against the +6 estimate (2,947 lines in cli/wuwei, under the 3,000 cap); the extra two lines are the help text, so it is a process misfit only.
- [low] blocks: no. No test checks that the other commands' exit codes are unchanged after the help refactor; I compared them by hand and they match (plan --help 0, plan bogus 2).

## Probes
- Full suite at the head in a git archive copy: 479 passed, 2 skipped. The 2 skips were not inspected.
- Mutant: removed the approved=False clearing. test_a_changed_promise_or_acceptance_needs_approval_again fails.
- Mutant: made the changed-contract comparison always false. The same test fails.
- Mutant: removed the per-candidate id/title check. Wrong-shape params data3, data4 and data5 fail.
- Mutant: removed the list/dict shape check. All six wrong-shape params fail.
- Mutant: removed the plan run `if not args.reason` refusal. test_plan_run_refuses_without_a_reason fails.
- Mutant: renamed the 'run' key in the actions table. The help test, the run-refusal test and the operations-item test fail.
- Acceptance: all four scenarios are covered. The {"items"} shape exits 2, names the shape and adds nothing. An unchanged promise and acceptance stay approved, a changed promise clears approval, and the board shows "awaiting plan approval". Run without --reason refuses and records nothing, and with --reason the item carries it. Help is checked as one line per action.
- Refactor: the __main__.py diff touches only the plan subparser, the plan add field lookup (now plan.FIELDS, the same keys) and the run branch. The other commands are unchanged. An unchanged re-add keeps approval, and an acceptance-only change clears it (tested).
- Vendored copies: cli/ and .claude/wuwei/cli are identical (diff -r shows only __pycache__).
Simplicity: none to delete. The FIELDS reuse already removed duplicated code, and the check is one expression with one error message.

## Residual risk
Clearing approval compares only non-empty new values, so re-adding with an empty promise keeps the old promise and approval. That matches the existing update semantics.
