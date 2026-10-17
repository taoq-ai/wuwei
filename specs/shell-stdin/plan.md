# Implementation plan: shell-stdin

**Spec**: `specs/shell-stdin/spec.md`
**Item**: shell-stdin, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, budget 3,000 lines. Main 86135fa holds
  2,976 after free-lines-4 (#1112); this item's budget is +2.
- `guards.segments` pre-lexes the command with one `re.sub` that keeps quote spans and drops an fd
  number glued before `<` or `>`. `_unwrap` reads redirects, wrappers and a shell's `-c` body.
- `guards.bash` refuses a command whose segments hold `UNREAD` when its raw text matches a
  `DOOR_WORDS` entry.

## Design

1. In the `re.sub` pattern, the fd alternative becomes `([0-9]+|\{[A-Za-z_]\w*\})(?=[<>])` with the
   same lookbehinds. The replacement drops a match whose first character is a digit or `{`; quote
   spans start with a quote and escapes with a backslash, so neither is dropped.
2. `_unwrap`'s last line appends `UNREAD` when the program is in `SHELLS`. The `-c` branch above
   it returns first, so only shells without a readable body get it.

Both edits change existing lines: +0 runtime lines.

## Verification

- Tests first in `tests/test_guards.py`: named-fd pushes meet the push door, shells fed a door
  command are refused, no-door shapes pass, infra and leak checks see the program after a named fd,
  and real bash with a stub `git` runs the push in each acceptance shape.
- The lead's generated probe, and an extended probe (shell positions, infra and leak), run under
  real bash at main and head from copies of the tree.
- The route corpus dumped at main and head; verdicts and reasons compared.
- Full suite with the vendored copy refreshed.

## Constitution check

Stdlib only, no new door, no new config key, test first, within the line budget.
