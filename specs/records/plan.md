# Implementation plan: records

**Spec**: `specs/records/spec.md`
**Item**: records, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main ab841e3 holds
  2,980 after merge-evidence (#1114); shell-stdin (#1115) adds 0. This item's budget is +15, so
  gh-args (+3 to +5) still fits.
- `guards.LEDGER` is a regex matched against redirect targets, writer arguments and edit paths. It
  reads `//` and `/./` but no glob, brace or `..`, and never the cache.
- `guards.bash` walks each segment; `git` reads `-C` before the subcommand.

## Design

1. `records(path, below=LEDGER)`: expand the innermost brace group and recurse (more than nine
   groups returns true at once); rewrite `[^` to `[!` and a POSIX class to `!-~`; `normpath`; split
   on `/` and `=`; true when a component starting with `.` matches `.wuwei` by `fnmatchcase` and is
   the last, or `below` is `None`, or the next component matches a name in `below`. `LEDGER` and
   `CACHE` become the tuples of names below `.wuwei`.
2. In `bash`, compute `program` and `writer` (the writers, `sed -i`, python, `find` with a writing
   action) once per segment. Refuse a redirect target matching `CACHE`, a writer argument matching
   `LEDGER` for `rm` and `CACHE` for the rest, and, once `inside`, any writer or file redirect.
   `inside` starts as `records(cwd, None)` and turns on after `cd` or `pushd` into `.wuwei`. The
   empty-argv `continue` goes: every later check is false for an empty program.
3. In the `git` branch, refuse `clean` with `x` or `X` (read by `_flags`, with `-e` valued) when
   `inside`, when `-C` names `.wuwei`, or when any pathspec does not start with a plain character,
   or there is none.
4. `pre_tool` matches edit paths with `CACHE`. `LEDGER_DENIED` names the cache and says removal
   passes.

## Verification

- Tests first in `tests/test_guards.py`: real bash changes the records for the seven acceptance-1
  commands and the guard refuses each; 45 refused spellings; the cache reason; acceptance-4 and
  other passes; a session inside `.wuwei`; the brace cap; infra and leak with the new shapes.
- The generated probe (35+ ledger spellings x 10 writers, 13 cache spellings x 4 writers) under
  real bash at main and head from `git archive` copies; an infra and leak probe; the lead's cache
  flip probe.
- The route corpus dumped at main and head, verdicts and reasons compared, sha256 recorded.
- Full suite with the vendored copy refreshed.

## Constitution check

Stdlib only (`fnmatch`, `os.path`), no new door (the cache joins the record door), no config key,
test first, within the line budget.
