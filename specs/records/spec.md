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
   path component with sh's glob rules (`*`, `?`, `[...]`, `[^...]`; a bracket holding a POSIX
   class, `[=x=]` or `[.x.]` reads as `*`, which over-approximates and fails closed), where a glob
   only matches the leading dot of `.wuwei` when the pattern itself starts with a dot. It is true for
   `.wuwei`, `.wuwei/ledger`, `.wuwei/ledger.jsonl` and anything under them, wherever the path
   appears: a redirect target, a writer argument or an edit path.
2. The cache (`.wuwei/cache`) holds entries that feed gate inputs (`ci-`, `review-`,
   `default-branch`). A redirect into it, a writer argument naming it (any writer but `rm`), a python
   argument (each path inside a `python -c` body too), or a Write or Edit path is refused, and the
   reason names the cache. `rm` of a cache file
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
- Q: What does "lies outside .wuwei" mean for a `git clean` pathspec? A: it is read by allowlist,
  since two denylists were each beaten by the next spelling. The pathspec and every `-C` dir are
  plain words (letters, digits, `_ . / -`), the pathspec joined to the `-C` dirs does not normalize
  to `.`, an absolute path or one climbing with `..`, and `records()` does not match it.
  `git clean -fdx build/` passes; `.`, `*`, `/abs/x`, `:(top)x`, `"$PWD"`, `~+`, `{.,}wuwei` and
  `$(pwd)` are refused. An exclude (`-e` or any prefix of `--exclude`, as git abbreviates) whose
  value is not a plain word counts like `x`, because one starting with `!` un-ignores `.wuwei`.
  Any git option before `clean` other than `-C <dir>` (`--work-tree`, `--git-dir`, `--namespace`,
  `-c`) and any `GIT_` in the command refuse it, because they move where git resolves pathspecs.
  A dry run gets no exemption: `--no-dry-run` and its abbreviations cancel `-n`.
- Q: Does the `find` rule apply the cache too? A: yes. `find` reads every argument against the
  ledger and the cache, so `find .wuwei/cache -delete` and a read such as
  `find .wuwei/cache -name '*.json' -exec cat {} +` are refused, while `rm -rf .wuwei/cache`
  passes. Telling a reading `-exec` from a writing one is not possible from the command line; the
  refusal costs a seat `ls` or `cat` instead.
- Q: How does the guard read a `python -c` body? A: every writer's arguments are also split at
  whitespace, quotes, parentheses, commas and semicolons, and each piece meets the matcher, so
  `open('.wuwei/cache/c.json','w')` is read. The whole arguments are still read as before, so a
  glob such as `.[,w]uwei` keeps its meaning.
- Q: Does a session whose directory is already inside `.wuwei` count as "cd into .wuwei"? A: yes.
  The Bash tool keeps the directory between calls, so `cd .wuwei` in one call and `rm -rf ledger` in
  the next would otherwise pass. The rule starts from `records(cwd)`.
- Q: Do `env -C`, `env --chdir` and `sudo -D` count as `cd`? A: yes, wider than promise (4), which
  names `cd` and `pushd`. Each changes the directory for the program after it, so
  `env -C .wuwei git clean -fdx ledger` deleted the ledger unrefused. The guard reads every `-C`,
  `--chdir` and `-D` value on the command line, of any program, and a value that names `.wuwei`
  (or expands past 64 words) turns on the same rule as `cd .wuwei`. So `tar -C .wuwei -xf x.tar`
  with a redirect, which does write there, is refused too, and a writer in another segment of the
  same command is refused as well. `git -C .wuwei status`, `env -C src git clean -fdx t`,
  `make -C build` and `sort -D` pass. The values are read as a set, and a writer's words too, so
  repeating one slow word costs one check.

## How this fails

1. A seat route writes into `.wuwei/cache` by shell or runs `git clean -x` (for example to reset a
   scratch tree) and is now refused. Guarded by the route corpus: no recorded route moves, and the
   refusal names the cache and says removal passes.
2. The matcher over-reaches and refuses a common read or a write elsewhere, for example
   `rm -rf .*` in a scratch folder. `cp .wuwei/cache/c.json /tmp/x` (cp reading a cache file) is
   refused by design: a writer argument naming the cache is refused wherever it stands, as main
   already does for the ledger. Measured: every acceptance-4 row passes, the
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
- FR-006: runtime within +15 lines (the coordinator's budget update); measured +15 (2,995), and
  the fix round after the gates at 6d4f8af stays at 2,995.

## Breaking

Commands that passed on main are now refused:

- any write into `.wuwei/cache` by shell or by the Write and Edit tools;
- glob and brace spellings of the ledger (`rm -rf .wuwei/*`, `rm -rf .*`, `rm -rf .w*/ledger`);
- `find` with `-delete`, `-exec`, `-execdir`, `-fprint`, `-fprintf` or `-fls` on a records path, the cache included (reads too);
- a `python -c` body naming a path in the ledger or the cache, reads too, and a writer argument
  whose quote or punctuation pieces name a records path (`cp a "x .wuwei"`);
- `git clean -fd -e '!...'` (an exclude that un-ignores `.wuwei`) without plain outside pathspecs,
  a git clean after a git option other than `-C`, or with `GIT_` in the command;
- a writer or redirect after `cd .wuwei` in the same command, or in a session whose directory is
  inside `.wuwei`, or in a command where a `-C`, `--chdir` or `-D` value names `.wuwei`
  (`env -C .wuwei rm -rf ledger`, `sudo -D .wuwei ...`, `tar -C .wuwei -xf x.tar > log`);
- any git command after a git option other than `-C` whose words contain `clean`
  (`git -c user.name=L commit -m "clean up"`, `git --no-pager log --grep clean`);
- `git clean -fdx` and `git clean -fdX` without plain pathspecs that lie outside `.wuwei`, dry runs
  (`git clean -n -x`) included.

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
- A writer path whose braces expand to more than 512 words is refused without expanding it,
  because expansion multiplies (five `{a..z}` groups took 36 s). Each group, even one of a single
  word, halves the budget, which bounds the depth. No recorded route has more than two groups.
  Overturned if a seat route expands more than 512 words in one writer path.
- Splitting every writer's arguments at quotes and punctuation refuses a few more names, such as
  `python3 -c "p = Path('.wuwei') / 'cache'"` or a file named `x .wuwei`. A `python -c` body that
  only reads the cache or the ledger (`print(open('.wuwei/cache/c.json').read())`) is refused too.
  Overturned if a seat route is refused this way.
- git clean with `x`, `X` or an exclude is read by allowlist, which refuses some safe commands:
  `git clean -n -x` and `git clean --dry-run -x` (a later `--no-dry-run` would cancel them, so no
  dry run is exempt), `git clean -fdx :/src` (pathspec magic), `git -C /abs/repo clean -fdx build`
  (an absolute `-C` dir), and any git command after an option other than `-C` whose words contain
  `clean` (`git --no-pager log --grep clean`). This is the safe side: a two-way choice, undone by
  widening the allowlist. Overturned if a seat route is refused this way.
- A brace range is measured before it is built: at most cap + 1 words are made, so a range up to
  U+3134A costs no more than a small one.
- The `-C`, `--chdir` and `-D` values are read from the whole command line, not only after `env`
  and `sudo`, because one regular expression costs 0 lines where a wrapper parser does not. A value
  is read with a 64-word brace cap, since a directory option takes one directory. The trace replay
  (4,052 unique rows) and the route corpus move no verdict. Overturned if a seat route that
  names `.wuwei` after one of these options, with a writer or redirect, is refused.

Rollback: revert the commits on this branch; no data or config migrates.
