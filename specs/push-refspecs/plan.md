# Implementation plan: push-refspecs

**Spec**: `specs/push-refspecs/spec.md`
**Item**: push-refspecs, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,400 lines. Main dc39cae held 3,011; main 6682925 held 3,026;
  main 7fd8f4b held 3,093; main 5a33509 held 3,178; main dc9aad9 held 3,183; main 17ff289 held 3,322; main 5b5084b holds 3,351.
  Round 3's budget is the PR's earlier +21; free-lines-5 is no longer a prerequisite.
- `guards.bash` reads git's options before the subcommand (git-globals) and calls
  `git_push(root, rest[i + 1:], here)`; a refusal passes only when `scratch()` reads the remote as
  a git directory in a scratch folder (scratch-remotes).
- `git_push` on main: refuses `--force*`, `--mirror`, `-f` clusters and `+` refspecs; then names
  each refspec's destination (first colon, `refs/heads/` stripped) and refuses one equal to the
  default branch.

## Design

1. `longs`: the option names `_flags` reads, with `PUSH_VALUED` (`o` and every prefix of
   `push-option`, `repo`, `receive-pack`, `exec`, `recurse-submodules`) taking the next word, and
   `--end-of-options` read as `--` (round 1). Any name that is a prefix of `mirror` is a force push
   (same text); a prefix of `all` or `branches` adds the pattern `refs/heads/*` to the targets.
   The operands are the words `_flags` reads as positional: every word after the first `--`.
2. Each refspec splits at its last colon (`rpartition`). A destination `''` or `HEAD` is the
   current branch, except the bare `:`, whose destination is the pattern `*`. A destination with a
   `*` is kept as a full-name pattern; any other becomes `refs/heads/` plus the name with a leading
   `refs/heads/` or `heads/` cut.
3. A source alone `@` resolves to `HEAD` (round 1: through rev-parse), and with no refspec the current branch is a target unless a
   `--tags` prefix stands (git then sends `refs/tags/*` alone). Both came from the probe's first
   run at the head.
4. The refusal: any default branch `b` with `fnmatchcase('refs/heads/' + b, target)` for a target.
   `deleting` holds when a refspec has a colon, an empty source and a destination, or with
   `--delete`/`-d`, so `:` and `--all` say "pushing to".
5. Re-vendor `.claude/wuwei/cli/wuwei/guards.py`; design.md and doors.md name the spellings in one
   clause each.
6. Round 1 (gates at b16d799): the last of `--tags` and `--no-tags` decides whether the current
   branch is a target. A refspec with no colon also adds the name
   `git rev-parse --verify --quiet --symbolic-full-name --end-of-options <word>` prints at the
   push's directory, through the guard's `_git`; an empty answer adds nothing and the text reading
   stands.
7. Round 2 (gates at 9cb834a; the lead's design): `_sources(cwd)` reads the refs once per push.
   One `for-each-ref` gives each symbolic ref and its final
   target; one `rev-parse --git-dir --git-common-dir` gives the directories whose root files
   starting with `ref: ` are root refs (the shared ones, `main-worktree/<name>`,
   `worktrees/<id>/<name>`, then this worktree's own, so HEAD is its own). A source alone adds
   the target of every name `REF_RULES` makes of it (`@` is `HEAD`). The current branch is read
   once per push. `_flags` takes its end markers as an argument, so only the first `--` or
   `--end-of-options` ends the push's options. A one-letter name is no `--tags` prefix, and any
   name `delete` starts with says "deleting". A target with no `*` is compared as a string.
8. Round 3 (gates at aa63d3b; the lead's design): `_sources(cwd, words)` keeps the one
   `for-each-ref` and replaces the root file reader with one
   `git -c core.warnAmbiguousRefs=false rev-parse --symbolic-full-name --revs-only --end-of-options`
   over the colon-less words. `words` leaves out `tag`, words starting with `^`, globs and `--`,
   and adds `main-worktree/--` last when `--` is a refspec. `_git` takes `failed`, the value it
   gives when git cannot run or finish in 5 s; both reads ask for `None`, and `git_push` refuses
   when either is `None`, with a text that names the default branch. The `suppress` import goes.
9. Round 4 (gates at 457f6a8): a `--` refspec adds the pattern `refs/heads/*` to the targets, so
   the push meets the door as `--all` does. The `main-worktree/--` lookup and the `--` exclusion
   from the batch go, since a push holding `--` is refused whatever the batch prints.

## Evidence

- Tests in `tests/test_guards.py`, 36 item cases: 15 real-git cases where real git moved main on a
  scratch bare remote and the door, with the remote read as non-scratch, refuses; 7 real-git cases
  that leave main alone and pass; 4 real-git cases from a clone on main (`@`, `--tags`); 5 unit
  cases (git rules with no 2.43 run: `--branches`, `--bra`, `+:`, `refs/heads/m*`, `--delete
  heads/main`); 5 reason-text cases. Round 1 adds 27 real-git cases: 13 from the main clone on main
  where an option takes the next word or `--no-tags` comes last and real git moves main, 3 that
  move nothing and pass, and 11 for a dash refspec after `--` or `--end-of-options`, another
  worktree's HEAD and a symbolic ref to main.
- Route corpus: main's 257 routes read the same at the head; 12 rows added, 8 of which move
  (pass on main, push at the head).
- Generated probe `specs/push-refspecs/probe.py` under real bash, a stub git on PATH that logs and
  then execs git 2.43, at main and at the head.
- Mutants: each rule changed in its own copy (both guards.py copies); the guard tests fail on each.
- Round 3: 18 real-git rows in `test_a_refspec_git_resolves_to_main_meets_the_push_door` (the
  security gate's root ref forms, the words that stop rev-parse, a root ref beside a branch of its
  name), `tag v1` as a pass row, a call-count test in place of the 1 s bound, a fail-shut test per
  ref read, and a `--del` text row. The probe adds the rootfile class (240) and the stopper class.

## Constitution check

- Stdlib only (`fnmatch`, `re`): pass.
- Test first: the first 32 cases ran 22 red on dc39cae's guard before the change; the 4 from the
  probe ran red before their fix. All 36 run 26 red on main 6682925's guard and green at the head.
- Simplest: `git_push` changed and one helper added in round 2, `_sources`, the ref read once per
  push; git's rules written as one normalisation, one table of ref rules and one pattern match.
  Round 3 makes `_sources` two git calls and no file reads.
- Runtime: 3,369 against main 5b5084b's 3,351 (+18), under main + 21 and the cap of 3,400 (spec
  Assumptions).
