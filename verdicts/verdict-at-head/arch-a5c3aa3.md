Verdict: PASS
Gate: arch
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: a5c3aa37ca9e1f00596f579c420c38ceca9cf6f7
Confidence: medium
Breaking: no (patch: the gate now counts only the verdicts the base docs already described as evidence at the PR head; `wuwei evidence` exit 1 still means gaps)

## Findings
- [low] blocks: no. The PR body's Assumptions still say "#1154 is still open at this writing" and "Overturned if #1154 does not merge". #1154 merged as b5822fe (REST `pulls/1154`: merged true). Change the line to say it merged, and drop that overturn clause. This is process text and does not change the classification.
- [low] cli/wuwei/evidence.py:247 blocks: no. Carried from 362e6d6. `verdicts` derives `ref` from the verdict body, while the attest row already records `pr` (hook.py:178). So one fact has two sources.
- [low] cli/wuwei/evidence.py:357 blocks: no. Carried from 362e6d6, now scoped by the docs. An attested PASS dropped for its PR or its head still leaves only "gates missing" with no reason. The site now says this (evidence.md, "shows only as the gate missing"), so it is a documented limit, not drift. Candidate follow-up: name the dropped PASS and why.

## Probes
- closed: site drift (docs/site/concepts/evidence.md:117) at a5c3aa3. The page now states the rules:
  - a verdict counts only at an ancestor of the PR head;
  - a PASS counts for this PR, its repository alone, or no PR;
  - a finding counts from any PR;
  - a pass at the same or an older head clears nothing;
  - the create and ready doors read no PR;
  - the migration is to re-run with `PR: <owner/repo>#<n>`.
  I checked each rule against gate_gaps at the head (evidence.py:297-302) and against docs/design.md:127-133. They agree.
- closed: undeclared break (evidence.py:298) at a5c3aa3. Under main's rule 7 (charters/sentinel-arch.md at b5822fe) and its "Breaking changes" table, this change is a patch. The docs at the base 5fe8347 already said the following (read with `git show 5fe8347:<path>`):
  - charters/_common.md:29,32: "Done means safety evidence at the PR head", "the gates the diff needs, passed at the head".
  - charters/_gate.md:3,56: a gate reviews "one item at one head", and its verdict names `PR: <owner/repo>#<number>`, or `<owner/repo>` alone before the draft exists.
  - docs/design.md:85: gates pass "at the head ..., each at an ancestor of the head".
  - docs/site/concepts/evidence.md:118-119: "At one head, a later pass does not outvote a finding; a new head does".
- How each moved case reads against those lines:
  - A PASS at an older head, or at a head off the line, used to clear a finding attested before it. That contradicted evidence.md:118-119, because only a new head outvotes a finding.
  - A PASS that names another PR was counted as this PR's evidence. That contradicted _common.md:29 and the PR binding in _gate.md:56.
  - The repository-only form and the no-PR imported form still count. So the documented pre-draft verdict keeps working (pinned by `test_an_imported_pass_counts_for_every_pr_of_its_item`).
  - The exit code keeps its meaning, which the main table names as a patch.
- The one soft reading: design.md:85 says "an ancestor of the head" without naming the PR. I resolve it with _common.md:29. A reading that design.md:85 alone promised cross-PR passes would make the change a major. That is what would overturn this call. The title has no `!`, and the Release notes say patch with the migration.
- breaking_gaps filter (evidence.py:343): in scope and recorded.
  - The promise says gate_gaps reads verdicts "the way breaking_gaps does ... on this PR", and the filter applies the same PR scoping to the arch `no`. The file is in the item's file list.
  - It is recorded as spec.md FR-006, in plan.md, and in the body's What-and-why and Review notes.
  - It fails closed: a yes still holds from any PR.
  - It is a patch for the same reason as above: a verdict naming #7 is not #5's evidence.
  - Verdicts without a `breaking` key (held or imported rows) never reach `v['ref']`, so there is no KeyError.
- Mutants, each in a fresh `git archive a5c3aa3` copy, with both cli/wuwei and the vendored copy changed, run against test_evidence, test_breaking and test_guards:
  - B1, filter dropped: killed (1 failure).
  - B2, repository-only form dropped: killed (1 failure).
  - B3, case fold dropped: killed (1 failure).
  - G1, round 0's `newer(..., head)` restored: killed only by the call-count test. This is as expected: gh.ancestor returns early on equal shas (gh.py:119), and the outer condition already asked the PR-head ancestry. The builder's 48,592-case moves file is byte-identical to round 0's, which is the differential showing behaviour equivalence.
- Fitness, `cat cli/wuwei/*.py | wc -l`:
  - main 73af8d4: 3,092;
  - head: 3,031 (base 3,026 plus 5, within the item's budget of 5);
  - merged tree: 3,097, under 3,400.
  - `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference at the head or in the merged tree.
- Suite at the head copy: `pytest -q` gave 1953 passed, 2 skipped.
- Merge with main 73af8d4: `git merge-tree --write-tree origin/main a5c3aa3` exits 0 (tree 07bec66), so it merges cleanly.
  - The merged tree has no leftover "outvote" line on the site.
  - Its suite gives 40 failed, 2064 passed. Main 73af8d4 alone gives the same 40 failures: `test_the_board_fills_the_cap_to_the_character_at_any_title_and_path_length`, KeyError 'models' in ws.write_config, the #1146 x #1149 clash. Main's CI test (3.13) also fails at 73af8d4.
  - An andon for main red is already in the ledger (.wuwei/ledger/78cdacfe.jsonl), so I did not pull it again. None of the 40 comes from this PR.
- closed: the design.md doors wording (low) at a5c3aa3. design.md:128-130 now names the create and ready doors and the repository-only pass.
- closed: the ready-door residual (low) as tracked. It is a plan item in .wuwei/plan.json:79 ("the ready door reads gates for the PR it turns ready").
- Guard code: guards.py and hook.py are unchanged since 362e6d6, so no parser probe or route differential is owed this round. The builder's re-run at 257 routes shows the same 142 moves.
- Why confidence is medium: the code, mutants and merge are sound, and every claim was reproduced. The Breaking call rests on reading design.md:85 under _common.md:29. An owner reading that the base docs promised cross-PR passes would turn it into a major.

## Residual risk
At the create and ready doors, a PASS from another PR of the item in the same repository still counts until the plan item at plan.json:79 lands. A dropped PASS shows only as the gate missing.
