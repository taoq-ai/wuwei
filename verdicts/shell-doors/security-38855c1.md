Verdict: PASS
Gate: security
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: 38855c10e14946b3737c597133e74ec972268d6b
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:87 blocks: no. Mutant R10 (treat a trailing redirect as followed by `(`) survives, but it is equivalent: segments always appends `;`, so the last pair has b = `;`, the CONTROL branch marks it unread, and c is never read. No input reaches a different verdict.
- [low] blocks: no. A named fd still hides the program: `{fd}>x git push origin main`, `{fd}<x ...`, `git {fd}>x push origin main`, `{fd}>&2 ...` and `true;{fd}>x ...` pass, and the stub git logged the push. This is on main too and is listed in SECURITY.md line 47.
- [low] blocks: no. A here-string fed to a shell, `sh <<<"git push origin main"` or `bash <<< '...'`, passes and bash pushes. This is listed in SECURITY.md line 39. So are `"$(...)"`, backticks, coproc and eval, which still pass with a real push. Existing ledger gaps, also on main: a write through a symlink, `install`, and a `python3 -c` body.

## Probes
Last round's findings at this head:
- `2>&1>x git push origin main`, `git 2>&1>x push origin main`, `true;2>&1>x ...`, `2>&1<x ...` and `echo x 2>&1>.wuwei/ledger/a.jsonl` (and `>>`) are refused: closed.
- `<<x git push origin main` and `<<-x ...` are refused: closed.
- `<&0 git push origin main` is refused, and mutant R9 (drop `<&`) is killed by `test_a_push_after_any_redirect_meets_the_push_door[<&0 ...]`: closed.
The builder's pairs.py (copied, sha256 b9aeca8b6ccd8046219f06f3e6048de7a96b0dd812e763d9b068c59943f70539, with my own stub git) run on both trees:
- Head: 34,300 push shapes read, 9,488 passed and run in bash, 6,912 ledger shapes read, 0 holes.
- Main a7fe6d5: 10,345 holes.
My triples.py (real bash with a stub git) at head:
- Three chained redirects from 12 operators with an optional `2` prefix, either glued, glued with words between, or a word then a glued pair, in three positions: 124,454 push shapes, 44,712 passed and run in bash. Plus 41,483 ledger shapes. 0 holes in the generated set.
- 38 extra shapes. The only holes are the named-fd and here-string notes above.
- exec forms (`exec >x;`, `exec 3>x`, `exec 2>&1>x`, `exec {fd}>x`, `exec <x`, `exec 3<>x`, `exec 2>&1>x<&0`) are all refused.
- Here-doc bodies (`bash <<x` with the push on the next line, `bash <<-x`) are refused by the multi-line rule.
The `(` exception cannot hide a door: the program inside the parentheses still becomes its own segment. `>(git push origin main)` as a redirect target in `echo x >(true) >(...)`, `>>(`, `2> >(`, `&> >(`, `> >(`, `>&>(`, `>| >(` and `2>&1 > >(`, plus `< <(...)`, `0< <(`, `3< <(`, `<(<(...))`, and bare `>(...)` and `<(...)`, all reach the push door.
The input-redirect change: `cat <.wuwei/ledger/a.jsonl` passes and bash leaves the file unchanged. `cat 0<>`, `echo x 1<>` and `tee <<<x .wuwei/ledger/a.jsonl` are refused, and `> >(tee ledger)` and `> >(cat >ledger)` are refused.
cmds1-7 at head:
- Leak and infra checks hold: all `$'`/`$"` curl shapes with a token are refused and `terraform apply $'...'` gets `ask`.
- The everyday shapes pass. The only refusals are merges of a PR with gaps (`gh pr merge 5 ...`) and one unnamed merge, `gh pr merge 5>&2`, matching bash, which runs `gh pr merge` with no number.
- 15 door commands with plain redirects or process substitution (`> >(tee x)`, `< <(gh pr list)`, `2>&-`, `<&-`, `3>&1 1>&2 2>&3`, `<<< x`) are not marked unread.
Mutants, each in a fresh copy made with git archive: R1 (no structural rule), R2, R3 (the `(` exception), R4 (`<<`), R5 (`(?<![<>]&)`), R6 (`<>` read as input), R7 (every redirect word a target), R8 (a redirect then a control operator) and R9 (`<&`) are each killed by a named test. R10 is equivalent (note above).
Suites: head 1192 passed, 2 skipped. Runtime is 2,999 lines (cat cli/wuwei/*.py | wc -l).
Route corpus: routes.json sha256 9ea9491c19cbd2535f70e04252f6044e4c306c48a298f8fdcbc44b5f2501dff8 at head (main a7fe6d5 has 5cdfe52932d9e1fde0afe31196b78616aa8047a60e318ef2e381518543084755). The 160 rows from e2950da are unchanged, and the route tests pass at head (267).
Refusals naming another PR or repo: none (119 refusals). The one heuristic hit, `gh pr merge https://github.com/other/x/pull/5 -R o/r`, names the URL's own repo, which gh acts on; it is the same on main.
Confidence is high because both generated probe sets run under real bash with a stub git, and every mutant except one equivalent is killed.

## Residual risk
The guard is still a word-level reading of sh. Named fds, a here-string fed to a shell, eval, coproc, backticks and `"$(...)"` stay recorded gaps.
