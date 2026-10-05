# Implementation Plan: A disposed item never blocks the close through a measurement

**Branch**: `517-close-parked` | **Spec**: `spec.md`

## Summary

Fix the shared spot, `closing.unresolved`, so a measurement failure on a parked or carried
item becomes a printed fact instead of exit 2; every caller (`close`, `close --widget`,
`closing.check`, the new `close --why`) benefits. Decouple the retro launch in
`commands/close.py` from measurements. Add one record writer for gone worktrees, used by
a new `doctor --fix` entry and a new `worktree remove` subcommand.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Real git in `tmp_path` for the close and doctor
tests; `tests/fakes/vcs.py` gains the two new reads for in-process tests.

## Constitution Check

Exit codes 0/1/2 kept (open-item and unreadable-ledger failures still exit 2). Core does
not import subprocess: new git calls live in `adapters/vcs/git.py`. The new event kind is
reserved in `commands/event.py`. No config added. Pass.

## Changes

### `cli/wuwei/closing.py`, `unresolved(root, rows, open_items=None, notes=None)`

- In the decisions loop, keep the seat outcome's reason: change `dispositions` from a set
  to a dict `{'parked DIV-1': '<reason or empty>'}` (reason parsed from `fields['Context']`
  after `Reason: `). Membership checks at `:208` keep working on dict keys.
- In the item loop compute once `disposed` = `'parked'` / `'carried'` from the PR
  disposition or the dict; keep the open-item finding for `not disposed and not merged`.
- Measurement block (`:223-236`): skip when `tree is None` (unchanged; covers
  `worktree_gone`). When disposed: if `not (root / tree).is_dir()` record the fact
  `worktree missing`; otherwise run the measurement inside `try` and on `watch.ERRORS`
  record the fact with `str(exc)`. A fact is appended to `notes` (when given) as
  `f'{name}: {disposed}{f" ({reason})" if reason else ""}, unmeasured: {why}'` and does not
  touch `code`. Not disposed: unchanged (exit 2 on failure).
- Disposed items with no measurement problem also add a plain `notes` line
  `f'{name}: {disposed}[ (reason)]'` so `--why` and the close output list every item.

### `cli/wuwei/commands/close.py`

- `register`: add `--why` (store_true): "Print what close still needs per item; writes
  nothing".
- `run`, `--why` branch: `names, notes = [], []`; `code, reason = closing.unresolved(...,
  open_items=names, notes=notes)`; print `reason` then each note; return `code`. No state
  write. Place it beside the `--widget` branch.
- `run`, close branch: call `unresolved` with `open_items=names, notes=notes`; launch
  `steward.run(root, trigger='close')` when `not names and code < 2` (was `code == 0`), then
  `closing.check` as today when `code < 2`. Print the notes after `reason`.

### `adapters/vcs/git.py` and `tests/fakes/vcs.py`

- `branch_head(repo, branch, root=None)`: `rev-parse --verify --quiet refs/heads/<branch>`
  through `_run` with `_revision`; return `{'sha': <sha> or None}` (missing ref is None, not
  an error; use `_run(..., missing=True)` if that is its not-found mode, else catch the
  exit 1 of `--quiet`).
- `worktree_remove(repo, path, root=None)`: `worktree remove -- <path>`; return
  `{'path': path}`. Mirror `worktree_add` (`:354`).
- Fakes: the same two functions with canned results.

### Shared record writer: `cli/wuwei/workspace.py`

- `mark_worktree_gone(root, item, vcs, repo)`: read `items[item]['worktree']`, read
  `vcs.branch_head(repo, item.lower())['sha']`, then one `state._write_state(...,
  reserved=False, kind='worktree.gone', payload={'item', 'path', 'last_commit'})` setting
  `worktree=None, worktree_gone={'path', 'branch', 'last_commit'}`. Placed next to
  `create_worktree` (`:764`). Used by both producers below; nothing else.

### `cli/wuwei/commands/doctor.py`

- `_gone_worktrees(root)`: sorted item names whose `worktree` is a non-empty str and
  `(root / tree)` does not exist.
- `_day`: one row, like `trace decisions` (`:575-580`): `_row('day', 'worktrees', 'warn',
  f'{", ".join(names)} recorded but gone', 'wuwei doctor --fix', apply='worktree-gone')`;
  read errors give an `unmeasured` row.
- `FIXES['worktree-gone'] = ('mark removed worktrees gone', _gone_preview, _gone)`;
  preview lists `<item>: <path> gone` and returns the names as token; apply re-reads,
  prints `changed since the preview; nothing applied` and returns 1 on mismatch, else calls
  `workspace.mark_worktree_gone` per item (repo from `config['repos']`, single repo rule as
  `worktree add`). Update the test that pins the FIXES allow list.

### `cli/wuwei/commands/worktree.py`

- Add `remove <item> [--repo]`: resolve the repo exactly as `add` does (extract the
  existing lines into a tiny `_repo(config, name)` only if both branches need it), call
  `vcs.worktree_remove(repo, root / item_worktree)` when the path exists, then
  `workspace.mark_worktree_gone`. Unknown item or no record: exit 1 with the reason.

### `cli/wuwei/commands/event.py`

- Reserve `'worktree.gone': 'wuwei worktree remove or wuwei doctor --fix'`.

## Must not change

- Exit 2 for measurement failures on open items, for unreadable decision ledgers, and for
  failures outside the item loop.
- The pushed-branch-without-PR finding for measurable items (carried or open).
- `closing.retro`, `closing.check`'s other checks, the steward itself, `report.md`,
  `next`, the board: they only read `worktree`, which becomes null.
- The `trace-decisions` fix and every other FIXES entry.

## Project Structure

Files touched: `cli/wuwei/closing.py`, `cli/wuwei/commands/close.py`,
`cli/wuwei/workspace.py`, `cli/wuwei/commands/doctor.py`, `cli/wuwei/commands/worktree.py`,
`cli/wuwei/commands/event.py`, `adapters/vcs/git.py`, `tests/fakes/vcs.py`, docs line for
`close --why` and `worktree remove` in the guide/command reference where `close` is listed.
Tests: `tests/test_close_parked.py` (new), plus additions to the existing doctor, worktree
and git adapter test files.
