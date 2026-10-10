# Implementation Plan: a new worktree fetches first and branches from origin/<base>

**Branch**: `681-worktree-from-origin` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One shared spot: the git adapter's `worktree_add` fetches `<remote> <base>`, reads the
fetched commit and creates the branch at that SHA. Its one caller, `workspace.create_worktree`,
passes the configured remote and the repository's default branch and appends a
`worktree.created` event with the start commit; `why` prints one line from that event. Every
path that starts an item (dispatch, `next`, the planner) already routes through
`wuwei worktree add`, so nothing else changes.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. The fetch is a subprocess inside the git adapter
(`_run`, closed allowlist, `TIMEOUT` 30 seconds). `fetch --no-tags <remote> <branch>` and
`rev-parse --verify FETCH_HEAD^{commit}` are already allowlisted (used by `vcs.fetch` for
PR fix rounds). Tests use real git in `tmp_path` with a bare origin or a missing-path remote:
no network.

## Constitution Check

- I (stdlib): unchanged; git stays a subprocess behind the adapter.
- II (exits, fail closed): a failed fetch is exit 2 with the reason (adapter `_operation`,
  then `registry.data` raises, then `__main__._call` prints and returns 2); nothing is created.
- III (one behaviour, one function): the start point lives in `worktree_add` only.
- IV (test first): each behaviour has its test task before its implementation task.
- V (ponytail): reuse the allowlisted fetch and `FETCH_HEAD` read; no new config key, no new
  port, no new helper. The `doctor` drift warning is deferred (spec, Deferred).
- Design spec conflict: section 8's vcs row lists `worktree_add(repo, branch, path)`; this
  feature changes it to `worktree_add(repo, branch, path, remote, base)` and amends that row
  (FR-007), as #641 did for its sentence.

## Design

### 1. `adapters/vcs/git.py`

Allowlist in `_run`: replace the case for `('worktree', 'add', '-b', branch, '--', path)` with
one that also takes a start SHA, so the no-start form is no longer runnable:

```python
case ('worktree', 'add', '-b', branch, '--', path, start):
    allowed = (bool(_revision(branch)) and isinstance(path, str) and bool(path)
               and '\0' not in path and bool(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', start)))
```

`worktree_add` (line 363):

```python
@_operation
def worktree_add(repo, branch, path, remote, base, root=None):
    """A new branch at <remote>/<base> as just fetched (#681), never the local HEAD."""
    branch = _revision(branch)
    path = os.fspath(path)
    if not path:
        raise ValueError('missing worktree path')
    try:
        _run(repo, 'fetch', '--no-tags', remote, base)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise ValueError(f'could not fetch {remote} {base}, so no worktree was created ({exc}); '
                         'check the network and the remote, then retry') from None
    # ponytail: FETCH_HEAD is per repository; two adds with different bases at once could swap
    # starts. One base per repository today; fetch into a named ref if that changes.
    start = _sha(_run(repo, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}'))
    _run(repo, 'worktree', 'add', '-b', branch, '--', path, start)
    return {'branch': branch, 'path': path, 'start': start}
```

Notes for the builder:

- The `fetch` allowlist case already rejects a remote or base that starts with `-`, has
  `..` or other characters; a `None` remote raises `TypeError` there, which `_operation`
  turns into exit 2. Do not loosen it.
- `_sha` already validates the `rev-parse` output. `_run` already redacts and caps the git
  stderr line in its `ValueError`, so the wrapped message carries no raw stderr.
- Branch from the SHA, not from `origin/<base>`: no upstream tracking is set on the new
  branch (today it tracks nothing), and it works without a remote-tracking refspec.

### 2. `cli/wuwei/registry.py`

`PARAMETERS['vcs']['worktree_add']` becomes `('repo', 'branch', 'path', 'remote', 'base')`
(the signature check in `tests/test_adapters.py` compares it exactly).

### 3. `cli/wuwei/workspace.py`, `create_worktree` (line 825)

Add keyword parameters `remote=None, base=None`. Replace the `add = ...` line and the call
after it with:

```python
if existing:
    result = data(vcs.worktree_checkout(str(repo), branch, str(path), root=root))
else:
    result = data(vcs.worktree_add(str(repo), branch, str(path), remote, base, root=root))
    state.append_event('worktree.created', {'item': Path(path).name, 'worktree': str(path),
                                            'branch': result['branch'], 'base': f'{remote}/{base}',
                                            'start': result['start']}, root)
```

The event is appended right after the add succeeds and before `_anchor`, so the record
exists even when anchoring fails afterwards (the worktree exists at that point). Gate check,
claim, `existing` path and `_anchor` are unchanged.

### 4. `cli/wuwei/commands/worktree.py`, `add`

Pass the configured remote and base:

```python
result = workspace.create_worktree(repo, args.branch or item.lower(), tree, root,
                                   registry.load('vcs', config), identity=repos[0]['identity'],
                                   existing=args.branch is not None,
                                   remote=config['brief']['remote'], base=repos[0]['default_branch'])
```

The printed JSON is the adapter's result, so it gains `start` with no other change.

### 5. `cli/wuwei/commands/event.py`

