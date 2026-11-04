# Implementation plan: push-force-clusters

**Spec**: `specs/push-force-clusters/spec.md`
**Item**: push-force-clusters, tier full, goal G-2, issue #1271

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 4,000 lines; main a53405f holds
  3,879. The item's estimate is +1 with a budget of 2.
- `git_push` (cli/wuwei/guards.py) refuses a force push before it reads refspecs: any argument
  starting with `--force`, any prefix of `--mirror`, or a word matching `-[a-z]*f[a-z]*`.

## Design

1. Replace `re.fullmatch(r'-[a-z]*f[a-z]*', a)` with `re.match('-[^-]*f', a)`: a word that starts
   with one dash and holds an `f` before any later dash. It is a superset of the old pattern and
   of every cluster git forces, digits and `-o` tails included.
2. Copy guards.py to `.claude/wuwei/cli/wuwei/guards.py`.
3. Route corpus: five rows naming the item (three push, two pass).

## Proof

- Tests first in tests/test_guards.py: unit cases on a feature branch (refused with the force
  text, in both positions), cases with no `f` that pass, and real git on a diverged remote main.
- The generated probe `specs/push-force-clusters/probe.py` (cluster, spelling, operator, plain
  and value classes) under real bash with a stub git, at main and the head.
- The route corpus read through main's and the head's guards, with its sha256.
- Mutants of the pattern, applied to both copies, one at a time.

## Constitution check

Test first, stdlib only, the shortest diff (one line), no new abstraction. Runtime +0 lines.
