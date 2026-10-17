# Feature Specification: writes to the ledger and the cache meet the ledger door in the spellings sh expands

**Feature branch**: `claude/records`
**Item**: records, tier full, goal G-2
**Input**: the lead's spike found writes to `.wuwei/ledger` that bash runs and `guards.bash` on main
passes (globs, braces, `cd .wuwei`, `find -delete`, `git clean -fdx`), and a two-step bypass of the
push door: a shell write of `.wuwei/cache/default-<repo>.json` flips the default branch the push
door reads, and the next `git push origin main` passes.

## The promise in my words

1. One function, `guards.records(path, below)`, replaces the `LEDGER` regex. It expands braces
   (`{a,b}`, `{a..z}`, nested, descending, stepped), collapses `//`, `/./` and `..`, and matches each
   path component with sh's glob rules (`*`, `?`, `[...]`, `[^...]`, POSIX classes), where a glob
   only matches the leading dot of `.wuwei` when the pattern itself starts with a dot. It is true for
   `.wuwei`, `.wuwei/ledger`, `.wuwei/ledger.jsonl` and anything under them, wherever the path
   appears: a redirect target, a writer argument or an edit path.
2. The cache (`.wuwei/cache`) holds entries that feed gate inputs (`ci-`, `review-`,
   `default-branch`). A redirect into it, a writer argument naming it (any writer but `rm`), a python
   argument, or a Write or Edit path is refused, and the reason names the cache. `rm` of a cache file
   or the cache folder passes: the next read fetches it again.
3. `find` with `-delete`, `-exec` or `-execdir` (also `-fprint`, `-fprintf`, `-fls`, which write a
   file) and an argument the matcher matches is refused. `find .wuwei -name x` passes.
4. `cd` or `pushd` into `.wuwei` or anywhere below it, followed in the same command by a writer
   program or a redirect to a file, is refused. `cd .wuwei && cat plan.json` passes.
5. `git clean` with `x` or `X` in any short cluster is refused unless it names pathspecs and every
   one lies outside `.wuwei`. `.wuwei` is git-ignored, so `git clean -fdx` deletes the ledger;
   `git clean -fd` passes.

The acceptance scenarios, restated:

1. In a fresh folder holding `.wuwei/ledger/a.jsonl` and `.wuwei/cache/c.json`, real bash changes
   the ledger row or the cache value for `rm -rf .wuwei/*`, `rm -rf .wuwei/{l,}edger`,
   `rm -rf .w*/ledger`, `find .wuwei -delete`, `cd .wuwei && rm -rf ledger`, `git clean -fdx` (in a
   git repository ignoring `.wuwei`) and `echo 0 > .wuwei/cache/c.json`, and `guards.bash` refuses
   each.
2. The generated probe (ledger spellings x writers, cache spellings x writers) runs every command
   under real bash in a fresh folder and through `guards.bash` at the head and reports the generated
   count, the count that changed the records, and 0 holes.
3. `echo '"x"' > .wuwei/cache/default-taoq-ai__wuwei.json` is refused with text naming the cache,
   and a Write tool call on `.wuwei/cache/ci-x.json` is refused by `guards.pre_tool`.
4. `rm -rf *`, `rm -rf .wuwei/cache`, `rm .wuwei/cache/x`, `cat .wuwei/ledger/x.jsonl`,
   `cd .wuwei && cat plan.json`, `find .wuwei -name x`, `git clean -fd`, `rm foo.wuwei` and
   `rm -rf .wuwei-x` pass.

