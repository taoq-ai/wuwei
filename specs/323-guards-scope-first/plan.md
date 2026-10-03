# Implementation Plan: Outside a WUWEI workspace every hook does nothing

**Branch**: `323-guards-scope-first` | **Date**: 2026-10-03 | **Spec**: `specs/323-guards-scope-first/spec.md`

## Summary

One scope gate in the dispatcher, `run` in `cli/wuwei/commands/hook.py`, placed right
after the existing root computation and before `env.load`, `discover()` and every guard.
Out of scope, `run` returns `CLEAN` and prints nothing. The gate reuses the root `run`
already computes (cwd plus file targets through `workspace.guard_scope`), the
`WUWEI_WORKSPACE` selection, and `workspace.scope` on the call's literal path words so a
Bash command that names a workspace path from an outside cwd stays guarded (design 9.1).
No guard module changes.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only
**Testing**: pytest; in-process `wuwei.commands.hook.run` with stdin replaced (as `tests/test_hooks.py` `replay` does)
**Constraints**: three-state exits; no new module, config key or dependency; hook budget under `WUWEI_BENCH=1` must not grow

## Constitution Check

- One behaviour, one function: scope for the hook is decided once, in `hook.py`; guards keep their own checks for direct callers. Scope itself stays in `workspace.scope`; the gate only chooses which paths to ask about.
- Test first: every change has a failing test task ordered before it (tasks.md).
- Fail closed where it matters: a workspace marker that raises while scoping counts as in scope, so guards report it exactly as today. A malformed payload is still refused before the gate.
- Ponytail: one function of about fifteen lines, one helper moved (not copied). No per-guard edits.

## Changes

### `cli/wuwei/commands/hook.py`

