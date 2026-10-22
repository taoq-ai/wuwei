Verdict: PASS
Gate: security
Item: smart-tier
PR: taoq-ai/wuwei#1240
Head: 713d3906d80893adef8a0dffae40e39a242ec76c
Confidence: medium
Supersedes: smart-tier/security-5ce0892.md

## Findings
none

## Probes
- closed: error-budget raise drops goal for an in-doubt smart item (evidence.py:343) at 2a903d1. gates_for now joins the raised set with what needed() owes at the unraised tier (evidence.py:349-350).
- Budget raise probe at 713d390, host stubbed, budget stubbed calm and raised. 96 rows: tiers light, smart, standard and full x domains clear and unclassified x doubt x src/app.py, src/auth.py and docs/a.md x a plain patch and a guard-word patch. 0 rows where the raised set lacks a calm gate, and 0 code rows below the raised tier's set.
- Mutant: drop the raise join (`if False:`) in fresh git archive copies, cli and vendored both. Killed by test_an_error_budget_overrun_keeps_every_gate_the_unraised_item_owed.
- Narrowed guard-word signal (713d390), lowering probe: smart at head against main's standard over 1 to 2 paths from 13 classes x 10 patches x 2 sizes x 5 domains x doubt x rise. The 10 patches cover: none, empty, plain, a changed deny line, a deny line in context only, deny in a hunk header, PROCESS in context, Exception, EXCEPTIONS, and a deny line removed. Light, standard and full at head equal main. 41,860 cases, 0 holes.
- changed() spot reads:
  - Guard words that count: deny in a hunk header, PROCESS in context, lower-case exceptions on a changed line.
  - Words that no longer count: deny or ask in a context line only, Exception, EXCEPTIONS.
  - The narrowing removes only arch that smart adds above the standard rows. Standard never read guard words.
- Mutant: drop the NAMED context read in changed(). Killed by test_a_clear_classification_on_a_guard_change_still_owes_arch.
- Route differential at 713d390 (own script, 9 code hosts, head tests folder):
  - routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1.
  - 2592 cases. 120 moved against main, all toward more gates, as in round 1. 0 moved against 5ce0892.
- Targeted tests at 713d390: test_smart.py plus test_guards.py -k "smart or route or vendored", 455 passed. cli/wuwei and .claude/wuwei/cli/wuwei are identical (diff -r).
- Scanner: unmeasured. The repository's CI runs no secret, dependency or static scanner, and this delta touches no dependency or workflow.
- Confidence medium: the closed finding and the narrowed signal are probed by generated cases and killed mutants. The round-1 notes (delta carry, base.sha at the merge door) remain unrun readings.

## Residual risk
The round-1 notes stand as notes. With 713d390, a guard change whose words sit only in unchanged context lines (other than PROCESS, DUTY, permissionDecision) no longer adds arch for a clear or complicated smart item. Spec How this fails 1 names this, and it stays at or above standard.