Add `'worktree.created': 'wuwei worktree add'` to `EVENT_PRODUCERS`, next to
`worktree.adopted`, so `wuwei event` refuses to forge it.

### 6. `cli/wuwei/commands/why.py`, `item`

`GROUPS` becomes `('queued', 'worktree', 'tier', 'gate', 'decision', 'phase', 'merge')`
(not in `REQUIRED`: an item without the event prints no worktree line). In the event loop:

```python
if kind == 'worktree.created' and payload.get('item') == name:
    add('worktree', f'worktree: branch {payload.get("branch", NOT)} from {payload.get("base", NOT)} '
        f'at {str(payload.get("start", NOT))[:12]}')
```

### 7. Docs

- `docs/site/reference.md`, "Item worktrees" first paragraph: replace "starting from the
  repository's current HEAD" with: it first fetches the repository's `default_branch` from
  `brief.remote` (default `origin`) and starts the branch at the fetched commit, never at the
  local branch; when the fetch fails it exits 2 with the git error and creates nothing; the
  JSON has `branch`, `path` and `start`, and the event `worktree.created` records the start
  commit, which `bin/wuwei why <item>` shows.
- `docs/specs/2026-09-24-wuwei-design.md`, section 8 adapters table, vcs row:
  `worktree_add(repo, branch, path)` becomes `worktree_add(repo, branch, path, remote, base)`.

## Reused, not re-implemented

- The allowlisted `fetch --no-tags` and `rev-parse --verify FETCH_HEAD^{commit}` cases and
  `_sha` (from `vcs.fetch`, PR fix rounds).
- `brief.remote` and `repos.default_branch`, the pair briefs and dispatch already use for
  `<remote>/<default_branch>` (`brief.py:384`, `dispatch.py:151`).
- `state.append_event` for the record; `registry.data` and `__main__._call` for exit 2.

## Must not change

- `worktree_checkout` and the `--branch` path (`pr claim`, `pr act` adopt), and `worktree
  adopt`.
- `vcs.fetch(repo, remote, branch, expected)` (PR fix rounds).
- The gate check, the claim, `_anchor`, identity, bootstrap and fast-check warnings in
  `worktree add`.
- `dispatch._start` and `build`: they already route through `wuwei worktree add`.
- No new config key; no `doctor` row (deferred).

## Files

| File | Change |
|---|---|
| `adapters/vcs/git.py` | `worktree_add` fetches and starts at `FETCH_HEAD`; allowlist case takes the start SHA |
| `cli/wuwei/registry.py` | `worktree_add` parameters |
| `cli/wuwei/workspace.py` | `create_worktree` passes remote and base, appends `worktree.created` |
| `cli/wuwei/commands/worktree.py` | `add` passes `brief.remote` and `default_branch` |
| `cli/wuwei/commands/event.py` | `worktree.created` producer |
| `cli/wuwei/commands/why.py` | `worktree` group and line |
| `cli/wuwei/signal.py`, `tests/test_signal_status.py` | `worktree.created` is silent, like `worktree.adopted` (found while building: every emitted kind needs a tier) |
| `tests/test_worktree_command.py` | two acceptance tests; fixtures push main to origin; fake result has `start` |
| `tests/test_vcs.py`, `tests/fixtures/vcs/recordings.json` | adapter replay, fetch failure, injection rows |
| `tests/test_git_hook.py`, `tests/fakes/vcs.py`, `tests/test_adapters.py`, `tests/test_path_day.py` | new signature |
| `tests/test_why.py` | the worktree line |
| `docs/site/reference.md`, `docs/specs/2026-09-24-wuwei-design.md` | behaviour and port row |

## Existing tests the new signature touches

- `tests/fakes/vcs.py:54`: `worktree_add(self, repo, branch, path, remote, base, root=None)`
  recording `(repo, branch, path, remote, base)`; `tests/test_worktree_command.py` lines 106
  and 118 expect `'origin', 'main'` at the end of the tuple; the `fake` fixture's
  `worktree_add` result (line 63) gains `'start': 'a' * 40`.
- `tests/test_adapters.py:62`: `('vcs', 'worktree_add', ('repo', 'branch', 'path', 'remote', 'base'), False)`.
- `tests/test_path_day.py:21`: the `worktree` stub accepts `**kwargs`.
- `tests/test_git_hook.py`: lines 282 and 346 pass `'origin', 'main'`; line 348's expected
  calls become the three argv lists (fetch, rev-parse, worktree add with the SHA) with replay
  steps; line 337's fake result gains `start` and line 340 passes `remote='origin',
  base='main'`; lines 370 and 403 (real git, no origin needed) pass `remote='.', base='HEAD'`
  (git fetches the repository's own HEAD; both pass the allowlist).
- Real-git `worktree add` tests in `tests/test_worktree_command.py` need the configured
  remote to carry `main`: line 24's test pushes `HEAD:refs/heads/main` to its bare origin
  before the add and expects `start` in the JSON; `hooked_workspace` (line 243) and
  `adopt_workspace` (line 367) push `main` to their bare origin after their last commit; the
  identity-template test (around line 180, no remote) adds `[brief]\nremote = "."` to its
  config.
