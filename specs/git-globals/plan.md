# Implementation plan: git-globals

**Spec**: `specs/git-globals/spec.md`
**Item**: git-globals, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main d1c3d79 holds
  2,996 after records (#1116). This item's budget is +2; gh-args (+3) follows, so the aim is 0.
- The git branch of `guards.bash` walks words starting with `-` and takes two words only for `-C`,
  `-c`, `--git-dir` and `--work-tree`. The records `git clean` rule reads `rest[:i:2]` and
  `rest[1:i:2]` as the option and `-C` dir pairs, so any option other than `-C` refuses a clean.

## Design

1. `GIT_OPTS`, one regular expression matched on `word\0next\0`: first a steering `-c` or
   `--config-env` (`[=\0]` then `alias.`, `remote.`, `branch.`, `url.`, `include`, or
   `push.default`, the section in any case), then a valued option (named group `pair`), then the
   one-word options and `=` forms. `\0` never occurs in an argv word, so `[^\0]*\0` reads one whole
   word.
2. The loop keeps walking words that start with `-` (so the clean rule sees the same `i`), and
   takes two words when `pair` matched. It records the first odd option: the two words of a steering
   `-c`, or an unknown word.
3. After the loop: refuse when there is a steering option, or an unknown one and `push` is a word of
   the command. `'push' in rest` runs once, after the loop, so the walk stays linear.
4. Lines: the regex takes 4 and the refusal 2; the loop keeps its 3. Tighten 4 existing lines: the
   `origin` docstring becomes a def comment, the `segments` flush and the `_unwrap` redirect step
   each become one line, and the `merge_door` docstring one line.
5. Re-vendor `.claude/wuwei/cli/wuwei/guards.py` byte-identical; update SECURITY.md (the alias gap
   closes, config before the call stays).

## Constitution check

- Stdlib only, runtime net 0 (2,996): pass.
- Test first: 22 red before the change, all green after.
- Simplest: one regex and one refusal, no new function.
