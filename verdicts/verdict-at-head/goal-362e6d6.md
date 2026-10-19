Verdict: PASS
Gate: goal
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: 362e6d6a96437713b9bec60eb2310f406d17225d
Confidence: medium

## Findings
- [low] blocks: no. The promise says "a verdict counts only at an ancestor of the PR head and on this PR". The code applies "on this PR" to a PASS only; a FIX from another PR of the item still holds. The PR body records this under Assumptions with its reason (dropping such findings loosens the gate) and what would overturn it. Acceptance scenario 2 names a PASS only, so the acceptance is met. A note for the owner, not a gap.
- [low] blocks: no. Files touched beyond the promise's list: tests/test_guards.py (three fixtures that attested a PASS for acme/app#42 while reading o/r, now naming the PR their door reads) and the specs/verdict-at-head/ artifacts (required at full). Both are stated in the PR body. The design.md edit is at lines 114-121, not 108; the text is the same section.
- [low] blocks: no. A FIX at an older ancestor head attested after a PASS at a newer head displaces the PASS (the gate reads again). This matches main and is stated in the spec and the body. It is stricter than the promise needs, but it is not new.

## Probes
- Goal trace: G-2 (bugs found running WUWEI on itself fixed before features). The item's why cites the #1135 gate finding at 21d9ce3. The delivered change is in cli/wuwei/evidence.py: gate_gaps now walks each gate's verdicts oldest first through newer(), and breaking_gaps shares that walk. Read with `git diff d7c4f43 HEAD` in the builder worktree.
- Acceptance 1 (arch FIX at head, older ancestor PASS attested later, still owed): traced through the code. The older PASS fails newer(), because the held head is not an ancestor of the older head. The test row is `[(HEAD,'FIX'),(OLD,'PASS')] -> OWED`.
- Acceptance 2 (a PASS at a non-ancestor head, or for another PR, does not count): the PASS guard on `said in (repo, ref)` plus the ancestor check. Test rows: `(OTHER,'PASS')`, `acme/app#7`, `acme/other#42` all owed.
- Acceptance 3 (FIX then PASS at the same head, still owed): newer() is false on the same 7-character head. Test row `[(HEAD,'FIX'),(HEAD,'PASS')] -> OWED`.
- Promise "reuses the ancestry walk": newer() is a single function called from gate_gaps and breaking_gaps. The vendored copy .claude/wuwei/cli/wuwei/evidence.py has the same changed lines as cli/wuwei/evidence.py (diff of the +/- lines is empty).
- Runtime lines, read with `cat cli/wuwei/*.py | wc -l` on `git archive` copies: d7c4f43 gives 2993 and the head gives 2998. That is +5, equal to the item's budget of 5 (the estimate was +3). The body's figures match.
- Body check (read live with `gh api repos/taoq-ai/wuwei/pulls/1152`): it names `WUWEI-Item: verdict-at-head`, the promise (What and why, with the spec as the explain-back), the assumption that a finding for another PR still holds, and the residual under Review notes (create and ready doors read no PR, so a PASS for another PR of the item in the same repository still counts there; candidate to pass `f'{repo}#{number}'` from guards.ready_door). It also has a Rollback line. The PR is a draft and the head matches the brief.
- Explain-back: spec.md "The promise in my words" and the three restated scenarios match the plan item's promise and acceptance with no drift. It claims nothing the item did not ask for, apart from the declared assumptions.
- Measures not recomputed: I did not re-run pytest (the module is missing in this environment) or the generated probes (probe.py, route_probe.py). The body's counts (1812 passed; 48,592 histories, 7,479 move; 251 routes x 6 forms, 142 moves) are therefore unverified by me. The goal gate judges the delivered artifact against the item, and the quality and security gates own the re-runs.

## Residual risk
The create and ready doors still let a PASS for another PR of the same item in the same repository count; this is declared and routed to a candidate outside the item's files. The 316 cases that now owe less are explained as delta reviews with a PASS for this PR at the head, but I did not re-derive them.
