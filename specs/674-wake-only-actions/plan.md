# Implementation Plan: a wake fires only for a change that needs an action

**Branch**: `674-wake-only-actions` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Every PR wake goes through one function, `watch.poll` (the watch calls it directly, the
listener through `watch.poll_prs`). Fix it there:

1. Drop `updated_at` from `watch.snapshot`, and count a PR as changed only when a field of
   the current snapshot differs, so an old baseline is not a change.
2. Turn `watch.summary` into `watch.parts`: the same rules, each returning a
   `(kind, key, evidence, text)` row instead of a string, so the parts are the one source of
   the wake text and of the action decision.
3. In `poll`, a part fires only when its kind is in a new `watch.ACTIONS` dict and its
   evidence fingerprint differs from `watch.delivered[<pr>][<key>]`. Fired and suppressed
   parts go to `watch.why[<pr>]`. Only PRs with a fired part get `pr.changed` and the wake.
4. SessionStart consumes the wake when the session is the registered planner, so a wake the
   planner read at session start is not carried into the next one.
5. `bin/wuwei watch why <pr>` prints `watch.why[<pr>]`.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, port, event kind or config key.
Two new sub-keys of the reserved `watch` state key (`delivered`, `why`), written only by
`watch.poll` (state key `watch` is already reserved to `wuwei watch or wuwei listen` in
`state.py:260`). One new CLI action, `watch why`, read-only.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: `poll` keeps 0 clean, 1 a wake fired, 2 a read failed. `watch why` exits 0 with
  a record, 1 without, 2 on an invalid reference, unreadable state or no workspace (`_call`
  in `__main__.py` turns a raised error into 2 with its reason).
- III one behaviour one function: parts in `watch.parts`, the fire decision in `watch.poll`,
  the planner action text in `watch.ACTIONS`.
- IV test first: tasks.md orders each test before its code.
- V simplicity: no event kind for suppressed changes (state holds the last per PR), no
  per-poll history, no config for the action map.
- VII security: `delivered` and `why` live under the reserved `watch` key, so a seat cannot
  forge a delivered record to silence a wake through `wuwei state set`.
- Workflow: no guard or decision rule changes, so no 9.2 invariant row (spec, Assumptions).

## Design

### cli/wuwei/watch.py

**`carried(root, key)`** (new, beside `previous`): today's `watch.<key>`, else the previous
day's, else `None`. Replaces the two inline copies in `poll` (`prs` at lines 439-441,
`facts` at 444-446) and serves `delivered`, `why` and the `watch why` command.

```python
def carried(root, key):
    value = saved(root).get(key)
    return previous(root).get(key) if value is None else value
```

**`snapshot`** (line 365): remove `'updated_at'` from the field tuple. `evidence` (line 353)
keeps `obligations._time(pr['updated_at'])`.

**`ACTIONS`** (new, above `parts`):

```python
# #674: the part kinds that need a planner action; any other part never wakes on its own.
ACTIONS = {'merged': 'close the item', 'closed': 'owner decision for the closed PR',
           'commits': 're-run the gates on the new head',
           'conflicts': 'rebase, resolve, run fast checks, push',
           'comments': 'triage the comments', 'approved': 'wuwei merge or merge decision',
           'changes_requested': 'triage review threads', 'review': 'triage the review',
           'check_failed': 'start a fix round'}
```

**`parts(before, after, fields)`** replaces `summary` (lines 395-431). Same rules, same
texts, same order; each appends a row instead of a string:

| Rule today | kind | key | evidence |
|---|---|---|---|
| `fields == ['new']` / `['gone']` | `new` / `gone` | `watched` | the kind |
| merged | `merged` | `state` | `'merged'` |
| closed | `closed` | `state` | `'closed'` |
| head moved | `commits` | `head` | `after['head']` |
| mergeable became False | `conflicts` | `mergeable` | `False` |
| mergeable False to True | `resolved` | `mergeable` | `True` |
| new comments, grouped by (surface, author, path) | `comments` | `f'{surface}:{author}:{path}'` | sorted `seen` keys of the group |
| new review (approved, changes_requested, commented) | `approved`, `changes_requested`, `review` | the `seen` key (`review:<id>`) | the review state |
| check not passing | `check_failed` | `f'check:{name}'` | `[after['head'], value]` |
| check passing after not passing | `check_passed` | `f'check:{name}'` | `[after['head'], value]` |
| reviewers added | `requested` | `requested` | the added logins |
| nothing above (or facts missing) | `updated` | `fields` | `fields` |

The grouping keeps today's order (thread groups first, then comment groups, insertion order
within). The `Counter` import goes if nothing else uses it (it does not today).

**`poll`** (lines 434-496):

- Baselines: `old = carried(root, 'prs')`, `old_facts = carried(root, 'facts') or {}`,
  `old_delivered = carried(root, 'delivered') or {}`; each must be a dict (or `None` for
  `prs`), else `ValueError(f'invalid PR ...; {DAMAGED}')` inside the existing `try`.
