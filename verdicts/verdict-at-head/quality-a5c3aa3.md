Verdict: PASS
Gate: quality
Item: verdict-at-head
PR: taoq-ai/wuwei#1152
Head: a5c3aa37ca9e1f00596f579c420c38ceca9cf6f7
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:343 blocks: no. Untested part of the breaking_gaps filter: a yes from another PR still holds (plan.md and FR-006 say so, and main behaves the same way), but no test pins it. Mutant B4 also applies the ref filter to the yes branch (`if v['ref'].lower() in (...) and (v['breaking'] or newer(...))`). It survived twice, each time in a fresh copy. The input it lets through: an arch yes on acme/app#7 for the same item at the PR head, after an arch no on acme/app#42 at that head. With the mutant, #42 owes no announcement. Missing test: add a row to test_breaking_is_read_from_the_latest_arch_verdict, `[(HEAD, 'no', 'PASS'), (HEAD, 'yes: x', 'PASS', 'acme/app#7')] -> ANNOUNCE`.
- [low] cli/wuwei/evidence.py:343 blocks: no. Mutant B1b (`in (ref, repo)` without .lower()) survived twice in fresh copies. No test passes a mixed-case repository to evidence.gaps. With the mutant, `wuwei evidence Acme/App#42` would keep a cleared yes, a spurious gap that fails closed. It is not a hole.
- [low] blocks: no. The three new gate_gaps tests (imported PASS, imported short-head FIX, calls once) call evidence.gate_gaps directly with the ref that gaps builds, not evidence.gaps. The three new breaking rows go through evidence.gaps by way of the breaking() helper. The real consumer passes the same arguments (evidence.py:385, 403), so this is a reach note, not a coverage hole.
- [low] blocks: no. Carried from round 0, unchanged: acceptance 1 names arch, but the fixture uses quality. An imported verdict with no ref is read as being for the caller's repository (recorded under the spec's Assumptions).

## Probes
- closed: repeated gh.ancestor(found['head'], head) in gate_gaps through newer at a5c3aa3. evidence.py:300 now passes found['head']. gh.ancestor short-circuits when older == newer (gh.py:119), so no call is made. Mutant D1 (passing head again) is killed by test_the_walk_asks_the_code_host_about_each_pair_of_heads_once only.
- closed: the plan's call-count claim at a5c3aa3. plan.md:20-27 and spec.md now state 2.0x main from calls.py. I re-ran calls.py myself (`python3 -I calls.py <tree> <scratch>`) and got the same counts in all three shapes. Head: 24/54/114/234 calls at 5/10/20/40 heads. Main 5fe8347: 12/27/57/117. Distinct pairs at head: 7/17/37/77.
- closed: the 7-character note (N4) at a5c3aa3. The full-head mutant is now killed by test_an_imported_finding_at_a_short_head_holds_against_a_pass_at_that_commit.
- Suite (pytest -q, git archive copies, wall-clock tests deselected by -k: 15 tests): head 1938 passed, 2 skipped, 15 deselected (1953 in all, matching the builder). Main 5fe8347: 1910 passed, 2 skipped.
- Mutants on cli/wuwei/evidence.py. Each ran in a fresh copy, full suite, vendored-copy test and timing tests deselected (scripts/mutate.py). Five of them ran at the same time once; that does not change the results, because no timing test was collected.
  - D1, ask about head again: killed (test_the_walk_asks_..._once).
  - B0, breaking filter removed: killed (said9, the another-PR no on the line).
  - B1, v['ref'] not lower-cased: killed (said11, Acme/App#42).
  - B1b, ref and repo not lower-cased: SURVIVED, and SURVIVED again (note).
  - B2, repository-only ref dropped: killed (said10).
  - B3, this-PR ref dropped: killed (said0, said11, said12, test_ledger_order_decides_not_file_names).
  - B4, filter applied to a yes too: SURVIVED, and SURVIVED again (note).
  - B5, any PR of the repository: killed (said9).
  - N3, newer's v-to-head ancestor dropped: killed (test_a_no_on_a_dropped_descendant_of_the_yes_clears_nothing).
  - N4, full-head compare: killed (the short-head imported FIX test).
  - M13, an imported verdict without a ref read as no repository: killed (the imported PASS test, [acme/app#42] and [acme/app#7]).
- History probe (probe.py, main 5fe8347 against head): 48,592 cases and 7,479 moves. Main has 6,175 ignored and 864 no-clear holes, and the head 0 and 0. Compare calls: main 86,944, head 84,454. The sorted moves sha256 is 1069931ea5712ab2ac48c4f6bcf933795099915d01c73410178f15a169877ba8, the same as spec.md.
- Runtime: `cat cli/wuwei/*.py | wc -l` gives 3,026 at main and 3,031 at head (+5, budget 5, cap 3,400). The vendored copy has no difference (diff -r without __pycache__).
- PR head read once over REST: draft, head a5c3aa37, open.
- Simplicity: nothing in the delta can be deleted. The `v['ref']` filter is fail-closed handling, and each of its members is killed by a named row. The new tests each kill a distinct mutant. The only call saving left is a per-read memo of gh.ancestor (37 distinct pairs against 114 calls at 20 heads). That is an optimisation, not dead code.
- Confidence high: every count the builder gave was reproduced exactly, both round-0 issues were closed by tests that kill their mutants, and the two survivors are untested edges outside the promise that fail closed or keep main's behaviour.

## Residual risk
The walk still makes 2x main's compare calls on long histories, and a memo would bring it to the distinct pairs. A yes from another PR holding is untested and could be lost silently by a later edit.
