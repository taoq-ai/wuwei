Verdict: PASS
Gate: goal
Item: 1223
PR: taoq-ai/wuwei#1228
Head: b6d06355cfedbb71a97acb2961e27092c95c00f5
Confidence: medium
Breaking: no
Supersedes: none

## Findings
- [low] blocks: no. A printed finding row cut at 100 characters with a sentence break after its last `|` is still recorded short and the yes waives nothing (fails closed, 6 of 252 probe cases, class `long row cut`, full tier). The PR body and spec.md state it and name the candidate fix in `evidence._rule`, outside this item.
- [low] blocks: no. The PR body counts (252 questions, 198 reached the owner, 54 sent back, 6 holes) match my re-run. Its main-side counts (18 / 234 / 180) I did not re-run.

## Probes
- Trace: #1223 acceptance (a full-tier spec-only PR, gates passed and an approval: exactly one of merge or exception succeeds) -> plan 1223 promise and 4 scenarios -> spec.md "promise in my words" (matches the plan; it keeps the out-of-scope line on reading unchecked tasks as expected) -> guards.py AskUserQuestion branch now sends back only `template's sections|changed lines|open N days`; hook.py `exception_refs` reads the gap up to the first `. ` or `?` after the last `|`.
- Scenario 1 and 2, end to end at the head (test_an_accepted_spec_gap_opens_the_merge_door_and_is_recorded, run in a `git archive` copy of the head): a full-tier spec-only PR with 17 unchecked tasks. The merge door holds with `tasks.md has 17 unchecked items`. The question passes the guard. A transcript-confirmed Yes records the ruling (kind exception, head aaaaaaa, approved) and the follow-up item `X-...: Close the exception on acme/app#42: ...`. The door then returns None. So the exception path succeeds; before the Yes the merge is refused. The issue's "exactly one of the two" holds: it takes the issue's option 1, the one `_common.md` Done states.
- Scenario 3 (test_an_accepted_finding_row_waives_only_the_whole_row and test_an_exception_gap_keeps_the_sentence_breaks_of_a_finding_row): the whole row `| A08 | HIGH | Spec says X. Plan says Y |` opens the door; the first sentence alone does not.
- Scenario 4 (test_an_exception_for_a_process_gap_goes_back_to_the_model, 3 kinds): template, size and age are still denied with "never block".
- Focused run `pytest -q tests/test_hook.py tests/test_guards.py -k "sentence_breaks or spec_gap or process_gap or finding_row or accepted_spec_gap"` in my copy: 21 passed (matches the body's 21).
- Question probe (specs/spec-gap-exception/question_probe.py, `PROBE_OUT=... pytest -q`, copy of the head): 252 passed, 252 rows written. Read from the output file: 198 owner, 54 sent back, 246 ok, 6 HOLE. All 6 holes are `long row cut` at full tier across the 6 tails, each fails closed (the Yes waives nothing). This equals the PR body's 252 / 198 / 54 / 6. Gap texts come from `evidence.gaps`, not typed. Below full tier, spec kinds are not shown to the planner, as the assumption says.
- G-2: the change removes a deadlock where the owner could not accept a gap that the merge door holds as safety, and the merge door and question door now agree with `_common.md` Done. It reads the goal's intent (the gate rule and what the owner decides agree), and it widens nothing else: process fit kinds stay denied, `evidence.py` is untouched, so which gaps are safety is unchanged.
- Drift, missing: none found. The issue's separate suggestion (spec-only PR reading unchecked tasks as expected) is out of scope by the plan and the spec says so. The PR body does not claim it. The PR body "Fixes #1223" is accurate for option 1 and the acceptance sentence; the "expected tasks" line is not addressed, but that is stated in spec.md and out of scope.
- Drift, extra: docs/design.md (3 lines) and docs/site/concepts/decisions.md (3 lines) document the two changed behaviours; the plan names design.md, and decisions.md describes the same exception-match rule. Not an unrequested claim.
- Runtime: `git archive` line counts of cli/wuwei are 3396 at 6828776 and at the head (limit 3400); the vendored copy matches the tree (same md5 over the concatenated sources). The "6 lines in place" claim in the PR body is 3 per copy by `git diff --stat`.
- Not run: the full suite (the body's 3227 passed is the builder's; I started it and did not wait for it). The route differential (288 routes) was not re-run by me; it is the arch and security gates' input and the change sits in a branch no Bash route reaches. CI is not my input.
- No closed findings (first round).

## Residual risk
The last-`|` rule cuts about 2 of 702 real finding rows short; those stay held and the owner would need a different text (fails closed, noted). Below-full spec-gap exceptions are now passable by the guard; harmless by the stated assumption.
