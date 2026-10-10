# Implementation Plan: wuwei pr raise --draft

**Branch**: `726-pr-raise-draft` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The raise path already has everything but the flag: the github adapter accepts `draft` in
`create_pr`, `raise_pr` already reads `merge.owner_hold`, ranks and requests reviewers, and
`state.record_pr` already records the raise. So the change is one boolean threaded from the
CLI through `raise_pr` into the existing payload, verification and event, plus a reviewers
line on stdout. Taking a PR out of draft needs one new code host operation, `ready(ref)`, and
one branch at the top of `pr_actions.act`.

## Technical Context

Python 3.11+ stdlib only (constitution I), pytest dev-only. No new module, no new state key,
no new event kind (`pr.raised` is already reserved to `wuwei pr raise`,
`cli/wuwei/commands/event.py:67`), no new config key. One new code host port operation.

## Constitution Check

- I stdlib: nothing new imported. `gh` stays behind the adapter.
- II exits: a created PR whose `draft` differs from the request, a failed `ready` and a PR
  still a draft after `ready` are exit 2 with the reason; `--ready` on a non-draft is exit 0.
- III one behaviour one function: the draft decision lives in `raise_pr`; the ready decision
  lives in `act`; the hold is read only through `merge.owner_hold`.
- IV test first: every task pair in tasks.md is test then implementation.
- V simplicity: no state key for draft (the host is read fresh), no new event for ready, no
  new watch action, no change to `classify`.
