Verdict: PASS
Gate: arch
Item: free-lines-4
PR: taoq-ai/wuwei#1112
Head: 725f63d85313da6bf5e71bd53b2869f6c0ae5295
Confidence: high
Breaking: no

## Findings
none

## Probes
- Previous FIX at 50f66d8 (OPS dropped `\|\|`, so `||&>` split differently) is closed: guards.py:17 restores `\|\|` and drops only `;;`. The comment now says only `;;` splits the same, and tests/test_guards.py adds `x||&>y` -> x, ||, &>, y. The FR-005 note is closed: the spec says three call sites.
- Merge of main a5edd81: `git diff --stat 9d6701e a5edd81 -- cli .claude/wuwei/cli` is empty, so the merge brings charters, agents, specs and tests only, and 9d6701e stays the right runtime base for the differential.
- p.py (acceptance-3 grid of 82,944, plus every run of 1-5 characters over `();<>|&`, glued and spaced; 122,158 segments outputs) on 9d6701e vs 725f63d: byte-identical. Since `\|\|` is back, the only OPS difference from base is `;;`, so dropping `;;` alone is safe over that space.
- d.py (1,372 commands built around `||&>` runs and door words, segments plus guards.bash decision) on 9d6701e vs 725f63d: byte-identical.
- Mutant: removing `\|\|` from OPS in a fresh git-archive copy of the head fails test_a_punctuation_run_splits_into_the_longest_operators_first[x||&>y]. The other failure, test_the_vendored_plugin_matches_the_tree, fails only because the edit touched one copy.
- `cat cli/wuwei/*.py | wc -l`: 2976 (23 freed from 2999). `diff -r` cli/wuwei vs .claude/wuwei/cli/wuwei: identical. Suite in a git-archive copy: 1203 passed, 2 skipped.
- Headroom: 3000 - 2976 = 24. Queued shell-stdin 1 + records 12 + gh-args 3 + merge-evidence 4 = 20, which leaves 4.
- Contracts: the fix round changes only OPS, two comments and a test. No CLI output, message or exit code changed (LEDGER_DENIED holds the base text). The 3.11 floor holds: every module parses with ast feature_version (3, 8).
- Line length: guards.py lines 28, 51, 199 and 379 exceed 150 characters, but all were already there at base (base had 5); no rewritten line goes over 150.
- Confidence high: two independent differential probes are byte-identical to base, and the new test kills the mutant that caused the previous finding.

## Residual risk
Equivalence is measured over punctuation runs up to length 5 and the acceptance grid. Longer runs are unmeasured, but no OPS alternative is longer than 3 characters.