- Diff (lines 474-482): for a ref in both, `fields = sorted(key for key in current[ref] if
  old[ref].get(key) != current[ref][key])` and record a change only when `fields` is not
  empty (an old baseline's extra `updated_at` key no longer counts).
- Decide per changed ref:

```python
delivered = {ref: dict(old_delivered.get(ref, {})) for ref in current}
why, fired = {ref: value for ref, value in (carried(root, 'why') or {}).items() if ref in current}, {}
for ref, fields in changes.items():
    marks, shown, held = delivered.get(ref, {}), [], []
    for kind, key, evidence, text in parts(old_facts.get(ref), new_facts.get(ref), fields):
        mark = fingerprint(evidence)
        if marks.get(key) == mark:
            held.append([text, 'already delivered'])
        elif kind not in ACTIONS:
            held.append([text, 'no action'])
        else:
            shown.append([text, ACTIONS[kind]])
        marks[key] = mark
    why[ref] = {'at': started.isoformat(), 'fired': shown, 'suppressed': held}
    if shown:
        fired[ref] = fields, f'PR {ref}: ' + '; '.join(text for text, _ in shown)
```

  (`why` for a `gone` ref is written and then pruned on the next poll; validate the carried
  `why` is a dict like the others.)
- The wake block (lines 483-493) runs over `fired` instead of `changes`: same
  `mark_wake` / `pr.changed` / `planner wake:` print, payload `{'pr', 'fields', 'summary'}`.
- Final save adds `'delivered': delivered, 'why': why`. Return `2 if unreadable else
  int(bool(fired))`.

`mark_wake` and `wake` do not change.

### cli/wuwei/guards/lifecycle.py

`session_start`, line 100: `notice = watch.wake(root, consume=bool(session) and session ==
(day or {}).get('planner_session_id'))`. `session` (line 55) and `day` (line 62 or 67) are
already in scope; `day` can be `None` only when both registry and memory reads failed.

### cli/wuwei/commands/watch.py

- `add`: when `name == 'watch'`, add `why` to `actions` with one positional `pr`
  (help: `Show what fired and what was suppressed for an owned PR`). `listen` gets no `why`.
- `run`: `if args.watch_action == 'why': return why(args.pr)` before `service`.
- `why(ref)`: `ref = references.pull_request(ref)`, `root = workspace.find_workspace()`,
  `value = watch.carried(root, 'why') or {}`; not a dict raises `ValueError(... DAMAGED)`.
  No record: print `watch why: no recorded change for <ref> today` and return 1. Else print
  `PR <ref> (<at>)`, then `fired: <text> (<action>)` per fired part, then
  `suppressed: <text> (<reason>)` per suppressed part, and return 0.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.2.1 "Wake outside the model" (line 218): "on any
  change" becomes: on a change with a part that needs a planner action (`watch.ACTIONS`),
  once per part (`watch.delivered`); `updated_at` is evidence time only; SessionStart in the
  planner session consumes the wake; `wuwei watch why <pr>` shows what fired and what was
  suppressed (#674).
- `docs/site/daily.md` (the "PR changes reach the planner" paragraph, line 366): "Every
  change" becomes every change that needs an action, once; a passed check, a resolved
  conflict, a reviewer request, a timestamp or a PR starting or stopping being owned does
  not wake; `bin/wuwei watch why <pr>` says why.
- `docs/site/reference.md`: one line for `bin/wuwei watch why <pr>` next to the watch
  status text (around line 176), with its exits.

## Tests that change

These assert today's behaviour that the issue removes; update them in the same tasks:

- `tests/test_watch.py::test_pr_poll_persisted_diff_wakes_once`: drop `updated_at` from the
  parameters (it moves to the new no-wake test).
- `test_poll_new_gone_and_midnight` and `test_midnight_without_day_state_keeps_polling`:
  `new` and `gone` now return 0 and write no `pr.changed`; assert `watch why` records them
  as suppressed (`no action`) instead.
- `test_stop_wake_once_accumulates_until_seen`: it relies on the `new` wake of
  `example/project#8`; make the second PR's change actionable (claim it, poll, then move its
  head) so the marker still accumulates two PRs.
- `test_poll_in_place_edit_and_unordered_evidence`: an edited comment body returns 0 now;
  assert `updated (threads)` is suppressed with `no action`.
- `test_summary_rules`, `test_summary_names_comments_files_and_failed_checks` and
  `test_summary_without_prior_facts_names_fields` move to `parts`: same texts, plus kind;
  the `updated_at` row becomes an `updated` part, and the no-prior-facts case returns one
  `updated (checks, head)` part.

Run the full suite: `tests/test_listen.py`, `tests/test_pr_ownership.py` and
`tests/test_signal_status.py` read `pr.changed` and should pass unchanged (their changes
are head, mergeable or comment changes, all actionable).

## What must not change

- `watch.evidence` validation, `facts`, `fingerprint`, `mark_wake`, `wake` and the Stop hook.
- The `pr.changed` payload shape and the summary text format (`PR <ref>: a; b`), which
  `listen.notify` and `status.attention` read.
- `pr_actions.observe` runs on every successful read, whatever the wake decides.
- Read-failure handling: the old snapshot, facts and delivered record of a PR that failed
  to read are kept.
- A SessionStart in any session other than the registered planner never consumes the wake.
