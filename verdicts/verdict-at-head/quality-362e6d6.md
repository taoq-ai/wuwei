Verdict: FIX
Gate: quality
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: 362e6d6a96437713b9bec60eb2310f406d17225d
Confidence: high

## Findings
- [medium] cli/wuwei/evidence.py:298 blocks: yes. Failure: on a long review history the walk roughly triples the code-host compare calls per gaps read, and a third of those calls repeat a check gate_gaps has just made. gate_gaps calls gh.ancestor(repo, found['head'], head) and then newer() (evidence.py:254) calls gh.ancestor(repo, v['head'], head) again for the same pair. Measured with a fake host over one line of N heads, three gates verdicted per head, read at the last head (calls.py): main 27 / 57 calls at 10 / 20 heads, this head 78 / 168, with 17 / 37 distinct pairs. A board reading several such PRs uses about 3x main's REST quota and reaches rate-limit failures sooner. The plan states the opposite (specs/verdict-at-head/plan.md:20-21, "The ancestry checks are the compare calls gate_gaps already makes"); that holds only for the probe's histories of at most 3 verdicts, where the PR filter skips calls (86,944 to 86,095). This is the "number or claim the data does not support" class. The duplicate can be deleted: passing found['head'] as newer's head in gate_gaps gives 0 result differences over the builder's 48,592 generated cases (head against the variant), keeps the suite green (1811 passed), and cuts calls to 114 at 20 heads (84,454 in the probe). A per-read memo of gh.ancestor would bring it to 37. Fix: drop the repeated call and correct the plan's claim using a long-history count.
- [low] cli/wuwei/evidence.py:253 blocks: no. Untested guard (existing gap, the same on main at evidence.py:291): changing the 7-character head comparison in newer to a full comparison (mutant N4) survives the suite twice, each time in a fresh copy. The input it lets through is an imported 0.34 FIX at a short head followed by a parsed PASS at the same commit in full: with the mutant the PASS clears the FIX (short.py prints [] instead of "gates missing at head aaaaaaa: quality"). Main's same mutant also survives (1791 passed). Missing test: an imported short-head FIX, then a full-head PASS at that commit, still owes the gate.
- [low] blocks: no. Acceptance 1 names an arch FIX and arch PASS; the fixture (test_a_gate_is_read_from_its_verdict_at_the_newest_head_on_this_pr, said0) uses quality. The walk does not depend on the gate, so this is a naming gap, not a coverage hole.
- [low] blocks: no. An imported or edited verdict carries no ref, so `found.get('ref') or repo` reads it as being for whatever repository the caller reads. It is the same on main and recorded under the spec's Assumptions.

## Probes
- Suite at head (git archive copy): 1812 passed, 2 skipped (test_release.py:36 and :57, ssh-keygen absent; base skips the same two). Base: 1792 passed.
- Red check: head tests on base code fail 7 (said0, said2, said3, said5, said6, said10, acme/other#42), which matches the builder's 7.
- Mutants on cli/wuwei/evidence.py, one per fresh copy, full suite with test_the_vendored_plugin_matches_the_tree_it_was_copied_from deselected (mutate.py). A kill means a behavioural test failed:
  - G1, dropping the `fix or` bypass: killed (said13, another-PR FIX holds [False]).
  - G2, `said.split('#')[0]` used with ref: killed (said2).
  - G3, full said used without ref: killed (37 failures, door tests).
  - G4, no PR filter: killed (said2, said3, acme/other#42).
  - G5, ref.lower() dropped from the membership tuple: killed (103).
  - G6, repo.lower() dropped from it: killed (42).
  - G7, said not lower-cased: killed (said9).
  - G8, gate_gaps' ancestor check dropped: killed (said1).
  - G9, the clause where a FIX displaces a PASS dropped: killed (said11, said12, said13, both another-PR FIX cases).
  - G10, any FIX displaces: killed (said5).
  - G11, newer forced true: killed (6, including the existing same-head tests).
  - G12, fix meaning ESCALATE only: killed (5).
  - N1, newer's same-head test dropped: killed (5, including a breaking test).
  - N2, the held-to-v ancestor dropped: killed (4).
  - N3, the v-to-head ancestor dropped: killed only by the breaking test test_a_no_on_a_dropped_descendant_of_the_yes_clears_nothing. This is expected, because gate_gaps checks the same pair itself (see the finding).
  - N4, full-head comparison: SURVIVED, re-run in a fresh copy: SURVIVED (note above).
  - V1, ref always the repository: killed (said2).
  - V2, no ref key: killed (3).
  - V3, ref always repo#pr: killed (said8).
- Builder's history probe, re-run main against head: 48,592 cases, 7,479 moves, main 6,175 ignored / 864 no-clear holes, head 0 / 0, compare calls 86,944 / 86,095. This matches the spec.
- Differential, head against the dedup variant (gate_gaps passes found['head'] to newer): 0 moves over 48,592 cases, 0 holes, calls 86,095 to 84,454.
- Long-history call counts (calls.py, fake host, 3 gates, shapes fix-then-pass / pass-each / ping): at 20 heads, main 57, head 168, dedup 114, distinct pairs 37.
- Route corpus probe (route_probe.py copied into a tests/ folder of fresh copies). Corpus sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1, the same at base and head. 1506 reads on 251 routes, 142 moved, 0 moved from a door to pass. Every o/r, o/r#5 and o/r#7 move apart from the 22 o/r#7 merges on o/r#5 is a route naming https://github.com/other/x/pull/..., and the counts match the spec's table.
- Fixture changes: in test_guards.py and test_evidence.py, the attest calls now name the PR or repository their door reads, and test_every_merge_route_passes_on_a_pr_without_gaps adds an other/x#5 PASS for the URL routes. No refusal assertion was removed or loosened. The refusal half of test_a_draft_leaves_draft... still runs before the attest.
- Acceptance: lines 1 to 3 are pinned through evidence.gaps (said0; said1 and said2; said4), and the doors are covered by the test_guards routes.
- Vendored copy: diff -r cli/wuwei .claude/wuwei/cli/wuwei shows no difference beyond __pycache__.
- Line budget: cat cli/wuwei/*.py | wc -l gives 2,993 on base and 2,998 at head (+5, item budget 5, cap 3,400).
- Ledger history size: unmeasured. Reading .wuwei/ledger was refused by the guard hook, so real per-item verdict counts come from the synthetic histories above.
- Simplicity: the repeated gh.ancestor(found['head'], head) inside newer, as called from gate_gaps, can be deleted (generated differential, 0 differences). Passing found['head'] or a per-read memo replaces it. Nothing else is deletable: the PR filter, the clause where a FIX displaces a PASS, and the same-head test are each killed by a behavioural test and are fail-closed handling.
- Confidence high: 19 mutants run, 18 killed by named behavioural tests, the builder's probes reproduced exactly, and the call amplification measured directly. A real ledger with mostly short histories would lower the weight of the call finding, not its existence.

## Residual risk
At the create and ready doors no PR is read, so a PASS for another PR of the item in the same repository still counts there (the builder's recorded limit, outside this item's files). The walk's held-to-found ancestry adds calls by design even after the dedup (about 2x main on long histories).
