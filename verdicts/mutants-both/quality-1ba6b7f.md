Verdict: PASS
Gate: quality
Item: mutants-both
PR: taoq-ai/wuwei#1153
Head: 1ba6b7fa136081344459c4af500eafc4685f6dd2
Confidence: high

## Findings
- [low] AGENTS.md:46 blocks: no. The first Mutants line holds two rules (apply the mutant to both copies or deselect the drift test; a kill counts only when a behavioural test fails), and the five lines are not wrapped at 100 columns like the "Testing the guards" lines. A style note only.
- [low] tests/test_charters.py:296 blocks: no. The test asserts two substrings in prose, so it pins lines 1 of the list only; lines 2 to 5 have no test. It matches the neighbouring charter text tests, and the item is docs plus one text test, so it is a note.

## Probes
- git archive of 1ba6b7f into a scratch copy; full suite there: 1925 passed, 2 skipped (pytest -q, 71s). tests/test_charters.py: 90 passed.
- Red run of the new test in a copy: with the "## Mutants" section removed from AGENTS.md it fails (AssertionError at test_charters.py:296). Replacing only `.claude/wuwei/cli/wuwei/` fails it; replacing only the drift test name fails it. Each of its two asserts is load-bearing.
- Line correctness against the repository: `.claude/wuwei/cli/wuwei/` and `cli/wuwei/` both exist; `test_the_vendored_plugin_matches_the_tree_it_was_copied_from` exists at tests/test_setup.py:233; wall-clock guard tests exist (tests/test_guards.py:299-574, time.perf_counter and time.monotonic bounds), so line 2 is true; `gaps` and `excepted` (exception rulings keyed by PR ref and head) exist in cli/wuwei/evidence.py (lines 377, 434), so line 5 is true.
- No em dash, en dash or other non-ASCII character in AGENTS.md or tests/test_charters.py (python scan of code points above 127: none). No emoji.
- Contradiction check against "Testing the guards": none. The new list adds mutant-run rules and the evidence.py differential; it does not restate or reverse the route-corpus, parser-probe or normalisation lines. Line 4 (probe case folders under the seat's scratch folder) is consistent with the guards' probe lines and Boundaries 2.
- Mutant guards: none changed (no code guard in the diff).
- Probes (route corpus, parser probe): not applicable, no change to guards.py or hook.py.
- The builder said it did not run the test red first; I ran it red (above) and it fails for the right reason.
- Simplicity: none. Five short lines and a two-assert test; nothing to delete. Lines 3 and 5 are terse ("input lengths", "the PR the door reads") but readable to the seats that use them.

## Residual risk
Lines 2 to 5 are untested prose; a later edit could drop them unnoticed. Low harm, docs only.
