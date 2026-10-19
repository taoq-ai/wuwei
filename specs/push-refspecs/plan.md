# Implementation plan: push-refspecs

**Spec**: `specs/push-refspecs/spec.md`
**Item**: push-refspecs, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,400 lines. Main dc39cae held 3,011; main 6682925 held 3,026;
  main 7fd8f4b holds 3,093. The item's budget is +4, ceiling 6; free-lines-5 is no longer a prerequisite.
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
3. A destination `@` reads as `HEAD`, and with no refspec the current branch is a target unless a
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

## Constitution check

- Stdlib only (`fnmatch`, `re`): pass.
- Test first: the first 32 cases ran 22 red on dc39cae's guard before the change; the 4 from the
  probe ran red before their fix. All 36 run 26 red on main 6682925's guard and green at the head.
- Simplest: one function changed, no new helper; git's rules written as one normalisation and one
  pattern match.
- Runtime: 3,098 against main 7fd8f4b's 3,093 (+5), one over the budget of +4, inside the ceiling of 6
  (spec Assumptions).