1. Add `import os` at the top.
2. New function, below `run`:

   ```python
   def reaches_workspace(payload, root):
       """Design 9.1 before any guard parses: the cwd or a file target (root), a
       WUWEI_WORKSPACE selection, or a literal path word of the call lies in, is, or
       directly contains a workspace or managed worktree."""
   ```

   Behaviour, in order:
   - `root is not None` or `'WUWEI_WORKSPACE' in os.environ`: return True.
   - Collect words: `tool_input['notebook_path']` (the one file key `guard_scope` does not
     read), `os.environ.get('GIT_DIR')`, `os.environ.get('GIT_WORK_TREE')`, and, when
     `tool_input['command']` is a string, the set of pieces from
     `re.split(r'''[\s;&|()<>'"`=\\]+''', command)` with a leading short option removed
     (`re.sub(r'^-\w(?=[~./])', '', word)`, so `-C/x` gives `/x`). Splitting on `=` turns
     `--git-dir=/x` and `GIT_DIR=/x` into `/x`; stripping quotes exposes paths inside
     `sh -c '...'` and `eval "..."`.
   - For each non-empty word: `path = (cwd / Path(word).expanduser()).resolve()` with
     `cwd = Path(payload['cwd']).resolve()`; skip the word on `OSError`, `ValueError` or
     `RuntimeError` (unknown `~user`, loops). Skip a word without `/` whose path does not
     exist (a bare word that is not a directory entry of the cwd cannot be a target; the
     cwd's own chain is already known to be outside).
   - Return True when `workspace.scope(path) is not None`, or `path.is_dir()` and
     `workspace.contains_workspace(path)`. Any exception from these two calls returns
     True (a symlinked `.wuwei`, an invalid anchor or a bad config is WUWEI-shaped; the
     guards report it as today).
   - Otherwise return False.
   - Add a `ponytail:` comment: words are checked one by one with `workspace.scope`, each
     walking its parents; dedupe the parent walk if a large heredoc shows up in the
     latency figures. Nonliteral targets (`cd $P`, bare `cd`, `cd -`, CDPATH) are not
     resolved; the code host and the worktree pre-push hook are the anchors (design 4.5).
3. In `run`, after the block that sets `root` (current lines 36 to 43) and before
   `if root is not None: env.load(root)`, add:

   ```python
   if not reaches_workspace(payload, root):
       return CLEAN
   ```

   It sits inside the existing `try`, so an unexpected error still refuses as today.

### `cli/wuwei/workspace.py`

Move `_contains_workspace(path)` from `cli/wuwei/guards/protect_state.py` (lines 232 to
238) unchanged into `workspace.py` as public `contains_workspace(path)`, next to `scope`.
It needs only `os`, already imported.

### `cli/wuwei/guards/protect_state.py`

Delete `_contains_workspace` and call `contains_workspace` from `wuwei.workspace` at line
223 (extend the existing `from wuwei.workspace import worktree_workspace`). No other edit.

### `docs/site/security.md` line 11

Replace "Outside that scope, guards return 0." with "Outside that scope, every hook returns
0 before any guard reads or parses the call; a command that names a workspace path
literally is in scope." Keep the rest of the paragraph.

## What must not change

- Every guard module's direct-call verdicts (`tests/test_commit_push.py`,
  `tests/test_pr_guards.py`, `tests/test_protect_state.py`, `tests/test_deploy.py` and
  the rest pass unedited), including their own scope and fail-closed paths.
- In-scope hook flow: when `root` is set the gate returns True on its first line; env
  loading, discovery selection, shadow mode, refusal recording and the SessionStart and
  Stop output contracts are untouched.
- Malformed payload handling (JSON errors and `validate`) stays before the gate.
- `guards/__init__.py`, `discover()` and `MODULES`: unchanged (tests replace `discover`
  with zero-argument stubs; the gate must sit in `run`, before the call).
- `workspace.guard_scope` and `workspace.scope` semantics: unchanged (many guards call
  them).

## Tests

New file `tests/test_scope_first.py`, in process through `wuwei.commands.hook.run`:

- `outside` fixture: `tmp_path / 'host/home/outside'` (no `.wuwei` above it; three
  levels deep so rows with `..` or `../..` stay inside `tmp_path` and never reach sibling
  test directories that hold workspaces), `HOME` set to it, `WUWEI_WORKSPACE`, `GIT_DIR`,
  `GIT_WORK_TREE` and `WUWEI_SEAT_ROLE` removed.
- `hook(event, payload)`: `monkeypatch` stdin with the JSON, call
  `run(SimpleNamespace(event=event))`, return code plus captured stdout and stderr.
- `TRIAL`: the two trial commands from the spec (heredoc body mentions `gh pr view` and
  `git status` in strings).
- `SHAPES`: one row per "could not run" shape: `git push "`, `gh pr merge "`, `ls ~/x`,
  `cd ~nosuchuser/x && git push`, `git push $(git rev-parse HEAD)`, a backtick form,
  `for r in a b; do git -C $r push origin main; done`, `if true; then gh pr merge 9; fi`,
  `cat <<'EOF'\ngit push --force\ngh pr merge 9\nEOF`, `git symbolic-ref refs/remotes/origin/HEAD`,
  `gh foo bar`, `echo x > .wuwei/days/2026-10-03/state.json`, `rm -rf .wuwei`.
- `harvested_rows()`: import `test_commit_push`, `test_pr_guards`, `test_deploy`,
  `test_protect_state`, `test_owner_actions`, `test_seat_command_forms`,
  `test_pr_ownership` (guard tables) and `test_shell` (bypass rows); for every
  module-level function's `pytestmark` parametrize marks, split the argnames, unwrap
  `pytest.param` values (`.values`), and take the string values of the `command`,
  `script`, `form`, `wrapper` and `operation` arguments; fill `{...}` placeholders with
  `format_map` over a `dict` subclass whose `__missing__` answers every key with a path
  under the outside directory, keeping the raw row when formatting raises. Deduplicate.
  On main today this yields about 860 unique rows from the guard modules alone; assert at
  least 500 so a refactor of the tables cannot empty the probe.
- The rows run as harvested. A row naming a host directory that directly contains a
  workspace on the test machine would be in scope by design; none of today's rows names
  a bare host directory such as `/tmp`, so no filtering is planned.
- `assert_outside_clean(rows, outside)`: helper used by the tests and by the mutation
  harness; for each row asserts exit 0, empty stdout and stderr, and no `.wuwei` created.

Mutation harness (`tests/test_guard_mutation.py`): add
`test_disabling_scope_gate_makes_outside_probe_red` (replace
`wuwei.commands.hook.reaches_workspace` with `lambda *args: True` and expect
`assert_outside_clean(TRIAL, ...)` to raise `AssertionError`), register it in
`SPECIAL_TESTS` under `('wuwei.commands.hook', 'reaches_workspace')` and add that key to
the `required` set in `test_special_policies_have_mutation_probes`.

## Complexity Tracking

None. Skipped: deduplicating the parent walk across words (add if a heredoc-heavy call
shows in the latency figures), resolving nonliteral `cd` targets from outside cwds
(design 9.1 leaves them to the code host and pre-push hook).
