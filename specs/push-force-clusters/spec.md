# Feature Specification: a force push in a short option cluster meets the push door

**Feature branch**: `fix/push-force-clusters`
**Item**: push-force-clusters, tier full, goal G-2, issue #1271
**Input**: the push-refspecs security gate (security-b16d799.md) measured that `git push -4f origin x`
passes the force check. At origin/main a53405f, `git_push` matches a force cluster with
`-[a-z]*f[a-z]*`, so a digit or punctuation in the cluster hides the `f`.

## The promise in my words

git's parse-options reads a short option word such as `-qf6` one letter at a time: `-q`, `-f`,
`-6`. Any letter that is `f` sets force, wherever it sits in the cluster, unless a letter before it
takes a value (only `-o` does for git push), which then swallows the rest of the word. The door
must refuse such a push with its force text, on any branch, not only on the default branch. A
cluster with no `f` (`-4`, `-6`, `-q`, `-v`, `-u`, and mixes of them) keeps the verdict it has
today.

The acceptance scenarios, restated:

1. Under real git, on a scratch bare remote whose main holds a commit the clone lacks, each of
   `-4f`, `-f4`, `-6f`, `-qf6` and `-4vf` with the refspec `main` moves main, so git really forced
   it. `guards.bash` refuses each with "force push refused", not with the default-branch text.
2. `-4`, `-6`, `-q`, `-v` and `-u` alone get the verdict they got on main: refused as a push to
   the default branch when the refspec is main (and git itself rejects the non-fast-forward), and
   passed on a feature branch.

Outside: long option prefixes (`--forc`, `--fo`) and `--no-force`, already read before this item;
the `+` refspec; config-steered pushes.

## How this fails

1. The new pattern misses a cluster git still reads as force: `f` after punctuation git accepts,
   for example `-fo=x` (force, then `-o` with the value `=x`), which the old pattern missed too.
   The generated probe crosses every cluster of git push's flags with `f` and `-o` tails.
2. The new pattern loosens a refusal: a word main refused now passes. The pattern must match every
   word the old one matched; the probe's newly passed count and the route corpus show it.
3. The new pattern refuses ordinary pushes: `-o fix` (a push option holding `f`), `-u`, `-4`. The
   pattern reads only a word that starts with one dash, and a separate value word is no cluster.

## Clarifications

- Q: How does git read `-qf6`? A: parse-options (`parse_short_opt`) takes one letter at a time;
  `-q`, `-f`, `-6` each set their flag. Real git 2.54 on a diverged remote: `-4f`, `-f4`, `-6f`,
  `-qf6`, `-4vf`, `-uf` and `-df` move the remote ref (exit 0).
- Q: What about letters after a valued one? A: `-o` takes the rest of the word as its value, so
  `-fo=x` and `-fo.x` force (moved, exit 0), while `-of` and `-o-f` do not (git sent push option
  `f` or `-f`, no force, exit 1 on the non-fast-forward).
- Q: What about letters git does not know? A: git stops with exit 129 before pushing: `-fx`,
  `-xf`, `-Vf`, `-4-f`. Refusing one costs nothing, as the command fails anyway.
- Q: Exact parse or a superset? A: a superset. `-[^-]*f` at the start of a word (no `-` before the
  first `f`) matches every word the old `-[a-z]*f[a-z]*` matched, plus every cluster git forces.
  It still refuses `-of`, as main does. Reading `-o`'s value exactly would loosen a refusal for no
  gain a seat needs.

## Requirements

- FR-1: `git_push` refuses, with the force text, any argument that starts with one `-` and has an
  `f` before any later `-`.
- FR-2: every argument main's pattern matched is still matched.
- FR-3: the vendored `.claude/wuwei/cli/wuwei/guards.py` matches the tree.

## Assumptions

- A word starting with one dash after `--` is a refspec to git; the door reads every argument, as
  main did, so `git push origin -- -4f` is refused. Overturned if a seat needs a ref named like a
  flag; none is known.
- Runtime cost is 0 lines (the same line changes). Overturned only by review asking for a helper.
