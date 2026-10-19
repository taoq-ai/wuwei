Verdict: FIX
Gate: arch
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: bf88fb49e19d12845030762c742081441731dd68
Confidence: medium
Breaking: no (patch: against main 5a33509, every moved case is a PASS the docs at 5a33509 did not make evidence for this PR at this head; the documented Supersedes use, a same-head PASS on this PR naming the FIX, still clears)

## Findings
- [medium] docs/design.md:137 blocks: yes. Failure: contract drift (the evidence contract, requirement versus output). The merge inserted the Supersedes clause right before "An arch `Breaking: no` clears a yes the same way". Read as written, that sentence says a same-head `Breaking: no` naming the FIX on a Supersedes line clears a yes. breaking_gaps (evidence.py:346, through `newer`, evidence.py:252, which needs a different head) reads no Supersedes. Probe P1: arch FIX `Breaking: yes` at HEAD, then arch PASS `Breaking: no` at HEAD with `Supersedes: I-1/arch-fix.md`. gate_gaps clears arch, but the board still says "breaking change without an announcement" on both main and head. A gate following design.md and _gate.md:60 withdraws its yes this way, and the PR is then held for an Announcement plus the owner's `breaking:` on a patch, or for the no-op commit #1162 removed. Before the merge the sentence was unambiguous ("only a pass from a strict descendant"). Shortest fix: in design.md say that a no clears a yes only from a strict descendant of its head, for this PR or its repository alone, and that Supersedes does not apply to it. That matches the code and the breaking_gaps docstring. Extending Supersedes to breaking_gaps would be a scope change.
- [medium] cli/wuwei/evidence.py:300 blocks: yes. Failure: an untested guard (requirement: "an ESCALATE stays the owner's", #1162). The merge's stricter reading, where an ESCALATE stays held against a later FIX at its head, has no test. Mutant E1 lets `named` take a held ESCALATE for a later finding while still refusing a PASS that names it, which is main's reading. It survives the whole of tests/test_evidence.py, test_breaking.py and test_guards.py (1567 passed). The input the reversed guard lets through is probe P2: quality ESCALATE at HEAD, then FIX at HEAD, then PASS at HEAD with `Supersedes: I-1/q-fix.md`. Main reads it clean (`[]`), so an owner's escalation is cleared by two seat verdicts with no owner answer. The head holds it (`gates missing at head aaaaaaa: quality`). Add that history as a row of `test_a_pass_clears_a_finding_at_its_head_only_by_naming_it`, or as its own test.
- [low] charters/_gate.md:60 blocks: no. Neither the charter line nor the docs say that a later FIX or ESCALATE at the same head replaces the held FIX, so the PASS must name the newest one. A gate naming its own earlier FIX after a second seat wrote a newer one clears nothing, and that fails safe. The gate_gaps docstring and spec.md:52 say it; the site and the charter could add "the newest FIX file at this head". #1166 carried the same gap on main.
- [low] cli/wuwei/evidence.py:248 blocks: no. Carried. `ref` is derived from the verdict body, while the attest row records `pr`, so one fact has two sources.
- [low] blocks: no. Carried and documented. A dropped PASS still shows only as the gate missing (evidence.md, last line of the attestation paragraph).

## Probes
- Read: plan with `wuwei plan show verdict-at-head`; PR via REST `repos/taoq-ai/wuwei/pulls/1152` (head bf88fb4, draft); checks via REST `commits/bf88fb4/check-runs`: 8 of 8 success. Copies made with `git archive` of bf88fb4 and of 5a33509 under my scratch folder.
- Merge keeps every rule from #1166 (`git show 5a33509`, `git diff 5a33509 bf88fb4`). Each rule and where it lives at the head:
  - A named PASS at the FIX's head clears it: `named` at evidence.py:300.
  - An unnamed PASS at that head does not: it is neither newer nor named.
  - A PASS naming an ESCALATE does not clear it: `prior['verdict'] == 'FIX'`.
  - A later FIX at the same head replaces the held FIX: `fix or`.
  - Matching is by `<item>/<file>`: `parts[-2:]`.
  - `path` is on parsed and held rows: verdicts(), evidence.py:244 and 248.
  - The verdict.py parse, the template and charters/_gate.md are unchanged from main (`diff` gives no output).
  - No test of main's was dropped: `comm` over the test names gives none missing. The one changed line is `not_started`, which now names `pr='o/r#5'`.
- Merge keeps every rule from this branch (`git diff a5c3aa3 bf88fb4 -- cli/wuwei/evidence.py`): it changes only the `path` key, the `named` term and the docstring, so the walk, the PR scope and breaking_gaps stay as I passed them at a5c3aa3.
- Coherence: gate_gaps (evidence.py:297-305), design.md:131-138 and evidence.md:158-165 state the same rule for gates:
  - only verdicts at an ancestor of the PR head count;
  - a pass counts for this PR, its repository, or no PR;
  - a finding counts from any PR and displaces a pass;
  - an older-head pass never clears;
  - a same-head pass clears only a FIX it names;
  - an ESCALATE stays held.
  The one exception is the Breaking sentence in finding 1. The site does not restate the Breaking clearing rule, so the rule is stated once there; design.md is where it drifts.
- Probes P1-P4 ran in both copies (a pytest file I added to each copy, then removed):
  - P1, Breaking: the same output on main and head (announcement gap held).
  - P2, ESCALATE then FIX then named PASS: main `[]`, head quality missing.
  - P3, named PASS for `acme/app#7`: main `[]`, head quality missing.
  - P4, named PASS at OLD for a FIX at OLD, with a newer FIX at HEAD: main `[]`, head quality missing.
- ESCALATE narrowing: acceptable as a two-way choice, not an owner question.
  - It is cheap to undo: one condition.
  - It is recorded under spec.md:205-207 and the PR's Assumptions.
  - It matches what main documented at 5a33509: evidence.md:159 says "At one head, a later pass does not outvote a finding; a new head does". Main's own intent, in #1166's message and its test name, is "an ESCALATE stays the owner's".
  - Main's path that cleared it was a bypass of that.
  - It only needs a test (finding 2).
- Breaking under rule 7 at 5a33509 (charters/sentinel-arch.md and the evidence.md "Breaking changes" table there). Each case that moves relative to main, P2-P4, owes more, and each contradicted docs at 5a33509:
  - evidence.md:159 (the same-head rule);
  - _common.md "evidence at the PR head";
  - _gate.md's `PR:` binding.
  The documented Supersedes form at _gate.md:60, a same-head PASS on this PR, still clears (the builder's 6-row test, and my P3 counter-case for this PR). `wuwei evidence` exit 1 keeps its meaning. So this is a patch. A reading that main's Supersedes line promised cross-PR clearing would make it a major; the line names no PR, while the template's `PR:` line binds the verdict.
- Mutant E1 (finding 2), in a fresh `git archive bf88fb4` copy with both cli/wuwei and .claude/wuwei/cli/wuwei changed: survived, 1567 passed. I did not re-run the builder's M1-M7, which the PR body reports as killed.
- Fitness, `cat cli/wuwei/*.py | wc -l`: main 5a33509 3,178, head 3,183 (+5, within the item's budget of 5, under 3,400). `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows nothing at either tree. `bin/wuwei agents check` says agents match the charters.
- Suite at the head copy, `pytest -q`: 2142 passed, 2 skipped.
- Guard code: guards.py and hook.py are unchanged by the merge round, so no parser probe is owed. The builder reports the route corpus at sha256 9e099867...7901b0 with the same 142 moves as round 1; I did not re-run it.
- Why confidence is medium: I read the combined condition case by case and reproduced the four edge histories in both trees. The Breaking call still rests on the `PR:` binding reading of main's docs.

## Residual risk
Once findings 1 and 2 are fixed, the rule is coherent. The create and ready doors still count a PASS from another PR of the item in the same repository (plan item at plan.json:79). A gate that names an older FIX clears nothing, and that is undocumented but fails safe.
