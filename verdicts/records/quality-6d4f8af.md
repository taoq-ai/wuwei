Verdict: PASS
Gate: quality
Item: records
PR: taoq-ai/wuwei#1116
Head: 6d4f8af518d0e253a9b097fce9fbaf65d992e90f
Confidence: medium
Breaking: no

## Findings
- [low] tests/test_guards.py blocks: no. Untested: the end of a brace range. Reversing `ord(max(m[2], m[3])) + 1` to drop the last letter survives all of tests/test_guards.py; the tests use {k..m} and {v..x}, whose ends are not the matching letter. A differential against head shows a difference on `.wuwei/{k..l}edger`. Add `{k..l}`.
- [low] tests/test_guards.py blocks: no. Untested: a ledger spelling in the second brace alternative. Keeping only the first alternative (`m[1].split(',')[:1]`) survives. Add `.wuwei/{x,ledger}`.
- [low] tests/test_guards.py blocks: no. Untested: `find ... -fprint`. Dropping '-fprint' from FIND survives (-fprintf and -fls stay covered). Add `find . -fprint .wuwei/ledger/a.jsonl`.
- [low] cli/wuwei/guards.py blocks: no. Untested: the `'.'` filter in `records` (`if p not in ('', '.')`). Dropping it survives; the generated differential found 241 of 89,817 differences, for example `.*=.`, so it is not dead code. Add a test with `=./` in a path.
- [low] cli/wuwei/guards.py blocks: no. Untested: `normpath(v)` in the git clean pathspec check. Without it `git clean -fdx x/../.wuwei` would pass; the head refuses it. Add that row.
- [low] cli/wuwei/guards.py blocks: no. `fnmatchcase('.wuwei', p.lower())` survives. A pattern such as `.WUWEI` would then be refused, an over-refusal only, so the harm is nil. Note only.
- [low] cli/wuwei/guards.py blocks: no. Readability. `records` and the rewritten loop in `bash` pack several rules into long lines, with a brace regex, a 2^n cap, a POSIX class rewrite and an `inside` flag carrying three rules. The comments help; a named `_CAP` and splitting the `any(...)` of the deny test would read better. The line budget (2,995 of 3,000) makes that costly, so note only.
- [low] specs/records/spec.md blocks: no. The spec says `hole 44 red` in tasks.md T007; on main with the head tests I count 56 failing test ids. The ids are parametrized rows, so this is a count of a different unit, not a mismatch in substance.

## Probes
- Suite at head (git archive into scratch, `pytest -q`): 1341 passed, 2 skipped. Matches the expected count.
- Red on main: head tests/test_guards.py and tests/fixtures/routes.json copied onto an archive of 5fa32fe: 56 failed, 878 passed. This includes the seven real-bash acceptance rows, the cache refusal, the brace cap and the cwd-inside-records tests.
- Runtime: `wc -l cli/wuwei/*.py` total 2,995 (at most 3,000).
- Vendored copy: `cmp` of cli/wuwei/guards.py and .claude/wuwei/cli/wuwei/guards.py shows no difference, both in the worktree and in git show at 6d4f8af.
- No emojis and no em dashes: grep for U+2014 bytes and 4-byte emoji bytes over cli, specs, tests/test_guards.py, docs/design.md, SECURITY.md, doors.md found none.
- Mutants (47 applied, each in a fresh copy, pytest -x tests/test_guards.py): 40 killed, 2 killed by timeout (brace cap raised to 99 or removed, the 2^n expansion), 5 survive (the findings above, re-run once in a fresh copy: same result). Killed by name: leading-dot rule, glob case, brace cap 0 and 8, [^x], POSIX class, normpath `..` collapse, `=` split, below=None, last-part only, the ledger.jsonl and cache targets, the rm exception both ways, redirect, edit and writer-argument checks, find -delete / -exec / -execdir and the rule itself, sed -i, python, cwd-inside, cd and pushd, the inside-writer and inside-redirect rules with the /dev exemption, git clean x and X, the pathspec exception (dropped, always allowed, class narrowed), `-C` and cd in clean.
- Differential probe (generated 89,000+ path x below pairs per mutant, head against mutant): innermost-brace regex mutant 0 differences (equivalent on this input class); dot filter 241 differences; lower 11,969 differences.
- Direct run of guards.bash at head: `git clean -fdx x/../.wuwei`, `find . -fprint .wuwei/ledger/a.jsonl`, `rm -rf .wuwei/{x,ledger}` and `rm -rf .wuwei/{k..l}edger` are denied; `git clean -fdx build/` passes.
- Spec completeness: specs/records has spec.md, plan.md, tasks.md, analysis.md and checklists/requirements.md; the spec carries the promise, acceptance, clarifications, How this fails, Breaking with migration, Assumptions and Rollback.
- Not run: the builder's generated bash probe (462 commands) and a route corpus dump; I read their reported numbers from the spec only.
- Confidence is medium: the suite and mutants are measured, the generated bash probe is not re-run.
- Simplicity: none to delete. The `'.'` filter looked redundant after normpath but the differential shows it is not. The `FIND` extras (-fprint, -fprintf, -fls) and the cap are guards. The innermost-brace pattern `[^{}]*,[^{}]*` could be loosened to `[^,]*,[^{}]*` with 0 observed differences, but it is the safer text; keep.

## Residual risk
Five guard branches pass the suite when reversed, so a later edit could regress them unseen; the head itself is correct in every direct run. Shell shapes the spec lists as known (dotglob, symlinks, cd "$VAR", xargs) stay open by design.
