Verdict: PASS
Gate: goal
Item: push-refspecs
PR: taoq-ai/wuwei#1155
Head: b16d799d3d522d11111fe796b483258e57a57968
Confidence: high

## Findings
- [low] blocks: no. The promise says a glob is refused "unless the refspec's source names no default-branch ref"; the head refuses a glob on its destination alone, whatever its source. The PR body records this under Assumptions with the reason (a local `f/main` carried by `refs/heads/f/*:refs/heads/*` moved main) and the cost (360 probe globs over-refused, git exit 0, main untouched), and says what would overturn it. A recorded, safe-side reading of the promise, so a note, not a drift. The owner may rule on it at review.

## Probes
- Trace: goal G-2 (bugs found running WUWEI on itself, fixed before features) -> item push-refspecs (a second live push-door bypass on main d1c3d79) -> promise (1) destination expansion, (2) `:`/--all/--branches/glob refused, (3) existing refusals keep their text -> delivered `git_push` in cli/wuwei/guards.py (and the vendored .claude/wuwei copy, identical by diff) plus docs/design.md and docs/site/concepts/doors.md lines. The change serves G-2 and adds nothing outside the promise except the `@` and `--tags`-alone fixes the probe found, both inside "the way git does" and acceptance 3.
- Acceptance 1: `test_a_refspec_that_moves_main_under_real_git_meets_the_push_door` runs real git 2.43.0 on a scratch bare remote for 15 commands including the four named, asserts main moved, then moves guards.TEMP off the remote and asserts the push door refuses. Passed in my full run of the archive at the head: `pytest -q` 1973 passed, 2 skipped.
- Acceptance 2: re-ran `python3 -I specs/push-refspecs/probe.py` on a `git archive` copy of the head: generated 6398, ran git push 6370, holes 0, moved main 1037, guard passed 3178, refused-but-main-unmoved 2183 (926 with git exit 0). Equals the PR body figures. The probe reads against a non-scratch remote and counts a hole only when the guard passes and main moved or vanished.
- Acceptance 3: `test_a_refspec_that_cannot_reach_main_passes_the_push_door` runs `feature`, `feature:feature`, `--tags origin` and `refs/heads/f/*:refs/heads/f/*` (and three more) under real git (main unchanged) and asserts the guard returns None. Green.
- Body claims read at the head: WUWEI-Item: push-refspecs present; promise in the builder's words present and matches the item; glob assumption and git 2.43 rules recorded; residuals (a) checkout main then push HEAD, (b) local symbolic ref, (c) case-insensitive store, config-steered pushes named. Runtime lines: `cat cli/wuwei/*.py | wc -l` is 3027 at the head and 3026 at 5fe83477 (+1, inside budget +4, ceiling 6, and under the 3,400 cap). routes.json sha256 at head 3c80e7c1... and at 5fe83477 9e099867..., both as the body states.
- Rollback line present. No breaking change to an outward contract.
- Drift check, missing: no promised outcome is absent (docs lines, routes.json rows, tests, vendored copy all in the diff). Drift check, extra: the `--mirr`/`--m` prefix reading and `@` are claims no acceptance line asked for, but both are named in the PR body and follow from reading options "the way git does".
- Mutants and gates other than goal: not run by me (outside the goal gate).

## Residual risk
Residuals (a) to (c) and config-steered pushes sit outside the item and are named in the PR body. The glob over-refusal is a deliberate safe-side reading awaiting the owner's view.
