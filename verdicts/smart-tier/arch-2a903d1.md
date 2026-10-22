Verdict: PASS
Gate: arch
Item: smart-tier
PR: taoq-ai/wuwei
Head: 2a903d1461cb8424da6fcc79768c6b32f6555e11
Confidence: high
Breaking: no (minor: a new tier value, new optional flags --domain and --in-doubt, and a new default for an optional flag whose default the public API never documented)
Supersedes: smart-tier/arch-5ce0892.md

## Findings
- [low] blocks: no. charters/planner.md:110 and docs/site/concepts/models.md:15,27 have no smart row for model and effort, so a smart complex item gets the default seats (carried from arch-5ce0892).
- [low] blocks: no. skills/wuwei-run/SKILL.md:37 still shows `--tier light|standard|full` without smart or --domain (carried).
- [low] cli/wuwei/evidence.py:63 blocks: no. WAIVE hard-codes this repository's guard names (PROCESS, DUTY, permissionDecision) in the generic evidence reader (carried).
- [low] blocks: no. Mixed versions: an older WUWEI reading a synced plan that has smart items gives quality only, and raises KeyError at RAISE[tier] under an overrun budget. A release note should ask every clone to upgrade together (carried).
- [low] blocks: no. Runtime is +30 lines against the brief's +20 (3,426 at head). The constitution's 3,600 cap holds (carried, and 2 lines larger).

## Probes
- closed: error-budget raise drops the goal gate of a smart in-doubt item (evidence.py:48) at 2a903d1. gates_for (evidence.py:344-345) now adds the unraised tier's needed() set to the raised set, in REQUIRED['full'] order.
- The delta 5ce0892..2a903d1 is ancestry-checked (`git merge-base --is-ancestor`). It touches 3 files, +14: evidence.py +2, its vendored copy +2, tests/test_smart.py +10.
- Raise probe in a git archive copy of 2a903d1: smart in doubt unraised gives "quality, goal"; raised gives "arch, quality, security, goal (tier raised to standard ...)"; standard raised gives "arch, quality, security, goal (tier raised to full ...)", unchanged from before. The union cannot drop a gate: the raised set is a superset of REQUIRED[RAISE[tier]], and needed() at the item's own tier only adds. Light, standard and full: needed() at the unraised tier is a subset of the raised REQUIRED set, so they are unchanged. A raise with no item reads tier standard, so it is unchanged too.
- Mutant: `if spent['raised']` replaced by `if False` in both cli/wuwei and .claude/wuwei copies. test_an_error_budget_overrun_keeps_every_gate_the_unraised_item_owed fails (1 failed, 35 passed): killed.
- Tests at 2a903d1 (copy): test_smart.py with test_charters.py gave 225 passed; test_evidence.py gave 372 passed.
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference. Runtime: `cat cli/wuwei/*.py | wc -l` gives 3,426 (cap 3,600). No charter or agent changed in the delta.
- Cost: under a raise, a smart non-complex, non-risky item now calls the cached rose() (two contents reads per changed .py file, kept a day per base and head). The cost is the same as the unraised path.
- Confidence is high: the delta is two lines, probed directly and mutant-killed.

## Residual risk
The guard-word signal is still lexical: a guard change that names none of the words reads as no guard change outside owner paths. The steward should watch smart clear and complicated items for arch escapes.
