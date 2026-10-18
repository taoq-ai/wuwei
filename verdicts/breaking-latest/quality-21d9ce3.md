Verdict: PASS
Gate: quality
Item: breaking-latest
PR: taoq-ai/wuwei#1135
Head: 21d9ce378a078a0364ba418fb17d039904ea5dee
Confidence: high

## Findings
- [medium] cli/wuwei/evidence.py:333 blocks: no. Stale-head clear (fail-open on the breaking-change safety gap): an arch PASS at the PR head saying "Breaking: yes: drops --format", then an arch PASS at an older head saying "Breaking: no" attested after it, makes evidence.gaps return [] (fully clean) at the head, where main returns the announcement gap. This matches the approved promise (ledger order decides) and the builder disclosed it, so it is not a requirement violation. But the bound in specs/breaking-latest/spec.md "How this fails 1" ("the arch gate still owes a pass at the head") does not hold: the PASS at the head that found the break satisfies it. Follow-up: read the latest arch verdict at the PR head when one exists, else the latest overall (a one-line change), or have the owner confirm ledger order knowing this case.
- [low] tests/test_evidence.py:894 blocks: no. `import os` inside the test body; the file's convention is top-level imports. The os.utime lines are decorative, since verdicts() never reads mtimes, but harmless.
- [low] blocks: no. An arch verdict with no Breaking: line at all parses to breaking '' and would clear an earlier yes (probe NOLINE). It cannot happen in practice: hook attestation parses strictly and refuses an arch verdict without the line, and upgrade imports are stubs with no breaking key, which the filter skips.

## Probes
Suite at head in a git archive copy: 1693 passed, 2 skipped (test_release.py:36 and :57, ssh-keygen absent). The 9 new tests are collected and none is skipped.
Mutants, each in a fresh git archive copy, full suite run: (1) revert to main's any() rule: killed by latest_arch[said0] (acceptance 1), [said2] and test_ledger_order_decides_not_file_names_or_times. (2) arch[0] instead of arch[-1]: killed by all 5 latest_arch rows and ledger_order. (3) gate filter dropped: killed by latest_arch[said1,said3,said4] and test_breaking.py::test_the_arch_gate_finds_an_undeclared_break. (4) 'breaking' in v filter dropped: killed by test_an_edited_arch_verdict... (KeyError) and test_upgrade::test_an_imported_pass_needs_only_a_delta_gate. (5) the same with .get: killed by test_an_edited_arch_verdict.... (6) the `declared or` dropped: killed by both test_a_declared_break_holds... ids and 2 test_breaking.py tests. (7) any() over arch verdicts only: killed by latest_arch[said0,said2] and ledger_order. Every mutant also trips test_setup vendored drift (incidental). No surviving mutant.
Consumer: every new test calls evidence.gaps (the real consumer `wuwei evidence` reads), not breaking_gaps directly.
Differential probe at head vs main (efcd9e7) through evidence.gaps: STALE/FULL (HEAD yes, then OLD no): head [] vs main ANNOUNCE (the medium note). NOLINE: head [] vs main ANNOUNCE (unreachable, the low note).
Vendored copy: .claude/wuwei/cli/wuwei/evidence.py is byte-identical to cli/wuwei/evidence.py (cmp). Runtime cli/wuwei/*.py is 2977 lines, under 3,000; the diff adds +1 runtime line, inside the budget of 2.
Guard-parsing probes: N.A. (no change to guards.py, hook.py or any parser).
Flake check: no wall clock, network or shared file. Ledger rows append in order within a tmp root.
Simplicity: none. The `'breaking' in v` filter is needed to skip edited and imported stubs (mutant 4 shows it), and the gate filter is needed (mutant 3). Nothing in the diff can be deleted.
Confidence reason: all 7 mutants are killed by evidence.gaps tests, and acceptance 1 fails on main's rule. The one weakness is a design case the promise chose, not a test gap.

## Residual risk
A stale older-head arch verdict attested last can clear a break found at the PR head, and the merge goes ahead without an announcement. It is rare (it needs two arch seats on one item at different heads), but the spec's stated bound is wrong.
