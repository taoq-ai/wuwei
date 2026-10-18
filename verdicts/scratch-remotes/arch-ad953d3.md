Verdict: PASS
Gate: arch
Item: scratch-remotes
PR: taoq-ai/wuwei#1141
Head: ad953d3ba88a0a622857269410be4993497f5577
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:167 blocks: no. Closes 6a5d00d finding 1 (requirement versus output, spec Clarification "force pushes and deletes to a scratch remote pass"). `+` is now in the word class and `(` is still out, so no extglob `+(..)` or `@(..)` can form. At the head, `git push origin +main`, `git push origin +HEAD:main` and `git push ../r.git +main` to a scratch bare remote pass. `git push gh +main` (GitHub), `git push /home/user/wuwei/.git +main` and `git push origin +(main)` are still refused.
- [low] docs/design.md:147 blocks: no. Closes 6a5d00d finding 2 (conformance with the written design). design.md and docs/site/concepts/doors.md:11 each carry one clause that names the scratch exception and points to SECURITY.md for the rule. This is docs only, so it carries the code passes.
- [low] cli/wuwei/guards.py:52 blocks: no. Closes the 6a5d00d hot-path note. TEMP is `()` at import, and gettempdir() is read only inside scratch() (line 178). After importing wuwei.hook and wuwei.guards, tempfile.tempdir is still None, so a hook makes no probe file.
- [low] blocks: no. Design of the new checks (layering and hot path). scratch() runs only after git_push has returned a refusal, and its full-command regex runs before any git call. Measured: a passing push (`origin feature`, `origin feature:heads/main`) and a non-push (`git status`) make 0 git calls. A would-be-refused push makes 3 to 5 git calls (rev-parse, remote get-url, config, and one rev-parse per URL), the same as the existing origin() and current_branch() calls. The git options the command passes go only to builtins. Coupling is one-way: guards.scratch reads ws.DIR and _git, and nothing new imports it.
- [low] blocks: no. push-refspecs can build on this, with limits it must record. scratch() keys on the remote, not the refspec, so a change to how git_push reads destinations composes with it unchanged. Two spellings in push-refspecs' acceptance do not pass through the scratch exception. (a) An option before the remote: `git push --all origin` from main is refused at the head. `git push origin --all` passes. (b) A forced glob such as `+refs/heads/*:refs/heads/*`, quoted or not: `*` and `'` are outside the word class, so it is refused. Unforced globs pass today only because git_push does not read them yet. Once push-refspecs refuses globs, its own probe through the door would refuse them too. The spec line "push-refspecs ... is not blocked by this" (spec.md:66) is therefore too broad. The fix costs no lines. push-refspecs can spell options after the remote, or widen the class to `*` and `'`. A `*` in the remote word already fails the URL pattern at line 172. Either choice is a two-way Assumption for that item.
- [low] blocks: no. Fitness. Runtime is 3,004 at the head against 2,986 at main 3d2eb29, under the 3,400 cap (test_setup.py:113, `cat cli/wuwei/*.py | wc -l`). The item's own budget is still +18 against +3, but that is recorded under spec Assumptions and is now inside the cap. The 396 lines left cover push-refspecs (6) and gs-args (5).
- [low] blocks: no. Not run, for the security gate. `--recurse-submodules=on-demand` (and `push.recurseSubmodules` config) passes the scratch rule (guard read: pass). git then pushes the submodules to their own remotes. The same shape is already open at main through any non-default-branch push (`git push origin feature --recurse-submodules=on-demand`), so this is an existing gap, not a regression.
- [low] blocks: no. Notes carried from 6a5d00d with no new evidence: the trust anchor is all of gettempdir() or /tmp (recorded under Assumptions), and core.worktree with updateInstead is an existing ledger-door gap.

## Probes
- Head unchanged: origin/claude/scratch-remotes-2 = ad953d3 (git rev-parse after fetch). The merge base with main is 3d2eb29. main has since moved to 8c1939e, which only touches the release files (git diff --stat).
- Suite in a git archive copy at the head: 1859 passed, 2 skipped (/root/.local/bin/pytest -q).
- Route differential: all 257 routes in the head routes.json (sha256 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0), read through guards.bash at 3d2eb29 and at the head with the corpus test's fixtures (origin o/r, branch i-1-change, cwd /repo): 0 routes move in verdict or reason.
- Guard reads with real git repositories in my scratch folder (bare r.git, clone c, origin ../r.git, gh on GitHub), 18 commands at main and at the head, with git subprocess calls counted. The results are in findings 1, 4 and 5. Every command that main refused and the head passes has a scratch remote.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (diff).
- No real push run: my reads go through guards.bash only. The builder's acceptance push and the 6a5d00d combinatorial probe (11,340 commands, 0 holes) were not re-run, because the delta to the parser is one character added to the class. That is the security gate's re-run.
- Confidence medium: the closures and the hot-path claim are measured directly. The submodule note and the push-refspecs limits are read from git's documented behaviour, not run.

## Residual risk
The scratch exception still trusts git's own reports of the push URLs and the common directory. Exec paths, receive hooks, submodule recursion and a race that plants .git stay open, as SECURITY.md lists. push-refspecs has to record how it spells options and globs to run through this exception.
