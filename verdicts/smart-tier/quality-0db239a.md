Verdict: PASS
Gate: quality
Item: smart-tier
PR: taoq-ai/wuwei#1240
Head: 0db239a4fc6531b8521c180e4c8816ea24f4d5e8
Confidence: medium
Breaking: no
Supersedes: smart-tier/quality-5ce0892.md

## Findings
none

## Probes
Delta 5ce0892..0db239a read: cli/wuwei/evidence.py (+2, the arch fix keeping the unraised gates under an error-budget raise, mirrored in .claude/wuwei), tests/test_smart.py (+55). Run in a git archive copy in my scratch folder.
Tests at the head: tests/test_smart.py + tests/test_charters.py + tests/test_setup.py (vendored drift) 297 passed; tests/test_evidence.py + tests/test_guards.py 2323 passed. Full suite not run.
Mutants re-run on the new head, one at a time (pytest -x tests/test_smart.py), 30 on cli/wuwei/evidence.py: each of the nine decision-node class drops (IfExp, For, AsyncFor, While, ExceptHandler, Assert, BoolOp, comprehension, match_case), each guard-word drop or narrowing (denied, refuse/refused/refuses, ask, allow/allowed/allows, waive*, excepted/exception(s), permissionDecision, PROCESS, DUTY, case-insensitivity of deny), the RecursionError catch removed, and the arch fix reversed (guard `if spent['raised']` off; the unraised tier replaced by 'standard'): all 30 killed by test_smart.py (test_every_decision_node_counts_toward_the_complexity_rise, test_a_clear_classification_on_a_guard_change_still_owes_arch rows, test_a_head_too_deep_to_parse_counts_as_a_rise, test_an_error_budget_overrun_keeps_every_gate_the_unraised_item_owed).
closed: DECIDE node classes untested at 5ce0892, closed at 0db239a.
closed: guard-word list untested at 5ce0892, closed at 0db239a.
closed: RecursionError catch untested at 5ce0892, closed at 0db239a.
The arch fix reads correctly: under a raised budget the gates are the union of the raised tier's full set and what the item's own tier needed (REQUIRED['full'] order); a smart item in doubt keeps goal (new test), and a full item is untouched (no raise).
Route differential: the delta changes only gates_for under a raised error budget, which the five route-differential hosts do not exercise (no merged PRs in their fake host); the 5ce0892 result stands (corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, 60 moved: guard 57, rise 3, all smart items, matching specs/smart-tier/route_diff.txt). I did not re-run the differential at 0db239a.
Non-blocking notes from 5ce0892 stay open: files with no added lines unmeasured rule untested; the rose cache key untested; the base side of the create door untested; pure renames with no patch; the board's base sha (pr base) against the create door's merge base differ.
Simplicity: none to delete. The test_a_head_too_deep_to_parse test patches the global ast.parse, which also hits pytest's own assertion rewriting on a failure, so a failing run prints a confusing traceback; the passing run is unaffected.

## Residual risk
The guard-word list still misses a guard change that names none of its words (the spec's own How this fails 1); the route differential was not re-run on the delta.