Out of scope (the item's Outside): deleting from an ancestor without naming `.wuwei`
(`find . -delete`, `rm -rf ..`), `.wuwei/plan.json` and verdicts.

## Clarifications

- Q: Which `find` arguments does the matcher read, only the start paths? A: every argument. A start
  path of `.` with `-path './.wuwei/*' -delete` deletes the ledger, so reading only start paths
  would leave a hole; reading all of them refuses more, never less, and `find .wuwei -name x` still
  passes because it has no action that writes.
- Q: Does "a writer program" after `cd .wuwei` include a redirect? A: yes, a redirect to a file
  (not an fd duplicate such as `>&2` or `2>&1`, and not `/dev/...`). Without it,
  `cd .wuwei && echo x > ledger/a.jsonl` truncates the ledger unrefused.
- Q: What does "lies outside .wuwei" mean for a `git clean` pathspec? A: the normalized pathspec
  starts with a plain character: not `.`, `..`, `/`, a glob character or `:` (pathspec magic).
  `git clean -fdx build/` passes; `.`, `*`, `/abs/x` and `:(top)x` are refused because each can
  reach `.wuwei`. A `-e`/`--exclude` value is not a pathspec.
- Q: Does a session whose directory is already inside `.wuwei` count as "cd into .wuwei"? A: yes.
  The Bash tool keeps the directory between calls, so `cd .wuwei` in one call and `rm -rf ledger` in
  the next would otherwise pass. The rule starts from `records(cwd)`.

## How this fails

1. A seat route writes into `.wuwei/cache` by shell or runs `git clean -x` (for example to reset a
   scratch tree) and is now refused. Guarded by the route corpus: no recorded route moves, and the
   refusal names the cache and says removal passes.
2. The matcher over-reaches and refuses a common read or a write elsewhere, for example `cp` reading
   a cache file, or `rm -rf .*` in a scratch folder. Measured: every acceptance-4 row passes, the
   route corpus keeps every verdict, and 164 of the 462 probe commands name the records without
   bash changing them (an ambiguous redirect, a failed `mv`); those are refused by design.
3. A spelling sh expands that the matcher does not read stays a hole: `shopt -s dotglob`, a
   symlink, a quote glued before the path, `cd "$VAR"`, `xargs`. These are listed in SECURITY.md as
   known shapes; the probe found 0 holes across its spellings, including POSIX classes and stepped
   ranges added after the first run found them.

## Requirements

- FR-001: `guards.records` replaces `LEDGER` in the redirect, writer and edit checks.
- FR-002: cache writes are refused with a reason naming `.wuwei/cache`; `rm` of the cache passes.
- FR-003: `find` with a writing action, `cd`/`pushd` into `.wuwei` then a write, and `git clean -x`
  without outside pathspecs are refused.
- FR-004: routes.json records the acceptance rows; every older row keeps its verdict.
- FR-005: docs (doors.md, design.md, SECURITY.md) and the vendored `guards.py` match.
- FR-006: runtime within +15 lines (the coordinator's budget update); measured +15 (2,995).

## Breaking

Commands that passed on main are now refused:

- any write into `.wuwei/cache` by shell or by the Write and Edit tools;
- glob and brace spellings of the ledger (`rm -rf .wuwei/*`, `rm -rf .*`, `rm -rf .w*/ledger`);
- `find` with `-delete` or `-exec` on a records path;
- a writer or redirect after `cd .wuwei` in the same command, or in a session whose directory is
  inside `.wuwei`;
- `git clean -fdx` and `git clean -fdX` without pathspecs that lie outside `.wuwei`.

Migration: WUWEI writes the cache itself; remove a stale entry with `rm .wuwei/cache/<name>` and the
next read fetches it. Name what `git clean -x` may delete (`git clean -fdx build/ dist/`). Run
writers from the repository root with paths that do not name `.wuwei`. The PR title carries `!`
and the commit a `BREAKING CHANGE:` line.

## Assumptions

- No recorded seat route writes into `.wuwei/cache` by shell or runs `git clean -x`: the route
  corpus keeps every verdict at the head. Overturned if a corpus row moves from pass to refusal.
- `-ok` and `-okdir` are left out of the find actions: they wait for a yes on stdin, which the Bash
  tool does not give. Overturned if a harness feeds stdin to Bash calls.
- The refusal text for ledger and cache is one message naming both, to stay in the line budget.
  Overturned if a seat reads the ledger message as being about the cache and acts wrongly.
- A writer path with more than nine brace groups is refused without expanding it, because
  expansion is 2^n. No recorded route has more than two groups.

Rollback: revert the commits on this branch; no data or config migrates.
