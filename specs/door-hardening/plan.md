# Implementation Plan: the fail-closed check reads the doors from one table, through quotes, and covers the leak check

**Branch**: `claude/door-hardening` | **Spec**: `specs/door-hardening/spec.md`

## Summary

Add `guards.DOORS` and read it in `guards.pre_tool` and `hook.door()`. Make `hook.door()` read the
command with quotes and backslashes removed, count network programs and every MCP tool, and count
`apply_patch` as an edit. Move `codex()` inside `handle`'s try. Tighten the assignment test in
`_unwrap` to `NAME=value`.

## Technical Context

Python 3.11 stdlib, pytest. Runtime is 2,939 of 3,000 lines on main 1620583; the estimate is +5.

## Constitution Check

- I. Stdlib only: yes, `re` only.
- II. Evidence over steps: no change to what the doors read.
- III. An auditor: no new door; the existing doors fail closed in more shapes.
- V. Test first: every new test ran red before the change.
- VI. Budgets: no config key; runtime +2 lines.

## Design

- `cli/wuwei/guards.py`: `DOORS = {'edit': (...), 'merge': (...), 'create': (...)}` beside
  `DOOR_WORDS`. `pre_tool` tests `tool in DOORS['edit']`, `tool.endswith(DOORS['merge'])` and
  `tool.endswith(DOORS['create'])`; auto-merge is `DOORS['merge'][1]`. `_unwrap` skips an argument
  only when `re.match(r'[A-Za-z_]\w*=', a)`.
- `cli/wuwei/hook.py`: `handle` looks up the handler, then calls `handler(root, codex(payload))`
  inside the try; the except branch passes the raw payload to `door()`. `door()` strips
  `'`, `"` and `\` from the command, matches `DOOR_WORDS`, and matches a `NETWORK` name as a program
  word: at the start or after whitespace, `;`, `&`, `|`, `(`, a backtick or `/`, and followed by
  whitespace or the end. Every `mcp__` tool, `guards.DOORS['edit']` and `apply_patch` are doors.
- `SECURITY.md`: one paragraph on what a failing guard refuses.
- Tests: `tests/test_hook.py` (quoted door words and network calls with `guards.bash` raising, MCP
  tools with `guards.pre_tool` raising, Read and Glob still open, the table test), `tests/test_codex.py`
  (malformed apply_patch), `tests/test_guards.py` (`env /opt/a=b/git push origin main`).
- Re-vendor `.claude/` with `setup.vendor('.')`.

## Rollback

Revert the PR's single commit; no data or config changes, so the revert restores the old checks.
