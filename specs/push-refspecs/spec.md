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
  and `--m`. git 2.43 has no `--branches` (added later as a synonym of `--all`); the guard refuses
  it and its prefixes, as the promise asks.
- Q: Where may `--all` stand? A: anywhere: parse-options reads options before and after the remote
  and refspecs. The guard on main read `git push --all origin` as a push of the current branch, so
  it was refused only when the current branch was main, whatever the option order.
- Q: What does the guard do with quoting and `*`? A: shlex reads single quotes, double quotes and a
  backslash as bash does, so the glob word the guard reads is the word git gets; bash leaves an
  unquoted glob that matches no file as typed. `$'..'` stays unreadable and is refused by the
  raw-text rule. The scratch exception's plain word class (`[\w./=@:+-]`) excludes `*` and quotes,
  so a quoted or glob refspec never passes through it: the door decides it as for any remote.

## How this fails

1. A destination spelling git reads as main that the rules miss: a case variant on a
   case-insensitive ref store, or a ref store that normalises `//` or `/./`. Probed: `MAIN`,
   `refs/heads//main`, `refs/heads/./main`, `refs/heads/x/../main`, `refs/heads/%6dain`, `main/`
   under real git 2.43 on Linux; none moved main. A remote on a case-insensitive store stays a hole
   (GitHub's refs are case-sensitive).
2. A source that resolves to main locally while the destination is spelt otherwise: a local
   symbolic ref (`refs/heads/x` pointing at `refs/heads/main`) pushed with no colon. git resolves
   it to `refs/heads/main` as its destination. That is a ref written before the call (Outside),
   recorded as a candidate.
3. An option that takes the next word hides `--all` or a refspec from the guard: `-o --all`,
   `--repo origin`. The guard reads every word that starts with `--` as a possible `--all` or
   `--mirror`, and every word without a dash as a possible refspec, so a swallowed word only
   adds refusals. Probed with `-o x` in each position.

## Requirements

- FR-001: `git_push` splits each refspec at its last colon and names `refs/heads/<x>` for a
  destination `x`, `heads/x` or `refs/heads/x`; a destination with a `*` is a full-name pattern.
- FR-002: `:` reads as the pattern `*`; `--all`, `--branches` and their prefixes add
  `refs/heads/*`; any prefix of `--mirror` is a force push.
- FR-003: a push is refused when any destination matches `refs/heads/<default>`; deletion keeps the
  "deleting" text, and `:` and `--all` say "pushing to".
- FR-004: the route corpus on main moves no row; new rows hold the acceptance commands.
- FR-005: the generated probe under real bash, a stub git and real git shows 0 holes at the head.
- FR-006: design.md and doors.md name the spellings; the vendored copy matches.

## Breaking

None. The change only refuses pushes that can reach the default branch and that main passed.

## Assumptions

- git 2.43 refspec rules (remote.c, refspec.c, refs.c). Overturned if the real-git probe shows a
  destination spelling reaching main that the rules miss (it shows none).
- A glob is refused on its destination alone (Clarifications). Overturned if the owner wants
  `refs/heads/f/*:refs/heads/*` style pushes to pass; then the guard must read local refs at call
  time, which a command can change before its push.
- Runtime lines: 3,012 at the head against 3,011 at main dc39cae (+1), inside the item's budget
  (+4, ceiling 6). free-lines-5 is no longer needed: the cap is 3,400.

Rollback: revert the commit; no data or config migrates.
