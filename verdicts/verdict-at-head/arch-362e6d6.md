Verdict: FIX
Gate: arch
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: 362e6d6a96437713b9bec60eb2310f406d17225d
Confidence: high
Breaking: yes: the merge door, `wuwei evidence` and the board now report "gates missing" on a PR whose gate was cleared on main by a PASS naming another PR or repository, by a PASS at a head off the PR's line, or by a PASS at an older head attested after a finding. An open PR that was mergeable on main is held and needs a new gate run on its own PR. Route corpus: 142 of 1,506 door reads move from pass to a door, 23 of them merge routes on o/r#5 cleared by a PASS for o/r#7.

## Findings
- [medium] docs/site/concepts/evidence.md:117 blocks: yes. Failure: the site still states main's rule, "At one head, a later pass does not outvote a finding; a new head does". At this head a pass at an older head, at a head off the PR's line, or one naming another PR or repository does not outvote a finding, and does not count at all. The site never says a pass counts only for its own PR. An operator who follows the site relaunches a gate at an older head, or relies on another PR's PASS, and sees "gates missing" that no user doc explains. This is docs drift on the contract this PR changes: docs/design.md:117-121 was updated but the site was not. Fix: put the design.md sentences on the site page.
- [medium] cli/wuwei/evidence.py:298 blocks: yes. Failure: this line breaks an outward contract without declaring it. The PR filter and the walk change the merge-door and `wuwei evidence` decision for the same ledger state. A PR that was mergeable on main through a PASS naming another PR of the item, another repository or an off-line head now reads "gates missing". I re-ran the route probe: 142 reads move from pass to a door. The four fixtures this diff edits in tests/test_guards.py and tests/test_evidence.py are tests of the old contract. Precedent: #1114, #1142 and #1148 each declared `!` and BREAKING CHANGE when they held PRs that read mergeable on main; #1135 only loosened its check and declared none. The title has no `!`, and the body has no BREAKING CHANGE line, migration or `Announcement:` line. Fix: declare the break, add the migration (re-run the gate on the PR itself with `PR: <owner/repo>#<n>`), post the announcement, and ask the owner `breaking:`.
- [low] cli/wuwei/guards.py:268 blocks: no. The create door and the ready door (through create_door) pass ref='', so at the ready flip a PASS for another PR of the same item in the same repository still counts. The merge door holds it, so this is a process gap (a PR turns ready before its own gates pass), not a merge hole, and it is narrower than on main. It belongs in a follow-up item: `ready_door` should pass `f'{repo}#{number}'` into create_door and on to gate_gaps. That is a guard change and must carry the route-corpus differential. The PR body calls it a candidate, but neither .wuwei/plan.json nor .wuwei/candidates.json names it yet.
- [low] docs/design.md:118 blocks: no. "(for its repository before the PR is read)" reads as if the ready flip were per PR, and it does not say that a PASS naming only the repository, or an imported one, counts for every PR of the item in that repository. Name the create and ready doors and the repository-only PASS explicitly.
- [low] cli/wuwei/evidence.py:357 blocks: no. Operability: `uncounted` lists only unattested or malformed files. A PASS that is attested but dropped (another PR or repository, an off-line head, or an older head after a finding) leaves the gap "gates missing" with no reason, even though the site promises that a verdict that does not count is never silent (site:120, which scopes that promise to shape and attestation). The cross-PR drop is a new silent class. Candidate follow-up: name the dropped PASS and why.
- [low] cli/wuwei/evidence.py:247 blocks: no. `verdicts` derives `ref` from the verdict body while the attest row already records `pr` (hook.py:178). The two are equal for an unedited file, but one fact now has two sources.

## Probes
- Rulings on the brief's questions:
  - Q1, the builder's reading is right and recorded. A finding about code on this PR's line is evidence whichever PR it was filed on. Keeping it fails closed, and a PASS on this PR at a strict descendant head clears it. Only a finding at exactly the PR head needs a new commit, which acceptance 3 already requires. The reading is recorded in the spec Assumptions, the PR body Assumptions with what would overturn it, and analysis A1. It is a two-way choice.
  - Q2, Breaking: yes, per the precedent above.
  - Q3, no collision with #1148 or #1150.
  - Q4, the ready door is a follow-up.
  - Q5, design.md matches the code apart from the doors wording; the site does not match.
- Conformance: `newer` is the #1135 walk moved out of breaking_gaps and shared, with no new import or module and no new layering edge. verdicts() has two consumers (grep `verdicts(` in cli/wuwei): gate_gaps and breaking_gaps; upgrade.verdicts is a different function. breaking_gaps now compares heads on 7 characters, which is equivalent because parse requires a 40-hex head (verdict.py:38).
- Fitness: runtime `cat cli/wuwei/*.py | wc -l` gives 2,993 at d7c4f43 and 2,998 at the head (+5, the item's budget, under 3,400). With #1148, #1150 and main dc39cae merged in it is 3,018. `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows the vendored copy is identical.
- Suite, head copy (git archive): `pytest -q` gave 1812 passed, 2 skipped.
- `git merge-tree --write-tree` exited 0 with no conflicts for:
  - head with #1148 (a1052b4)
  - head with #1150 (24062fd)
  - #1148 with #1150
  - head with main dc39cae
  - all four together, tree 5460e68 plus main
- The combined tree's suite gave 1936 passed, 2 skipped.
- Semantic check of #1150: its GATES regex parses the "gates missing at head" and "no gate passed at head ... (a delta review by" texts, which this PR leaves unchanged. #1148 edits breaking_gaps after the loop this PR touches. Their site hunks (lines 77 and 151) are clear of lines 113-121.
- Mutants, each in a fresh copy and run against test_evidence, test_breaking and test_guards: 9 of 9 killed.
  - findings filtered by PR: 2 failures
  - repository-only split at the doors dropped: 37 failures
  - PR filter dropped: 3 failures
  - finding no longer displaces a pass: 5 failures
  - outer ancestor check dropped: 1 failure
  - same-head check dropped: 5 failures
  - descent from the held head dropped: 4 failures
  - case fold dropped: 1 failure
  - head ancestry dropped in newer: 1 failure
- Route corpus (sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1, the same at main and the head): I ran specs/verdict-at-head/route_probe.py at d7c4f43 and at the head, 1,506 reads over 251 routes. 142 reads move, all from pass to a door. This matches the builder's table row for row. No PASS form for a route's own PR moves. No o/r#7 ready move appears on o/r#5 routes, which confirms the ready-door residual.
- Guard code: guards.py and hook.py are unchanged, so no parser probe is owed.
- Confidence high: every mutant was killed, both probes reproduced exactly, and the combined merge is green. The Breaking call is a judgement against the stated precedent.

## Residual risk
At the ready flip a PASS from another PR of the item in the same repository still counts until ready_door passes its PR. A PASS dropped for its PR or head is silent apart from the gate gap itself.
