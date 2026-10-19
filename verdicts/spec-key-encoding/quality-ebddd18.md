Verdict: PASS
Gate: quality
Item: spec-key-encoding
PR: taoq-ai/wuwei#1174
Head: ebddd18ccdb875b1fdb01cd038524abb57957cf1
Confidence: high
Breaking: no

## Findings
- [low] blocks: no. The 32-hex cut (from 16) has no test and needs none. Reversing it to 16 hex passes both new tests and the suite at the head. No small fixture can hit a 64-bit versus 128-bit collision, so a behavioural test would need a forged digest. It is a margin, not a guard. Untested, not a defect.
- [low] blocks: no. Both mutants of the vendored copy (.claude/wuwei/cli/wuwei/evidence.py) survive the two new behavioural tests, because tests/conftest.py puts only `cli/` on sys.path. The existing drift test `tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from` fails on each of them, so a vendored copy that lags cannot merge. That kill is a byte comparison, not behaviour. Existing design, noted only.
- [low] blocks: no. `ws.version()` is now called in `gaps` outside the `except (GhError, KeyError, TypeError)` clause. A missing plugin.json would raise an OSError there. `__main__` already calls `ws.version()` on every CLI start, so the file must exist whenever this code runs. No reachable failure.

## Probes
- Archive copies of base d4a803f3 and head ebddd18 in my scratch folder (`git archive`). Tests overlaid from the head onto the base copy.
- Fail-before: at d4a803f3 with the head's tests/test_evidence.py, `pytest -q tests/test_evidence.py -k "newline or upgrade"` gives 2 failed. Both fail on `assert found is not None`; the door returned None where it should deny. They fail for the reason the item names (shared key, stale cross-version result), not an error. At the head: 2 passed.
- Exact outcomes: the newline test asserts `merge_door(...) is None` on the first read and, after the retarget, a deny whose reason contains 'specs/8-stacked/tasks.md has 1 unchecked item'. It matches the item's acceptance scenario. The upgrade test asserts a clean read, then a deny containing 'tasks.md has 1 unchecked item' after a version bump. Both assert a decision and its reason, with no wall-clock or ordering dependence. The reason strings are the existing spec-gap text and would break only if that text changed.
- Mutants, each applied alone in a fresh copy of the head, run with the two new tests:
  - restore `'\n'.join` in cli/wuwei/evidence.py: killed by test_a_path_holding_a_newline_does_not_share_a_spec_key_with_two_paths (1 failed, 1 passed).
  - same mutant in .claude/wuwei/cli/wuwei/evidence.py: survives the behavioural tests (2 passed), killed only by the byte-drift test (see the note above).
  - drop `ws.version()` from the key in cli/wuwei/evidence.py: killed by test_a_wuwei_upgrade_reads_the_spec_again (1 failed, 1 passed).
  - same mutant in the vendored copy: survives the behavioural tests, killed only by the drift test.
  - 16 hex in cli/wuwei/evidence.py and in the vendored copy: both survive (2 passed). The drift test kills the vendored one. See the first finding.
  - The reversals were applied with sed; I printed the diff of each against the head to confirm exactly one line changed.
- Suite: `/root/.local/bin/pytest -q` at the head gives 2153 passed, 2 skipped (109 s), including tests/test_setup.py drift and tests/test_status_perf.py.
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` is empty at the head, and the two evidence.py diffs against base are byte-identical.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` in the head copy gives 3208 (builder's figure holds; the cap is 3,400). The change is 3 lines out and 3 in, so 3208 at base too.
- Perf: `ws.version()` reads and parses plugin.json in 36 us per call (timeit, 20,000 calls). It runs once per non-light PR whose evidence is computed, so 18 PRs cost about 0.7 ms. That is negligible against the 50 ms-per-call gh stub the perf test uses and against real gh latency. The cost is unmeasured on a real board, only on this timeit and the green perf test.
- Cache effect: the key now includes the version. A newer version rereads once, and old-version keys in the same 24-hour cache file are ignored and expire with the file. Nothing grows without bound.
- Standards lines: nothing in this diff touches guard parsing (guards.py and hook.py are unchanged), so the generated combinatorial probe and the routes differential do not apply. Unmeasured, not clean.
- Simplicity: none. The json.dumps replaces the join one for one. `ws.version()` is the existing helper. The longer comment line could be shortened, but it is not worth a round.

## Residual risk
The fix is behaviourally covered only through cli/; the vendored copy depends on the byte-drift test. The 32-hex margin is untested by design.
