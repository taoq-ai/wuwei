# Feature Specification: the push door reads each refspec's destination the way git does

**Feature branch**: `fix/push-refspecs`
**Item**: push-refspecs, tier full, goal G-2
**Input**: the git-globals security gate found, and guards.bash on main confirms, that
`git push origin feature:heads/main`, `git push origin :`, `git push --all origin` and
`git push origin 'refs/heads/*:refs/heads/*'` pass the push door while `feature:main` and
`feature:refs/heads/main` are refused. Each moves main under real git 2.43.

## The promise in my words

Round 3 (the promise the owner approved on 2026-10-20, after the gates at aa63d3b):

1. The push door names the destination of each refspec as git 2.43 does. git splits a refspec at
   its last colon and expands the destination with its ref rules, so `main`, `heads/main` and
   `refs/heads/main` all name the default branch. A leading `+` is a force push and keeps its own
   refusal.
2. A push that can reach the default branch without naming it is refused too: the matching
   refspec `:`, `--all` and `--branches` (any unique prefix git reads, such as `--al`), and a glob
   refspec whose destination pattern can match `refs/heads/<default>`.
3. A source with no colon goes where git itself sends it. The door counts every candidate git's
   ref rules find among the symbolic refs one `git for-each-ref` lists. It also counts the ref one
   batched `git -c core.warnAmbiguousRefs=false rev-parse --symbolic-full-name --revs-only
   --end-of-options <words>` resolves each such word to: root refs in any spelling, symlinks,
   nested names, another worktree's refs, any ref store. The `tag` keyword, negative refspecs
   (`^x`) and globs stay out of the batch. Round 2's own reader of root ref files is removed.
   Round 4 (gates at 457f6a8, as the coordinator directed): a push of a ref named `--` is refused,
   in place of asking `main-worktree/--`, because git reads that root ref per worktree.
4. When git cannot run either read, or does not finish it in 5 s, the door stays shut.
5. The existing refusals keep their text: `--mirror` (in any prefix git reads, such as `--mirr`) is
   a force push; an explicit default branch is "pushing to" or "deleting" it.

The acceptance scenarios, restated:

1. In a scratch bare remote with a clone holding main and feature, real git runs
   `feature:heads/main`, `:`, `--all` and `'refs/heads/*:refs/heads/*'`; each moved main. The same
   commands, with the remote read as the real origin (not a scratch folder), are refused by
   guards.bash.
2. A generated probe of destination spellings (main, heads/main, refs/heads/main, `+`, globs, `:`,
   `--all`, `--branches`, `--tags`) crossed with sources runs under real git against a scratch
   bare remote; guards.bash, reading each with the remote as a non-scratch one, refuses every
   command that moved main (0 holes), and pushes that cannot reach main pass.
3. A clone c and a linked worktree w hold a ref git resolves to main, written before the call in
   each form the security gate found: a `ref:` root file with no space, a tab or 300 spaces; a
   symlink root ref; a nested name under the git directory; another worktree's per-worktree ref
   named through `main-worktree/` or `worktrees/<id>/`; a lowercase name git reads from the common
   directory over w's own. Every `git push origin <name>` from c or w that moved main is refused,
   and the generated rootfile class reports generated, ran and 0 holes.
4. A word git push accepts but rev-parse cannot resolve (`tag v1`, `^nope`, a glob, a branch named
   `--`) before a root ref to main does not hide it, nor does a root ref named `--` or `-x`.
5. A push of 15,000 tag words makes as many git calls as a push of one word, with no clock in the
   test; a rev-parse or for-each-ref that does not finish in 5 s refuses `git push origin feature`.
6. `git push origin feature`, `feature:feature`, `--tags origin`, `tag v1`,
   `'refs/heads/f/*:refs/heads/f/*'`, and `HEAD` from a linked worktree on feature pass.

