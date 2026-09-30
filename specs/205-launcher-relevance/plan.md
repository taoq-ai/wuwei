# Implementation Plan: The launcher and irrelevant scripts are never refused as opaque

**Branch**: `205-launcher-relevance` | **Date**: 2026-09-30 | **Spec**: `specs/205-launcher-relevance/spec.md`

## Summary

Fix both causes at the one shared spot, `cli/wuwei/shell.py`, which every script-reading
guard already routes through:

1. `mentions` gains a keyword-only `script=False`. With `script=True` it answers from
   literal tokens only (raw text and quote and backslash stripped text; ANSI-C quoting is not relevant),
   skipping the command-text fallbacks that make every substitution relevant.
2. `script_path` returns `None` when the named file resolves to the wuwei launcher (the
   plugin's own `bin/wuwei` or the path recorded in `.wuwei/executable`). `script_text`
   calls `script_path`, so commit/push, deploy and PR all stop reading the launcher.

The three guards pass `script=True` where they judge script text. `protect_state` gains
`.wuwei/executable` as a protected name, because guards now trust it.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only
**Testing**: pytest, in-process guard tables and in-process `wuwei.commands.hook.run`
**Constraints**: three-state exits, fail closed, no subprocess in the core, no new config keys

## Constitution Check

- One behaviour, one function: relevance stays in `shell.mentions`, script discovery stays in `shell.script_path`. No guard re-parses or re-implements either.
- Test first: every change below has a failing test task ordered before it.
- Fail closed: a relevant script that cannot be parsed still exits 2; an unreadable or invalid pointer only disables pointer recognition.
- Ponytail: no new module, no new helper file, no config. One keyword flag and one private helper.

## Changes

### `cli/wuwei/shell.py`

- `mentions(raw, names, *, script=False)`: skip the `$'` check in script mode; after the literal
  `pattern.search(raw) or pattern.search(unquoted)` check (lines 88 to 93), return False
  when `script` is True. Add a `ponytail:` comment: constructed names in script files are
  not seen; the worktree pre-push hook anchors pushes and branch protection anchors gh
  merges. Default behaviour for command text is unchanged.
- New private `_launcher(path, cwd) -> bool`: True when `path.resolve()` equals the
  resolved plugin launcher `Path(__file__).resolve().parents[2] / 'bin/wuwei'` or the
  resolved first line of `<root>/.wuwei/executable`, where `root` is
  `workspace.find_workspace(cwd)` falling back to `workspace.worktree_workspace(cwd)`.
  Import `wuwei.workspace` inside the function (it does not import `shell`, so no cycle).
  Any `OSError`, `ValueError` or `RuntimeError` while finding the root or reading the
  pointer means "pointer not known", never an exception out of the guard.
- `script_path`: compute `Path(cwd) / target` as today, return `None` if `_launcher` says
  so. Update the docstring ("the wuwei launcher is the CLI, not a script").

### `cli/wuwei/guards/commit_push.py` line 251

`shell.mentions(script, {'git', 'gh'}, script=True) and shell.mentions(script, relevant, script=True)`.

### `cli/wuwei/guards/deploy.py` line 263

`mentions(script, protected, script=True) and mentions(script, DEPLOY_ACTIONS, script=True)`.

### `cli/wuwei/guards/pr.py` lines 339 to 340

Both `shell.mentions` calls on `script` get `script=True`. The early exit at line 334
already uses `shell.script_path`, so the launcher now returns 0 there.

### `cli/wuwei/guards/protect_state.py` `_protected_name` (line 63)

Add `('executable',)` to the tuple of protected `.wuwei` tails next to `('merge.lock',)`.
This covers Write, Edit, MultiEdit, NotebookEdit and Bash redirections, `cp`, `mv`, `rm`
through the existing `_protected` path.

## Must not change

- `mentions` default behaviour for command text (every existing call site other than the
  three script-text calls, including `security.py` and `protect_state.py`).
- `normalize`, `is_opaque`, `script_text` size and type limits, and every guard's handling
  of a relevant script (commit/push still raises "opaque script command", deploy and PR
  still exit 2).
- `protect_state._wuwei_action` and the mcp/drafts CLI match: they already treat any
  `argv[0]` named `wuwei` as the CLI, which is what keeps owner actions refused through
  the launcher path. Test rows lock this in; no code change.
- Scope helpers (`workspace.scope`, `guard_scope`) and out-of-workspace behaviour.
- No new config keys, so no template or `docs/site/configuration.md` change.

## Project Structure

- `cli/wuwei/shell.py`: `mentions` flag, `_launcher`, `script_path`.
- `cli/wuwei/guards/commit_push.py`, `cli/wuwei/guards/deploy.py`, `cli/wuwei/guards/pr.py`: pass `script=True`.
- `cli/wuwei/guards/protect_state.py`: protect `.wuwei/executable`.
- `tests/test_shell.py`: unit rows for script-mode relevance and launcher recognition.
- `tests/test_protect_state.py`: pointer protection rows.
- `tests/test_launcher_relevance.py` (new): the issue's acceptance table through the PreToolUse hook in process, from the workspace root and from `worktrees/ITEM-1`.

## Test fixture notes for the builder

- Workspace: `tmp_path / 'workspace'` with `.wuwei/config.toml` (empty is enough),
  integrity seeded with `fakes.integrity.seed`, `worktrees/ITEM-1` created inside it,
  `WUWEI_WORKSPACE` and `CDPATH` removed with `monkeypatch.delenv`.
- Plugin launcher: `ROOT / 'bin/wuwei'` where `ROOT = Path(__file__).resolve().parents[1]`.
- Recorded launcher: copy `ROOT / 'bin/wuwei'` to `tmp_path / 'previous-plugin/bin/wuwei'`
  and write that path plus a newline to `.wuwei/executable`, so pointer recognition is
  exercised separately from the plugin path. An unrecorded copy at
  `tmp_path / 'other/bin/wuwei'` must still be returned by `script_path`.
- Scripts: `sub.sh` containing `x=$(pwd)\n` and `push.sh` containing
  `git push --force origin main\n`, both `chmod 0o755`, invoked as `./sub.sh` and
  `./push.sh` with the path relative to the session cwd (write them into each cwd used).
- Run the hook as `tests/test_protect_state.py::test_review_hardlink_alias` does:
  monkeypatch `sys.stdin`, call `wuwei.commands.hook.run(SimpleNamespace(event='PreToolUse'))`,
  read `capsys` for the deny JSON. Exit 0 means allowed; refused means return 2 and
  `permissionDecision == 'deny'`.
- Keep `git` and `gh` out of test function names: pytest puts the test name in
  `tmp_path`, and the command text carries that path.

## Deferred

- Constructed guarded names inside script files (`${g}t push`) are not detected by
  PreToolUse; the pre-push hook remains the anchor. Revisit only if a non-push guarded
  action needs a parse-independent anchor.
