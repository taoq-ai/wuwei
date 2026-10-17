Verdict: FIX
Gate: arch
Item: records
PR: taoq-ai/wuwei#1116
Head: 6d4f8af518d0e253a9b097fce9fbaf65d992e90f
Confidence: high
Breaking: yes: Bash sessions and seats that write .wuwei/cache by shell or by Write/Edit, spell the ledger with globs or braces (rm -rf .wuwei/*, rm -rf .*), run find with -delete, -exec, -execdir, -fprint, -fprintf or -fls on a records path (cache included, reads too), run a writer or a redirect to a file after cd/pushd into .wuwei or with a session cwd inside it, or run git clean -x/-X without plain outside pathspecs, are now refused

## Findings
- [high] cli/wuwei/guards.py:344 blocks: yes. Failure: promise (5) says git clean -x is refused unless every pathspec lies outside .wuwei, but the pathspec test only checks the first character (not . / * ? [ : \) and never runs the new records() matcher. Under real bash and real git, in a fresh repository with .wuwei git-ignored, each of `git clean -fdx "$PWD"`, `git clean -fdx $PWD`, `git clean -fdx "${PWD}"`, `git clean -fdx ~+`, `git clean -fdx {.wuwei,src}`, `git clean -fdx {src,.wuwei}`, `git clean -fdx "$PWD"/.wuwei`, `git clean -fdx $(pwd)` and `git clean -fdx` with backtick pwd deleted .wuwei/ledger/a.jsonl, and guards.bash passed all 9. `"$PWD"/.wuwei` and `{.wuwei,src}` are spellings that promise (1) says the matcher reads. The same fix applies to the vendored copy .claude/wuwei/cli/wuwei/guards.py:344. A fix that fits the 5 lines of headroom: add `$`, `~`, `{` and backtick to the refused first characters, and also refuse when records(v, None) matches a pathspec. Then add the 9 commands to tests/fixtures/routes.json as refusals.
- [low] blocks: no. docs/design.md:148 and docs/site/concepts/doors.md:13 say "`find` with `-delete` or `-exec`". The code (FIND in guards.py:24), SECURITY.md and the spec also refuse -execdir, -fprint, -fprintf and -fls. The PR's Change 3 and its BREAKING CHANGE line leave out -fprint, -fprintf and -fls. Name all six in both places.
- [low] blocks: no. find applies the cache set too, so `find .wuwei/cache -name "*.json" -exec cat {} +` (a read) and `find .wuwei/cache -delete` are refused, while `rm -rf .wuwei/cache` passes. This goes beyond promise (3), whose matcher covers .wuwei and the ledger. The BREAKING line's "records path" does not say that it includes the cache. Record this under Assumptions, or name it in the BREAKING line.
- [low] blocks: no. `inside` never resets: `cd .wuwei; cd ..; rm -rf build` is refused, and so is `cd .wuwei && cat plan.json > /tmp/x`. A session whose cwd is inside .wuwei cannot run `python3 -m pytest` or `cp`. These are over-refusals. The docs and the PR review notes describe them, and no traced route hits them.
- [low] blocks: no. `git clean -fdx -e .wuwei` is refused because an exclude is not a pathspec. This is safe-side and documented in the spec's clarification.
- [low] blocks: no. `touch .wuwei/cache/x` passes, because touch is not in WRITERS. That gap existed before and it creates an empty entry only.

## Probes
- Read with `wuwei plan show records`, `git diff origin/main...6d4f8af5` and `gh api repos/taoq-ai/wuwei/pulls/1116` (head 6d4f8af5, draft). The tree was copied with git archive into the scratch folder arch-records/head, with base 5fa32fe in arch-records/base.
- The cli/wuwei and .claude/wuwei/cli/wuwei copies of guards.py are byte-identical at head (diff).
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 2995 at head and 2980 at base. That is +15 against a budget of 18, under the 3,000 cap with 5 lines left for gh-args. The code imports only the stdlib (fnmatch, os.path).
- `pytest -q` in the head copy: 1341 passed, 2 skipped.
- Traced seat routes: all 3,701 Bash and edit rows of .wuwei/traces.jsonl replayed through guards.bash and guards.pre_tool at base and at head. Base refused 53 and head refused 52. The one difference (a gh pr create note that became a pass) is a replay artifact: once() wrote a notes-s marker during the base run, and the head run saw it. No route moved from pass to refuse.
- WUWEI's own paths: grep over charters, agents, skills, hooks, bin, scripts and cli found no shell write to .wuwei/cache, no git clean and no cd into .wuwei followed by a write. The CLI writes the cache through ws.cache_put and atomic_write in Python, which the Bash guard never sees, and `wuwei sync` and `cd .wuwei && wuwei status` pass. Builder worktrees are not under .wuwei.
- Edit paths at head: .wuwei/plan.json, goals.md, config.toml and verdicts/* pass. .wuwei/cache/ci-x.json, the bare .wuwei and .wuwei/{cache,x}/a are refused.
- Edge probe of 37 commands at head: the acceptance shapes behave as the spec says, and the 10-group brace path is refused. The over-refusals listed above were found here.
- git clean pathspec probe: 11 commands, each run under real bash and real git in a fresh repository with .wuwei ignored, then through guards.bash. It found 9 holes (finding 1). `src` and `"$OLDPWD"` did not delete the ledger.
- Docs: design.md, doors.md and SECURITY.md follow. SECURITY.md drops the gaps this closes (cd .wuwei, globs, find -delete, git clean) and keeps the ones it leaves (symlink, glued quote, install). It adds cd to a variable or `cd -`, xargs, dotglob and GLOBIGNORE, and ancestor deletes. It does not list the git clean variable or brace pathspec, which the fix closes.
- Mutants: not run. They belong to the quality gate, and this gate traced contracts and routes.
- Confidence high: finding 1 was reproduced by real execution, and the route replay covers every traced row.

## Residual risk
The pathspec rule tests a spelling, not where the path resolves: a pathspec the shell expands from a variable, a substitution or ~ can reach .wuwei unless that first character is refused. The leading-dot glob reading depends on dotglob and GLOBIGNORE being unset, as SECURITY.md records.
