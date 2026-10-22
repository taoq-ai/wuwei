Verdict: PASS
Gate: arch
Item: 1230
PR: taoq-ai/wuwei#1234
Head: 497f0d04b97eeb3a675afde1bbe8a8219874a63e
Confidence: high
Breaking: no (minor: a new optional Generated standards line; the PR title is now feat)

## Findings
- [low] charters/_common.md:43 blocks: no. "a delta of docs, generated files or at most 20 lines off risky paths" can be read as "off risky paths" qualifying only the 20 lines. Reordered with the same word count, "a delta off risky paths of docs, generated files or at most 20 lines" scopes all three, which fits the 2,250-word ceiling that agents/sentinel-arch.md is at. The runtime decides, not the seats, and design.md, evidence.md and reference.md spell out the risky, owner and contract exclusion, so the wording is clear enough to pass.
- [low] blocks: no. The PR Assumptions say the steward's 30-day pruning should skip a Generated line, but charters/steward.md rule 8 does not say so; a retro may still propose removing it. Carry this to the retro as a charter proposal.

## Probes
- Delta a626a8a..497f0d0 (git diff): the evidence.py `moved` filter keeps a file when RISKY, CONTRACT or owned(root, [p]) matches, whatever the Generated globs name. The docstring is shortened. The vendored copy is byte-identical (cmp). Docs, _common.md and the regenerated agents changed; specs and tests changed.
- closed: [high] evidence.py:346, a Generated glob carries a risky own-diff change, at 497f0d0. I re-ran my probe (tests/test_probe_arch.py) in a fresh git archive copy of 497f0d0: a 100-line own-diff change to src/auth/token.py now owes "a delta review by security" with no line, with src/auth/*, with *, with a 1999-01-01 line, and with the line inside a role line (6 passed, 5 rows plus the tree assert).
- closed: [low] _common.md silent on the Generated carry, at 497f0d0 ("docs, generated files or at most 20 lines").
- closed: [low] who writes the Generated line, at 497f0d0 (PR Assumptions: the owner only, no guard, and the line drops no risky, owner or contract path, so a stray line carries at most a plain-path change).
- closed: [low] fix-type commit for a new capability, at 497f0d0 (title "feat(evidence): ...").
- Still open as notes, not re-listed: the dual meaning of "generated" (the GENERATED regex versus the standards line); two extra cached compares per new head after a pass, plus patches in the cache. Neither moved in this delta.
- Mutants on the new clause, each in a fresh git archive of 497f0d0 with cli/ and .claude/ both patched, run one at a time with -k generated: dropping RISKY is killed by test_a_base_merge_that_changes_only_declared_generated_files_carries_the_passes (security delta expected); dropping CONTRACT is killed by the same test (arch delta expected); dropping owned is killed by the same test (security delta expected). 3 of 3 killed.
- tests/test_charters.py and tests/test_setup.py at 497f0d0: 225 passed (agents in sync with charters, word ceiling and runtime budget hold). agents/sentinel-arch.md is 2,250 words (wc -w), exactly at AGENT_WORDS = 2250.
- Runtime (cat cli/wuwei/*.py | wc -l): 3381 at 497f0d0, as at a626a8a; main is 3373, so +8. With 1211-confirm (+10) and 1222 (+0): 3391, under 3400.
- The route differential is not re-run this round. The delta does not touch guards.py; the builder reports 54 moves back on the generated host against a626a8a and only the 54 intended merge-host moves against main. My a626a8a run showed those 54 and nothing else.
- Confidence high: the blocking finding is closed by a probe I re-ran myself and by three killed mutants. No new host call and no new dependency in the delta.

## Residual risk
A PR hunk moved between identical three-line contexts still carries. A stray Generated line can still waive a quality re-read on plain paths, since only charters keep other sessions from writing standards.md.
