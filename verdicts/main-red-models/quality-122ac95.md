Verdict: PASS
Gate: quality
Item: main-red-models
PR: taoq-ai/wuwei#1159
Head: 122ac95874d17c63e7bb24420643215aa47d4f37
Confidence: high

## Findings
none

## Probes
- Confidence reason: two-line change, every claim reproduced in git archive copies at 73af8d4 and at the head.
- New assertion in tests/test_ledger.py (test_config_keeps_only_the_six_keys) at 73af8d4: fails, KeyError at cli/wuwei/ws.py:96 (data[key]); at the head: passes.
- Sweep test (tests/test_charters.py, board fills the cap) with test_charters.py and test_sync.py at 73af8d4: 40 failed, 144 passed; at the head: passes (the full run below).
- Full suite at the head (pytest -q): 2076 passed, 2 skipped, matching the builder.
- Vendored copy: cmp of cli/wuwei/ws.py and .claude/wuwei/cli/wuwei/ws.py at the head shows identical bytes.
- Mutant A (data.get(key, DEFAULTS[key]) back to data[key], both copies): killed by test_config_keeps_only_the_six_keys (KeyError, behavioural). Sweep tests do not fail on it (184 passed), so the ledger test is the one killer.
- Mutant B (models condition back to data[key], both copies): killed by test_config_keeps_only_the_six_keys (KeyError) and by the 40 sweep tests (behavioural).
- Mutant C (A on the vendored copy only): killed by test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from (drift test, not behaviour); the vendored copy has no behavioural test of its own, as before this PR.
- Simplicity: none. The .get(key, DEFAULTS[key]) and .get(key) are the smallest forms; the second copy is required by the vendored-drift test.

## Residual risk
Low. An extra data key outside DEFAULTS stays ignored, as before. The default-fallback guard is covered by one test only (the ledger one), but that test is a real round trip through raw_config.
