# Feature Specification: the push door reads each refspec's destination the way git does

**Feature branch**: `fix/push-refspecs`
**Item**: push-refspecs, tier full, goal G-2
**Input**: the git-globals security gate found, and guards.bash on main confirms, that
`git push origin feature:heads/main`, `git push origin :`, `git push --all origin` and
`git push origin 'refs/heads/*:refs/heads/*'` pass the push door while `feature:main` and
`feature:refs/heads/main` are refused. Each moves main under real git 2.43.

## The promise in my words

1. The push door names the destination of each refspec as git 2.43 does. git splits a refspec at
   its last colon, and a refspec with no colon is its own destination. git matches a destination
   against the remote's refs with its ref rules (`%s`, `refs/%s`, `refs/heads/%s`), so `main`,
   `heads/main` and `refs/heads/main` all name the default branch; a leading `+` is a force push
   and keeps its own refusal.
2. A push that can reach the default branch without naming it is refused too: the matching
   refspec `:`, `--all` and `--branches` (any unique prefix git reads, such as `--al`), and a glob
   refspec whose destination pattern can match `refs/heads/<default>`.
3. The existing refusals keep their text: `--mirror` (now in any prefix git reads, such as `--mirr`)
   is a force push; an explicit default branch is "pushing to" or "deleting" it.

The acceptance scenarios, restated:

1. In a scratch bare remote with a clone holding main and feature, real git runs the four
   commands above; each moved main. The same commands, with the remote read as the real origin
   (not a scratch folder), are refused by guards.bash.
2. A generated probe of destination spellings (main, heads/main, refs/heads/main, `+`, globs, `:`,
   `--all`, `--branches`, `--tags`) crossed with sources runs under real git against a scratch
   bare remote; guards.bash, reading each with the remote as a non-scratch one, refuses every
   command that moved main (0 holes), and pushes that cannot reach main pass.
3. `git push origin feature`, `git push origin feature:feature`, `git push --tags origin` and
   `git push origin 'refs/heads/f/*:refs/heads/f/*'` pass.

Outside (the item's Outside): config-steered pushes (git-globals: `remote.*.push`, `push.default`,
`branch.*.merge`) and config or refs written before the call. Pushes git runs itself (submodule
recursion, `core.hooksPath`) are item push-git-runs.

## Clarifications

- Q: Which colon splits a refspec? A: the last one. git 2.43's `parse_refspec` (refspec.c) uses
  `strrchr(lhs, ':')`. The guard on main split at the first, so `git push origin :/fix:main`
  (source `:/fix`, a commit found by its message) passed and real git moved main.
- Q: Which destination spellings reach `refs/heads/main`? A: git's `count_refspec_match` matches
  the destination against the remote's refs with `ref_rev_parse_rules`: `%s`, `refs/%s`,
  `refs/tags/%s`, `refs/heads/%s`, `refs/remotes/%s`, `refs/remotes/%s/HEAD`. Only three of them
  give `refs/heads/main`: `refs/heads/main`, `heads/main` and `main`. A refspec with no colon takes
  the source's full name as its destination, so `git push origin heads/main` pushes main too.
- Q: How does git match a glob? A: `match_name_with_pattern` (refs.c): one `*` matches any run of
  characters, `/` included, between a fixed prefix and suffix, against the full ref name. The
  guard reads a destination with a `*` as a full-name pattern (fnmatch, where `*` also crosses
  `/`). `heads/*` names no full ref, so `git push origin 'heads/*'` passes, as real git pushes
  nothing for it.
- Q: Which glob pushes are refused? A: every glob whose destination pattern can match
  `refs/heads/<default>`, whatever its source. The item's "unless the refspec's source names no
  default-branch ref" is read at the destination only: a source pattern decides which local refs
  are sent (`refs/heads/f/*:refs/heads/*` reaches main when a local `f/main` exists, and
  `refs/tags/*:refs/heads/*` when a tag `main` exists), and those refs can be written in the same
  command before the push. Over-refusal only; the probe counts it.
- Q: Which option spellings mean `--all` or `--mirror`? A: git's parse-options takes any unique
  prefix of a long option. In git 2.43 push, `--a` is ambiguous (`--all`, `--atomic`) and fails;
  `--al` is `--all`; every prefix of `mirror` is `--mirror`, since no other push option starts with
  `m`. The guard on main refused only `--mirror` spelt in full, and real git moved main for `--mirr`
  and `--m`. git 2.43 lists `--branches` as an alias of `--all` (`git push -h`); the guard refuses
  it and its prefixes, as the promise asks.
- Q: Where may `--all` stand? A: anywhere: parse-options reads options before and after the remote
  and refspecs. The guard on main read `git push --all origin` as a push of the current branch, so
  it was refused only when the current branch was main, whatever the option order.
