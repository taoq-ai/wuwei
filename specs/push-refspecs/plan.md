# Implementation plan: push-refspecs

**Spec**: `specs/push-refspecs/spec.md`
**Item**: push-refspecs, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,400 lines. Main dc39cae holds 3,011.
  The item's budget is +4, ceiling 6; free-lines-5 is no longer a prerequisite.
- `guards.bash` reads git's options before the subcommand (git-globals) and calls
  `git_push(root, rest[i + 1:], here)`; a refusal passes only when `scratch()` reads the remote as
  a git directory in a scratch folder (scratch-remotes).
- `git_push` on main: refuses `--force*`, `--mirror`, `-f` clusters and `+` refspecs; then names
  each refspec's destination (first colon, `refs/heads/` stripped) and refuses one equal to the
  default branch.

## Design

1. `longs`: the long-option words (`--[a-z]+`) with the dashes cut. Any of them that is a prefix
   of `mirror` is a force push (same text); a prefix of `all` or `branches` adds the pattern
   `refs/heads/*` to the targets.
2. Each refspec splits at its last colon (`rpartition`). A destination `''` or `HEAD` is the
   current branch, except the bare `:`, whose destination is the pattern `*`. A destination with a
   `*` is kept as a full-name pattern; any other becomes `refs/heads/` plus the name with a leading
   `refs/heads/` or `heads/` cut.
3. The refusal: any default branch `b` with `fnmatchcase('refs/heads/' + b, target)` for a target.
   `deleting` holds when a refspec has a colon, an empty source and a destination, or with
   `--delete`/`-d`, so `:` and `--all` say "pushing to".
4. Re-vendor `.claude/wuwei/cli/wuwei/guards.py`; design.md and doors.md name the spellings in one
   clause each.

## Evidence

- Tests in `tests/test_guards.py`: 15 real-git cases where real git moved main on a scratch bare
  remote and the door, with the remote read as non-scratch, refuses; 7 real-git cases that leave
  main alone and pass; 5 unit cases (git rules with no 2.43 run: `--branches`, `--bra`, `+:`,
  `refs/heads/m*`, `--delete heads/main`); 5 reason-text cases.
- Route corpus: main's 257 routes read the same at the head; 12 rows added, 8 of which move
  (pass on main, push at the head).
- Generated probe `specs/push-refspecs/probe.py` under real bash, a stub git on PATH that logs and
  then execs git 2.43, at main and at the head.
- Mutants: each rule changed in its own copy (both guards.py copies); the guard tests fail on each.

## Constitution check

- Stdlib only (`fnmatch`, `re`): pass.
- Test first: the item's tests ran 22 red on main's guard before the change, 32 green after.
- Simplest: one function changed, no new helper; git's rules written as one normalisation and one
  pattern match.
- Runtime: 3,012 against main's 3,011 (+1).
