Verdict: PASS
Gate: quality
Item: free-lines-5
PR: taoq-ai/wuwei#1123
Head: a287d4458e68ee0cafb94c0e70246718a8892ed0
Confidence: medium

## Findings
none

## Probes
- Differential probe: ran the builder's test_zz_probe.py on fresh git archive copies of main d1c3d79 and the head. Both passed (10 tests) and the two output files are byte-identical (cmp, 8,782,452 bytes each, also identical to the builder's head.json). guards.bash covered 19,386 commands (16,932 generated, at least 5,000 required), plus verdict.parse 8,001 inputs, hook 900 each, 40 upgrade cases and 60 report rows.
- Suite on the head archive: 1500 passed, 2 skipped (pytest -q). Runtime lines: cat cli/wuwei/*.py is 2,996 on base and 2,975 on head, so 21 freed (promise: 12 or more).
- Wrong-rewrite mutants on the head copy (suite with -x, then the probe against base.json). All are caught by the existing suite and by the probe: upgrade count off by one (len(known) - before - 1), upgrade `>` changed to `>=`, report learning without the `approved` check, agents.stale `or` changed to `and`, board unreadable path reading `mine[:1]`, board cache key `'prs-' + repo`, board.rows dropping the cache, hook `is None` flipped, plan.mark `is None` flipped, setup.doctor wrong directory. One mutant (evidence.verdicts path default '' changed to 'x') gave identical probe output: both defaults raise OSError on read, so it is equivalent for that input. The suite still flagged it, which shows the suite is the stronger net there.
- Vendored copy: git diff d1c3d79..a287d44 --stat lists the same ten modules under .claude/wuwei/cli/wuwei/ and cli/wuwei/ with equal line counts. The diff of the two trees at the head shows only files that exist in one tree (plugin metadata, charters), no content differences in the shared modules.
- Timing: ran the builder's timing.py at 125 KB and 500 KB on both trees, best of 5 alternating runs. The worst head/base ratio is 1.18 (plan.mark 125 KB, a rewrite that adds no work, so this is noise); the builder's best-of-4 worst is 1.12. A first pair of runs showed outliers up to 2.2x in short shapes; they vanished on repeat. Under the 20 percent bound, but the margin on the noisiest shape is thin.
- Readability: each rewrite is a plain `if (x := f()) is None:` guard, a single comprehension, or an inlined expression. No `;` joins and no squeezed lines were added (grep of the added lines), and no em dashes or emojis in the diff or specs/free-lines-5. The agents.stale comprehension computes `base / f'{role}.md'` twice (a pure path build, so no change in order of growth). The board `mine` reuse turns a generator into a list that already existed.
- upgrade.items: len(known) - before equals the old `moved` count because both loops add only ids not already in known (the guards `not in known` precede each `known.add`), so each import adds exactly one id. Duplicate ids inside one state or lead file are covered by the probe's random names (A-0, a-1, B-1, b-1 ...).
- New tests: none added. For a pure refactor with no behaviour change this is acceptable: the existing 1500-test suite plus the differential probe, which is not committed, pin the behaviour. The probe and timing scripts remain uncommitted in the builder scratchpad, so a later item cannot re-run them from the repo (see Notes).
- Spec: specs/free-lines-5 has spec.md, plan.md, tasks.md, analysis.md and checklists/requirements.md.
- Simplicity: nothing further to delete. The `before = len(known)` line replaces the `moved` counter and its two increments, and `evidence._cached` replaces the hand-written get/put in board.rows. Nothing here is trust-boundary validation.

## Residual risk
The equivalence rests on a probe that is not in the repository and on randomised inputs. A rewrite on a path that neither the suite nor the probe reaches (for example the hook SubagentStop `ended` branch with unusual payloads) is unproven, though each rewrite there is a mechanical walrus form. Timing margin on noisy shapes is small.

## Notes
The probe and timing scripts are not committed. If later items (gh-args, scratch-remotes, push-refspecs) need the same evidence, consider committing them under tests/ or scripts/. Not a block: the promise does not require it.