- VII security: the new adapter command is one closed allowlist entry (`gh pr ready <url>` with
  the URL rebuilt from a validated ref, no other flags). The automatic ready reads only the
  `owner_merge` record, which only the owner can clear (#678); a seat can ask with
  `--ready`, which grants no merge (`merge.check` still refuses a held item and checks
  `draft` itself).
- Workflow: no guard or decision rule changes, so no 9.2 row and no `test_invariants.py`
  change. I37 keeps holding: `--ready` never reaches `merge.execute`.

## Design

### cli/wuwei/commands/pr.py

- `raise_cmd.add_argument('--draft', action='store_true', help='Open the PR as a draft;
  automatic for an owner_merge item')`; `run_raise` passes `draft=args.draft` to
  `shepherd.raise_pr`.
- `mode.add_argument('--ready', action='store_true', help='Mark a draft PR ready for review')`
  in the existing mutually exclusive group of `act`; `run_act` passes `ready=args.ready` to
  `pr_actions.act`.

### cli/wuwei/shepherd.py, `raise_pr`

- Signature: `raise_pr(root, repo_name, base, title, body, item, draft=False)`.
- Right after the existing `if hold := merge.owner_hold(row):` block (line 324), add
  `draft = draft or bool(hold)`. Keep the body line and the label call as they are.
- `create_pr` payload (line 352): add `'draft': draft`.
- The created-PR check (line 356): `if pr['head'] != head or pr['url'] != created['url'] or
  pr['draft'] != draft:` with the existing message.
- `state.record_pr(root, item, ref, raised=True, head=head, reviewers=reviewers, draft=draft)`.
- Output (lines 368-370): after `print(ref)`, print
  `'reviewers: ' + ' '.join(reviewers) if reviewers else obligations.SOLO` (the same line
  `commands/pr.py:run_reviewers` prints). Replaces the `if not reviewers:` print.
- Must not change: the gate check, the grant argv at line 312 (`--draft` does not change what
  is published, so a grant for the raise still matches), the lint, identity, ranking and
  `request_reviewers` calls, the tracker call, the error mapping.

### cli/wuwei/state.py, `record_pr`

- Signature gains `draft=False`; after the `reviewers` payload line, `if draft:
  payload['draft'] = True`. The write itself is unchanged (no new state key). `claim_pr` keeps
  calling it without `draft`.

### Code host port: `ready(ref)`

- `cli/wuwei/registry.py` PARAMETERS `code_host`: add `'ready': ('ref',)`.
- `adapters/code_host/github.py`:
  - `_run` allowlist: a case `['pr', 'ready', url]` with `repo, number = _ref(url)` and
    `allowed = url == f'https://github.com/{repo}/pull/{number}' and payload is None`, beside
    the `pr merge` case.
  - `@_operation def ready(ref, root=None)`: `repo, number = _ref(ref)`;
    `_run(['pr', 'ready', f'https://github.com/{repo}/pull/{number}'], json_output=False)`;
    return `{'ready': True}`. Not an outward operation (no text).
- `adapters/code_host/none.py`: `def ready(ref, root=None): return record_none('code_host',
  'ready', root, measurement=False)`.
- Tests' port mirrors: `tests/fakes/code_host.py` gains `ready`; `tests/test_adapters.py`
  CALLS gains `('code_host', 'ready', ('ref',), False)`;
  `tests/fixtures/code_host/recordings.json` gains one `ready` recording (argv
  `["pr", "ready", "https://github.com/acme/widget/pull/7"]`, stdout `""`, data
  `{"ready": true}`), which `tests/test_code_host.py` picks up as a write case for both the
  success replay and the failure table.

### cli/wuwei/pr_actions.py

- `observe`: the row dict (line 160) gains `'draft': measured['pr']['draft'] is True` (the
  recorded fixture and the github adapter always carry the field).
- `act(root, ref, *, run=False, complete=False, reply=None, ready=False)`: right after the
  `row['exit'] == 2` return and before `row['exit'] == 0`:

  ```python
  if ready and not row.get('draft'):
      print(f'{ref}: already ready for review')
      return 0
  if row.get('draft') and row['state'] != 'closed' and (ready or _cleared(root, ref)):
      return _ready(root, ref)
  ```

- As built, the cleared test is folded into `_ready(root, ref, ready)`, which returns None when
  neither `ready` nor a cleared flag applies. Cleared: true when an item
  with `pr == ref` has an `owner_merge` record and `merge.owner_hold(item)` is None (so a malformed record raises `ValueError`, exit 2 via the
  CLI, and is never read as cleared).
- `_ready`: `act` calls it inside `try`; load the code host, `merge.read(host.ready, ref,
  root=root)`, then `merge.checked_pr(host, ref, root)`; if `draft` is still true raise
  `ValueError('PR is still a draft after ready; run bin/wuwei pr state, then retry')`; print
  `json.dumps({'action': 'ready', 'pr': ref})`; return 0. On the same exception tuple `act`
  already catches, print `f'{ref}: PR action unmeasured: {exc}'` and return 2.
- Must not change: `classify`, `ACTIONS`, the episode and deadline logic, `check`, and every
  existing branch of `act` (a held draft without `--ready` behaves exactly as today).

### docs/site/reference.md

- "Raising a PR": one sentence for `--draft` (and the automatic draft for an `owner_merge`
  item, the `pr.raised` payload `draft: true`), one for the `reviewers: <logins>` line, one for
  `pr act <ref> --ready` and the automatic ready after `plan set <item> owner_merge=false`.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/commands/pr.py` | `--draft` on raise, `--ready` on act |
| `cli/wuwei/shepherd.py` | `raise_pr` draft flag, payload, check, record, reviewers line |
| `cli/wuwei/state.py` | `record_pr(draft=)` event payload |
| `cli/wuwei/registry.py` | `ready` port parameters |
| `adapters/code_host/github.py` | allowlist case and `ready` |
| `adapters/code_host/none.py` | `ready` |
| `cli/wuwei/pr_actions.py` | row `draft`, `act(ready=)`, `_cleared`, `_ready` |
| `docs/site/reference.md` | raise and act lines |
| `tests/test_shepherd.py` | raise tests |
| `tests/test_pr_actions.py` | act tests |
| `tests/test_code_host.py`, `tests/fixtures/code_host/recordings.json` | adapter tests |
| `tests/test_adapters.py`, `tests/fakes/code_host.py` | port contract and fake |
