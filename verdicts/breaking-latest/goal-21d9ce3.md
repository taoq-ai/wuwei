Verdict: PASS
Gate: goal
Item: breaking-latest
PR: taoq-ai/wuwei#1135
Head: 21d9ce378a078a0364ba418fb17d039904ea5dee
Confidence: medium

## Findings
- [low] blocks: no. Issue #1129 says "newest head, or newest file"; the approved promise says ledger order, and the PR follows the promise (the promise governs, and a head or file-name rule would be weaker on stale seats). The residual (a stale arch seat at an older head attested last with Breaking: no clears a yes found at the PR head) is stated in the PR body and spec "How this fails 1"; it follows the promise and is a limit, not a regression. A later item may rank by head ancestry.
- [low] blocks: no. A non-arch verdict's Breaking field no longer counts (before: any gate). The promise says arch, and verdict.parse sets a breaking key on every parsed verdict (verdict.py:65), so the arch filter is needed; mutant removing it fails 3 tests.

## Probes
- Traced issue #1129 (test: old yes then new no gives no gap; reverse gives the gap), promise, 3 acceptance scenarios, spec, and the code at the head (evidence.py breaking_gaps). Each scenario maps to a test: said0 (clear), said1 (raise), test_a_declared_break_holds_though_every_arch_verdict_says_no (2 titles). The explain-back in the PR body and spec matches the promise.
- git archive copy of the head: `pytest -q` gives 1693 passed, 2 skipped; `pytest -q tests/test_evidence.py tests/test_breaking.py` gives 153 passed. Both match the PR body.
- Red claim: head tests copied onto main's code (efcd9e7): `pytest -q tests/test_evidence.py` gives 3 failed, 139 passed (said0, said2, test_ledger_order_decides_not_file_names_or_times). Matches the body.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` is 2977 at head and 2976 at main (+1, budget 2). Matches the body. `cmp` of cli/wuwei/evidence.py and .claude/wuwei/cli/wuwei/evidence.py: identical.
- Mutants run in fresh copies: arch[-1] to arch[0] fails 6 tests; dropping the 'breaking' in v filter fails the edited-verdict test; dropping the gate == arch filter fails 3 tests. None survive.
- Probe counts for a guard parser (generated/ran/holes): N.A.; the PR claims none and changes no guard or parser (diff touches evidence.py, its vendored copy, tests, specs only).
- Drift check: PR claims "no breaking change", "AUTH N.A.", "VAL N.A."; the diff has no guard, CLI, config or schema change. Holds.
- CI: test 3.13 was still running when launched; unmeasured here.

## Residual risk
Ledger-order rule lets a late stale older-head "no" quiet a real break; accepted in the promise and recorded. Assumption that attest rows follow gate completion order is untested against a real ledger.