- Q: What did the first probe run at the head find? A: 6 holes, all one class: `git push origin @`
  from a clone on main. git reads `@` as `HEAD`, so it pushes the current branch; the guard read
  `@` as a branch named `@`. The first head read a destination `@` as it reads `HEAD` (the current
  branch). Round 1 dropped that rule: a source alone `@` now resolves through rev-parse to the
  current branch, and git 2.43 rejects `@` as a destination (`feature:@`, `:@` and `@:@` are
  invalid refspecs), so the rule held nothing a mutant could show. The same run showed `git push --tags origin` refused on main: with no refspec the
  guard read the current branch, while git 2.43 sends only `refs/tags/*` when `--tags` stands
  alone. The guard now adds the current branch only when no refspec and no `--tags` prefix is
  given, so acceptance 3 holds on any branch.
- Q: What does the guard do with quoting and `*`? A: shlex reads single quotes, double quotes and a
  backslash as bash does, so the glob word the guard reads is the word git gets; bash leaves an
  unquoted glob that matches no file as typed. `$'..'` stays unreadable and is refused by the
  raw-text rule. The scratch exception's plain word class (`[\w./=@:+-]`) excludes `*` and quotes,
  so a quoted or glob refspec never passes through it: the door decides it as for any remote.
- Q: Which words does an option take (gates at b16d799)? A: parse-options gives the next word
  whole to `-o`, to a short cluster whose first `o` is last (`-vo`, `-4o`), and to any unique
  prefix of `--push-option`, `--repo`, `--receive-pack`, `--exec` and `--recurse-submodules`
  written without `=`. That word is neither an option nor a refspec. The guard now reads the
  options with `_flags` and those names. At b16d799, `git push --repo --tags origin` and
  `git push -o --tags origin` dropped the current-branch default; real git pushed main from a
  clone on main, and main's guard refused them. `git push origin -o ci.skip` and
  `git push --repo x origin` read `ci.skip` and `origin` as refspecs, on main too.
- Q: Which of `--tags` and `--no-tags` wins? A: the last one (an `OPT_BOOL`). Real git pushed main
  for `git push --tags --no-tags origin` from a clone on main; the guard reads the last of the two.
- Q: What ends the options? A: the first `--` or `--end-of-options` that is not an option's value.
  Every later word is a refspec, one that starts with a dash too: after
  `git update-ref refs/heads/-x HEAD`, real git moved main for `git push origin -- -x:main`, which
  the guard dropped as an option on main and at b16d799.
