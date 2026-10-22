Verdict: PASS
Gate: security
Item: 1230
PR: taoq-ai/wuwei#1234
Head: 497f0d04b97eeb3a675afde1bbe8a8219874a63e
Confidence: medium

## Findings
- [low] cli/wuwei/evidence.py:345 blocks: no. Any session can still write .wuwei/standards.md (pre_tool guards only the ledger and cache). A `Generated` glob such as `*.py` can therefore still waive the quality delta re-read on plain code off risky, owner and contract paths, with no owner ruling and no date check. Note for the retro: let the line count only when an owner ruling records it.
- [low] cli/wuwei/evidence.py:342 blocks: no. Moved hunks between identical contexts, rename-source swaps, and mode or symlink changes stay invisible to the patch-text key. The PR body now names them as known limits; unchanged from a626a8a.
- [low] blocks: no. charters/_common.md says "a delta of docs, generated files or at most 20 lines off risky paths carries the passes". It does not say that generated files on risky, owner or contract paths still count, though the code and docs/design.md do.

## Probes
- closed: Generated glob waives risky paths (evidence.py:346) at 497f0d0. In a fresh git archive copy of 497f0d0 I re-ran my test_sec_probe.py. The 300-line src/session.py change under `*`, `src/*`, `*.py` and `  * Generated (ACME/APP, 1999-99-99): src/sess*` now gives "no gate passed at head aaaaaaa (a delta review by security)" in 4 of 4 cases (it was 0 of 4 at a626a8a). My old "waives" assertions fail as expected. The compare error still reads "evidence unreadable" (fails closed). My missing-patch control on a plain 1-line file carries, as it did at a626a8a: a quality gate on a delta of 20 lines or fewer is below the threshold, so that is expected.
- Mutants on the new terms, each in a fresh copy applied to both cli trees, run with `pytest tests/test_evidence.py -k generated`. Dropping `RISKY.search(p)` gave 4 failed; dropping `CONTRACT.search(p)` gave 3 failed; dropping `owned(root, [p])` gave 4 failed. All are killed by test_a_generated_glob_never_drops_a_risky_owner_or_contract_path.
- Route differential, re-run with the head's route_diff.py, main fbf187b vs 497f0d0 (tests from the head): corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at both; 288 routes, 1152 cases, 54 moved.
  - By host: gap 0, merge 54, fix 0, generated 0 moved.
  - Every moved route is in the merge host and goes from "security delta owed" to "no gap", as intended. This output matches the first section of the builder's route_diff.txt.
- Delta read: the only runtime change is the `moved` filter at evidence.py:345-346, mirrored in .claude/wuwei. The rest of the delta is docs, charters and agents rebuilt from charters, spec artifacts and tests. No dependency or workflow changes.
- Confidence medium: GitHub's patch omission, rename pairing and base.sha freshness are still reasoned from the API docs and local git, not run against the live API.

## Residual risk
Gate waivers through standards.md on plain code paths still rest on seats keeping to their charter. The limits of a patch-text key (moved hunks, renames, mode changes) remain, and the PR names them.