Outside (the item's Outside): config-steered pushes (git-globals: `remote.*.push`, `push.default`,
`branch.*.merge`); refs or HEAD the same command writes before its push; a relative `git -C`
(push-moved-head); force digit clusters (push-force-clusters). Pushes git runs itself (submodule
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
  target (a plain ref names itself, which the text reading already gives). Round 2 then read the
  root ref files itself; the security gate at aa63d3b found 136 holes in 200 generated commands,
  root refs git reads in forms that reader missed (`ref:` with no space or other whitespace, a
  symlink, a nested name, another worktree's refs, and a lowercase name read from the wrong
  folder). Round 3 asks git instead: one `git -c core.warnAmbiguousRefs=false rev-parse
  --symbolic-full-name --revs-only --end-of-options <words>` prints the full name git resolves
  each colon-less word to, through the same ref code git push uses. The guard opens no file in the
  git directory. One word and 15,000 words make the same git calls. At the head, 15,000 tag words
  read in 1.2 to 1.3 s on loose refs and 0.4 s packed (git 2.54, load 6 to 7 on 10 cores), where
  round 1 took 74 s.
- Q: Why keep for-each-ref when rev-parse resolves the word? A: rev-parse takes the first rule
  that matches, a root ref before `refs/heads/<name>`; git push matches the word among the local
  refs first. With a root `ZZ` naming feature beside `refs/heads/ZZ`, a symbolic ref to main, git
  pushes main while rev-parse names feature. The door counts both answers.
- Q: Which words stay out of rev-parse's batch? A: rev-parse with `--revs-only` prints nothing for
  any word after the first one it cannot resolve. git push sends nothing when one of its sources
  does not resolve (git 2.54: `git push origin nope main` exits 1 and leaves main), so such a word
  cannot be pushed either. Three kinds of word git push takes that rev-parse cannot resolve stay
  out: the `tag` keyword (the tag name after it goes in), a negative refspec `^x` and a glob; a
  refspec with a colon names its destination and stays out too. The lead's sketches that kept one
  of them in the batch each left a hole on it. The fourth is `--`, which ends rev-parse's revisions
  even after `--end-of-options`. Round 3 asked a root ref named `--` as `main-worktree/--`, but git
  reads that name per worktree (refs.c pseudoref syntax takes `-`), so from a linked worktree git
  read `.git/worktrees/<id>/--` and the guard the common one (gates at 457f6a8). git branch,
  switch and tag refuse the name, so only plumbing writes it: round 4 refuses every push with a
  `--` refspec.
- Q: What does the door do when git cannot read the refs? A: it refuses the push. `_git` takes the
  value a git that cannot run or finish in 5 s gives; the two ref reads ask for `None`, and
  `git_push` refuses ("git could not read the refs in 5 s, so the door cannot tell whether it
  reaches the default branch"). A git that runs and answers "not a repository" gives `''`, and the
  text reading stands as before. This is the module's rule that a door which cannot read its
  evidence stays shut. A FIFO named as the pushed word holds git for 5 s, and the door refuses.
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
2. A source that resolves to main locally while its name reads otherwise: a symbolic ref, a root
   ref in any spelling, a symlink, a nested name or another worktree's ref, pushed with no colon.
   git resolves it to `refs/heads/main` as its destination. Round 2 read the root ref files itself
   and missed forms git reads (gates at aa63d3b). Round 3 asks git: rev-parse resolves each word
   through git's own ref code on any ref store, and for-each-ref's candidates cover the match git
   push takes over rev-parse's. Round 3's own lookup of a root `--` read the wrong worktree (gates
   at 457f6a8); round 4 refuses a push of `--` instead. What stays open: a word git push accepts
   that stops rev-parse, beyond the three kept out of the batch and `--` (the stopper class tries 41
   words, and git 2.43 is unmeasured here); a ref the same command writes first
   (`git symbolic-ref refs/heads/x refs/heads/main && git push origin x`), or a HEAD it moves
   (`git checkout main && git push origin HEAD`), listed in SECURITY.md.
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
- FR-008: git resolves each source alone. A refspec with no colon names the target of each
  candidate of git's ref rules among the symbolic refs one `for-each-ref` lists, and the full name
  one batched `rev-parse --symbolic-full-name --revs-only` (with `core.warnAmbiguousRefs=false`,
  after `--end-of-options`) prints for it. The `tag` keyword, negative refspecs and globs stay out
  of the batch; a push with a `--` refspec is refused as a push to the default branch (round 4).
  The guard opens no file in the git directory.
- FR-009: the git calls per push do not grow with the refspecs (one word and 15,000 make the same
  calls); a `for-each-ref` or `rev-parse` that cannot run or finish in 5 s refuses the push.

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
- Runtime lines: 3,369 at the head against 3,351 at main 5b5084b (+18), under main + 21 and the
  3,400 cap. Round 3 drops the root file reader (6 lines) and the `suppress` import, and adds the
  batch: the words line and its comment, and the refusal (2 lines) in `git_push`. Round 4 adds no
  line: the `--` check joins the `--all` line, and the `main-worktree/--` lookup goes.
- A push with a `--` refspec is refused, whatever `--` names (round 4, the security gate's first
  fix, chosen by the coordinator over asking `worktrees/<id>/--`). git branch, switch and tag
  refuse the name, so only plumbing writes a branch or root ref `--`. Over-refusal only: a push of
  such a branch that git sends elsewhere is refused too. This replaces the approved promise's
  "`--` is asked last as `main-worktree/--`".
- git push sends nothing when one of its sources does not resolve, so the words rev-parse skips
  after one it cannot resolve cannot be pushed. Measured on git 2.54 (`git push origin nope main`
  and `nope ZZ` exit 1, main unmoved). Overturned if a probe under git 2.43 finds a word git push
  accepts that stops rev-parse, beyond `tag`, `^x`, globs and `--`.
- `core.warnAmbiguousRefs=false` makes rev-parse take its first rule's match, a root ref before
  `refs/heads/<name>`. A root file naming main beside a branch of the same name at another commit
  is refused, though git pushes the branch (git 2.54: refused, main unmoved). Over-refusal only.
- A git that cannot run or finish a ref read in 5 s refuses the push, where round 2 let the text
  reading stand. A git that runs and answers "not a repository" still gives the text reading.
  Overturned if a push in a large repository takes git over 5 s to read; the lead's sketch read
  60,000 loose tag words in 3.5 to 3.8 s (git 2.54).
- Every candidate counts, though git takes one strong match over weak ones and fails on two
  strong ones. Over-refusal only: a branch and a tag of one name, one a symbolic ref to main, make
  git fail while the guard refuses. The probe counts such refusals.
- The force check still reads every word, an option's value and a word after `--` included, so
  `git push -o -f origin feature` stays refused. Over-refusal only, as on main.
- A one-letter name never reads as a `--tags` or `--no-tags` prefix (round 2), so `-n` is the dry
  run it is and `git push --tags -n origin` from main passes. `--t` and `--n` are ambiguous in
  git 2.43 and exit 129. A short `-d` in a cluster (`-vd`) and any prefix of `--delete` from
  `--de` say "deleting".

Rollback: revert the commit; no data or config migrates.
