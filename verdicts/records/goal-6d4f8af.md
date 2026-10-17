Verdict: PASS
Gate: goal
Item: records
PR: taoq-ai/wuwei#1116
Head: 6d4f8af518d0e253a9b097fce9fbaf65d992e90f
Confidence: high

## Findings
- [low] blocks: no. SECURITY.md is changed but is not in the promise's Files list. The change rewrites the ledger paragraph and the known-shapes list so they match the new rule. That keeps the docs honest rather than adding scope; the spec's FR-005 names it. Note for the retro.
- [low] cli/wuwei/guards.py:328 blocks: no. Clauses (3) and (4) are applied more widely than the promise says, and the spec's Clarifications record each widening. find reads every argument, not only the start path, so `find /tmp -name .wuwei -delete` is refused. A redirect after cd counts as a write. A session whose cwd is inside .wuwei refuses every writer, `rm /tmp/x` too. Each widening refuses more, never less.
- [low] blocks: no. `cp .wuwei/cache/c.json /tmp/x` (cp reading a cache file) is refused. That follows the letter of clause (2), because the source is a writer argument other than rm, and main already did the same for the ledger. But spec "How this fails" 2 names this exact command as the over-reach to avoid, and its Measured line does not cover it. The spec text and the behaviour disagree on this one example.

## Probes
- Trees: both made with git archive into scratchpad/goal-records/{head,main}. Head 6d4f8af5; main 5fa32fe4, which is the merge-base.
- Acceptance 1 (scripts/acc.py): real bash -c in a fresh folder holding .wuwei/ledger/a.jsonl and .wuwei/cache/c.json. git clean -fdx ran in a git init repo whose .gitignore lists .wuwei/. On both trees all 7 commands changed the ledger row or the cache value. guards.bash refused all 7 at head and passed all 7 on main.
- Acceptance 2: re-ran scratchpad/builder-records/probe/recprobe.py from a copy. Head: 462 generated, 288 changed the records under bash, 0 holes, 164 refused without changing them. Main: 462 generated, 288 changed, 234 holes.
- Acceptance 3: the echo into .wuwei/cache/default-taoq-ai__wuwei.json is denied at head, and the reason names ".wuwei/cache" and "feed gate inputs (ci-, review-, default-branch)". pre_tool denies Write on .wuwei/cache/ci-x.json, relative and absolute. Edit and MultiEdit on a cache path are denied too. Main passes all of these.
- Acceptance 4: all 9 commands pass at head. Extra passes at head: rm .wuwei/cache/c.json, find .wuwei -name "*.json" -print, git clean -fdx build/, git clean -n, pushd .wuwei && cat plan.json, echo x > .wuwei/plan.json (plan.json is Outside), rm -rf ?wuwei/ledger and rm -rf */ledger (sh globs skip the leading dot).
- Clauses (1)-(5) at head: refused are cd/pushd + truncate/rm/redirect, find -exec/-execdir, find . -path ./.wuwei/ledger -delete, git clean -fdX/-dfx/-f -x -d/-fdx ./-fdx .wuwei, git -C .wuwei clean -fdx build, and cp/tee/dd of=/mv/python3 into the cache. All of these pass on main.
- Route corpus (probe/test_zz_dump_routes.py, head's routes.json loaded in both trees): 184 rows. No row that exists on main changed its verdict. The only reason change is the shared LEDGER_DENIED text, which now also names the cache, on 9 ledger rows that already refused. 8 new rows move pass to refusal, and they are acceptance 1 and 3. At head every row matches its recorded verdict.
- Suite at head: pytest -q gives 1341 passed, 2 skipped. Runtime lines (cat cli/wuwei/*.py | wc -l): 2980 on main, 2995 at head. That is +15, within the budget of 18 and the 3,000-line cap.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (diff).
- Spec: specs/records/spec.md restates promise clauses (1)-(5) and the 4 acceptance lines, and they match plan.json. Outside and the Assumptions are carried over. The doors.md and design.md door lines match the behaviour.
- Confidence reason: every acceptance line was reproduced independently on both trees by real execution, and the corpus shows no unintended move.

## Residual risk
The guard is a tripwire. SECURITY.md lists shapes it still does not read: dotglob, symlinks, xargs, cd to a variable. Over-refusals after cd into .wuwei, or with the cwd inside .wuwei, may surprise a seat, though the refusal text gives the remedy.