- Q: Which destination does a source alone take? A: git's `match_explicit` (remote.c) resolves the
  source and takes its full name, through a symbolic ref; `main-worktree/HEAD` and
  `worktrees/<id>/HEAD` name another worktree's HEAD. Round 1 added the name `git rev-parse
  --symbolic-full-name` printed for the word. Round 2 (gates at 9cb834a) replaces it; see the next
  two answers.
- Q: How does git pick the ref for a source alone? A: `count_refspec_match` (remote.c) tries the
  word under each of git's ref rules (`%s`, `refs/%s`, `refs/tags/%s`, `refs/heads/%s`,
  `refs/remotes/%s`, `refs/remotes/%s/HEAD`). One match under `refs/heads/` or `refs/tags/`, or a
  name spelt in full, beats any number under `refs/remotes/`. With no match, git resolves the word
  itself as a ref: HEAD, `@`, a root ref such as `ORIG_HEAD`, `main-worktree/HEAD`,
  `worktrees/<id>/HEAD`. rev-parse disambiguates another way and printed nothing for
  `git push origin origin` with `refs/heads/origin` a symbolic ref to main beside
  `refs/remotes/origin/HEAD`; real git moved main. The guard now takes every candidate the rules
  give and refuses when any of them ends at the default branch, so it never has to disambiguate.
- Q: How does the guard read the refs, and what does it cost? A: once per push, not once per word.
  One `git for-each-ref --format='%(refname) %(symref)'` gives every symbolic ref with its final
  target (a plain ref names itself, which the text reading already gives). One `git rev-parse
  --git-dir --git-common-dir` gives the git directories, whose root files (each worktree's `HEAD`,
  `ORIG_HEAD`, a one-level name) the guard reads when they start with `ref: `. The shared
  directory's files come first and this worktree's last, so HEAD is this worktree's own. The
  current branch is read once too. 15,000 words with 15,000 tags behind them read in 0.25 s, where
  round 1 took 77 s; 15,000 `:` words read in 0.12 s, where main takes 61 s. An empty or failed
  read adds no candidate and the text reading stands, never weaker than main's.
- Q: Which end marker ends the options? A: only the first `--` or `--end-of-options` that no option
  takes as its value. A later one is a refspec: with `refs/heads/--end-of-options` a symbolic ref to
  main, real git moved main for `git push origin -- --end-of-options`. `_flags` takes the end
  markers as an argument, so the push reads both and gh keeps `--` alone.

## How this fails

1. A destination spelling git reads as main that the rules miss: a case variant on a
   case-insensitive ref store, or a ref store that normalises `//` or `/./`. Probed: `MAIN`,
   `refs/heads//main`, `refs/heads/./main`, `refs/heads/x/../main`, `refs/heads/%6dain`, `main/`
   under real git 2.43 on Linux; none moved main. A remote on a case-insensitive store stays a hole
   (GitHub's refs are case-sensitive).
2. A source that resolves to main locally while the destination is spelt otherwise: a local
   symbolic ref (`refs/heads/x` pointing at `refs/heads/main`) or `main-worktree/HEAD` pushed with
   no colon. git resolves it to `refs/heads/main` as its destination. Round 2 closes it for a ref
   that exists when the guard reads (every candidate of git's rules, the root ref files). A ref
   on the reftable store is read only through `for-each-ref`. A ref the same command writes first
   (`git symbolic-ref refs/heads/x refs/heads/main && git push origin x`), or a HEAD it moves
   (`git checkout main && git push origin HEAD`), stays open and is listed in SECURITY.md.
3. An option that takes the next word hides a word from the guard. The first head claimed a
   swallowed word only adds refusals; the gates showed it false. A taken `--tags` dropped the
   current-branch default (`git push --repo --tags origin` moved main from main), and a taken `x`
   or `origin` read as a refspec suppressed it (`git push origin -o ci.skip`). The guard now skips
   the taken word. What remains: an option a later git adds that takes the next word. The probe's
   valued class crosses each such option and prefix with the words it can take.

## Requirements

- FR-001: `git_push` splits each refspec at its last colon and names `refs/heads/<x>` for a
  destination `x`, `heads/x` or `refs/heads/x`; a destination with a `*` is a full-name pattern.
- FR-002: `:` reads as the pattern `*`; `--all`, `--branches` and their prefixes add
  `refs/heads/*`; any prefix of `--mirror` is a force push; `@` alone resolves to `HEAD`; `--tags` with no
  refspec adds no current branch.
- FR-003: a push is refused when any destination matches `refs/heads/<default>`; deletion keeps the
  "deleting" text, and `:` and `--all` say "pushing to".
- FR-004: the route corpus on main moves no row; new rows hold the acceptance commands.
- FR-005: the generated probe under real bash, a stub git and real git shows 0 holes at the head.
- FR-006: design.md and doors.md name the spellings; the vendored copy matches.
- FR-007: the word an option takes (`-o`, `-vo`, a prefix of `--push-option`, `--repo`,
  `--receive-pack`, `--exec`, `--recurse-submodules`) is no option and no refspec; the last of
  `--tags` and `--no-tags` wins; after the first `--` or `--end-of-options` every word is a refspec.
- FR-008: a refspec with no colon also names the ref each candidate of git's ref rules ends at
  (symbolic refs and root ref files read once per push), so another worktree's HEAD, a root ref
  and a symbolic ref to main meet the door, an ambiguous name too.
- FR-009: the guard's time does not grow with git calls per refspec: 15,000 refspecs read in
  under 1 s.

## Breaking

None. The change refuses pushes that can reach the default branch and that main passed. One
spelling main refused now passes: `--mirror` (or `--all`) taken as the value of `--repo` or `-o`,
which git does not read as an option (`git push --repo --mirror origin feature` pushes feature).

## Assumptions

- git 2.43 refspec rules (remote.c, refspec.c, refs.c). Overturned if the real-git probe shows a
  destination spelling reaching main that the rules miss (it shows none).
- A glob is refused on its destination alone (Clarifications). Overturned if the owner wants
  `refs/heads/f/*:refs/heads/*` style pushes to pass; then the guard must read local refs at call
  time, which a command can change before its push.
- A destination `HEAD` (or empty) keeps main's reading: the current branch. Under real
  git 2.43, `feature:HEAD` from a clone on main left main alone, so the guard over-refuses it there;
  the rule is main's and the item does not ask to change it.
- Runtime lines: 3,199 at the head against 3,178 at main 5a33509 (+21), over the item's budget of
  +4 and its ceiling of 6, under the 3,400 cap. Round 1 ended at +5. Round 2 adds 16: the ref read
  `_sources` (10 lines and 2 blank), the `suppress` import, `REF_RULES`, and two lines in
  `git_push` (the refspec list, read once, and the one ref read per push). The lead chose the
  design for round 2: one ref read per push in place of one git call per word, which the gates
  found let a 94 KB push run 77 s, past the hook's timeout.
- An empty or failed ref read adds no candidate and the text reading stands rather than a refusal
  (security upheld it at 9cb834a). Overturned if a probe finds a source alone that git resolves to
  main from a ref the read cannot see; reftable is the known one (SECURITY.md).
- Every candidate counts, though git takes one strong match over weak ones and fails on two
  strong ones. Over-refusal only: a branch and a tag of one name, one a symbolic ref to main, make
  git fail while the guard refuses. The probe counts such refusals.
- The root ref files are read with `open` only when `is_file` holds, 256 bytes at most, so a FIFO
  or a large file there cannot hold the guard (a test plants a FIFO as `ORIG_HEAD`).
- The force check still reads every word, an option's value and a word after `--` included, so
  `git push -o -f origin feature` stays refused. Over-refusal only, as on main.
- A one-letter name never reads as a `--tags` or `--no-tags` prefix (round 2), so `-n` is the dry
  run it is and `git push --tags -n origin` from main passes. `--t` and `--n` are ambiguous in
  git 2.43 and exit 129. A short `-d` in a cluster (`-vd`) and any prefix of `--delete` from
  `--de` say "deleting".

Rollback: revert the commit; no data or config migrates.
