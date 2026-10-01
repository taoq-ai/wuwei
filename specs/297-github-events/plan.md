# Implementation Plan: GitHub events reach the planner and the owner

**Branch**: `297-github-events` | **Date**: 2026-10-01 | **Spec**: `specs/297-github-events/spec.md`

## Summary

No new module, no new adapter kind, no new process. Each behaviour lands at the shared spot its
callers already route through:

- `watch.poll` keeps the fingerprint baseline and the one `pr.changed` per PR, and adds a
  body-free fact record per PR so it can write a precise `summary` into the event and the wake
  marker; `watch.wake` prints the summaries first.
- `status.scan` turns `pr.changed` into one nudge per PR with the summary, listed first and
  cleared at `session: wake-seen`; `status.line` adds `prs <n> changed`. `nudges`, SessionStart,
  the cockpit and the phone `status` read these already.
- The code host port gains one operation, `probe(ref, tags)`: conditional `gh api --include`
  reads with `If-None-Match`. The listener probes every tick and calls the watch's full read
  (extracted as `watch.poll_prs`) only on a change, a failed probe or the `pr.poll_seconds`
  backstop. The watch skips its PR poll while the listener is alive.
- The listener sends each new summary to the owner DM through `control_plane.notify` and
  `remote.TRANSPORT`, the path `remote.escalate_new` already uses.
- `shepherd.headless` dispatches one headless shepherd seat per PR action episode by chaining
  what exists: `brief.write`, the Claude runtime adapter's `dispatch` (launch prompt),
  `agent_launch.check` (the seat launch guard: logged brief, MCP gate, memory floor,
  `host.seats`, reservation), the adapter's `headless`, `state.stop_seat`, `sessions.touch` and
  `watch.mark_wake`.
- One environment marker, `WUWEI_SEAT_ROLE=shepherd`, set only on the headless child, makes
  `merge.execute` refuse and `outward.classify` draft. Both are the single functions every merge
  and every outward tier decision already goes through.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in-process with the existing fakes (`tests/fakes/code_host.py`,
`tests/fakes/vcs.py`, the `Source` and `Runtime` fakes in `tests/test_listen.py` and
`tests/test_remote.py`), `subprocess.run` stubs for the GitHub and Claude adapters
**Constraints**: three-state exits, fail closed, core never imports `subprocess`
(`tests/test_adapters.py`), no comment bodies in events or state, outward lint unchanged

## Constitution Check

- Reuse: `watch.poll`, `watch.mark_wake`, `watch.wake`, `watch.health`, `watch.records`,
  `watch.owned`, `merge.poll`, `pr_actions.ACTIONS` and `pr_actions._item`, `brief.write`,
  `agent_launch.check` (it already applies the memory floor, so `remote.memory_floor` is not
  called again), `state.stop_seat`, `sessions.touch`, `control_plane.notify`,
  `remote.TRANSPORT`. No second event kind for a PR change: `pr.changed` gains `summary`.
- Imports: `shepherd.headless` and `shepherd.pending` import `brief`, `pr_actions`, `watch`,
  `sessions` and `guards.agent_launch` inside the functions, as `pr_actions` and `outward`
  already import `shepherd` lazily, so no import cycle appears.
- Ports: the conditional read lives in `adapters/code_host/github.py` behind the closed `_run`
  allowlist; the core sees only `probe`.
- Fail closed: a failed or malformed probe means "read fully"; a failed full read clears the
  in-memory ETags so the next tick reads again; a shepherd step that cannot run records exit 2
  with its reason and a planner wake.
- Ponytail: no event bus, no webhook server, no config for the 30 s probe, no retry queue for
  shepherd episodes, one shepherd turn per tick.

## Changes

### `cli/wuwei/watch.py`

1. `facts(measured)` (new, next to `snapshot`): from the dict `evidence` returns

   ```python
   {'head': pr['head'], 'mergeable': pr['mergeable'], 'state': pr['state'],
    'merged': pr.get('merged') is True,
    'requested': sorted(pr['requested_reviewers'] + pr['requested_teams']),
    'seen': {'comment:<id>': [author, ''], 'thread:<id>': [author, thread.get('path') or ''],
             'review:<id>': [author, review state]},
    'checks': {name: conclusion or state}}
   ```

   Authors are logins (`None` becomes `''`). No body is read.

2. `summary(ref, before, after, fields)` (new): returns `f'PR {ref}: ' + '; '.join(parts)`.
   Parts, in this order, each only when it applies:
   - `before is None and after is not None`: `now watched` (and nothing else);
     `after is None`: `no longer owned`;
   - `merged` became true: `merged`; else `state` became `closed`: `closed`;
   - `head` moved: `new commits pushed (head <7 hex>)`;
   - `mergeable` became `False`: `conflicts with its base`; from `False` to `True`:
     `conflicts resolved`;
   - new `thread:` ids grouped by `(author, path)` in first-seen order:
     `<n> new review comment[s] by <author>[ on <path>]`;
   - new `comment:` ids grouped by author: `<n> new comment[s] by <author>`;
   - new `review:` ids: `approved by <a>`, `changes requested by <a>`, `review by <a>` for
     `commented` (dismissed and pending are skipped);
   - each check whose value changed to a failing conclusion (completed and not success,
     neutral or skipped): `check <name> failed`; each that changed from failing to `success`:
     `check <name> passed`;
   - logins newly in `requested`: `review requested from <a, b>`;
   - no part at all: `updated (<fields joined by ', '>)`.
   `before` missing (upgrade) with `after` present and a known ref falls to the field rule
   above; never return a text without a part.

3. `poll(root)`: compute `facts(measured)` right after `snapshot` (before
   `pr_actions.observe`, so a classification failure keeps the facts consistent with
   `current`); keep old facts for unreadable refs exactly as `current` keeps old snapshots;
   read old facts from `saved(root).get('facts')`, else `previous(root).get('facts')`, else
   `{}`. For `changes`, build `summaries = {ref: summary(...)}`, pass
   `summaries=[summaries[ref] for ref in changes]` to `mark_wake`, add `'summary'` to the first
   payload and to each `rest` event, print `planner wake: <summary>` instead of the field list,
   and save `'facts': new_facts` in the same final `save` as `prs`.

4. `mark_wake(root, *, prs=(), inbox=0, summaries=(), kind, payload)`: the early return
   (`already covered`) also requires `not summaries`; when merging an unseen pending marker,
   `lines = pending.get('summaries', []) + list(summaries)`, otherwise `list(summaries)`; store
   `'summaries': lines[-20:]` only when `lines` is nonempty (a marker without summaries stays
   byte-identical to today). `# ponytail: last 20 summaries while unseen; a day-long idle
   planner reads the rest in nudges.`

5. `wake(root, *, consume=False)`: validate `summaries` (list of non-empty strings when
   present); `message = '\n'.join([*summaries, f'planner wake ({at}): ' + ...])`. The
   `planner wake` line is unchanged and stays last, so `endswith` checks keep passing.

6. `poll_prs(root)` (new, extracted from `tick` lines 402 to 405):

   ```python
   def poll_prs(root):
       """One full PR read and merge reconcile: the shared step of the watch and the listener."""
       from wuwei import merge
       result = max(poll(root), merge.poll(root))
       save(root, {'poll_at': workspace.now().isoformat()})
       return result
   ```

7. `listening(root)` (new): `return health(root, name='listen') == (0, '')`.

8. `tick`: `if due('poll_at', ...) and not listening(root): result = max(result, poll_prs(root))`.

### `cli/wuwei/listen.py`

- `PROBE_SECONDS = 30` with `# ponytail: fixed probe interval; a 304 is free, so no config.`
- `tick(root, tags=None)`: `tags = {} if tags is None else tags`. Order: clock; inbound poll
  and store (unchanged); `code = max(code, prs(root, config, tags))`; the responder block
  (commands, `escalate_new`, then `notify(root, config, waiting)` under the same
  `SLACK_OWNER_DM_CHANNEL` check); the inbox wake (unchanged); last,
  `if config['responder']['enabled'] and config['shepherd']['autostart'] and waiting:`
  `code = max(code, 2 if shepherd.headless(root, *waiting[0]) == 2 else 0)`. `waiting` is
  `shepherd.pending(root)` read once after `prs`, inside a try that sets code 2 on
  `watch.ERRORS`. The kill switch `responder.enabled = false` stops the DM and the shepherd
  as it stops commands and escalations.
- `prs(root, config, tags)` (new): for each ref from `watch.owned(root, config)`, call
  `host.probe(ref, tags.get(ref, {}), root=root)`; accept only `exit == 0` with a dict holding
  a bool `modified` and a dict `tags`; anything else counts as modified and drops
  `tags[ref]`. Full read when any ref is modified or `poll_at` (from `watch.saved`) is absent or
  at least `config['pr']['poll_seconds']` old: `if watch.poll_prs(root) == 2: tags.clear();
  return 2`, else return 0 (a change is not a listener finding). No full read means no write
  at all. `watch.ERRORS` print `listen PR poll unmeasured: <reason>` and return 2.
- `notify(root, config, waiting)` (new): today's rows from `watch.records`; `sent` is the set
  of `(pr, at)` from `pr.notified` payloads; for each `pr.changed` row with a `summary` whose
  `(pr, ts)` is not in `sent`: text = summary plus the tail, sent with
  `control_plane.notify(text, root=root, transport=remote.TRANSPORT)`; on exit 1 send
  `f'PR #{number} changed; details are on the host.'` with `remote.TRANSPORT.dm`; on exit 0
  append `pr.notified {'pr': pr, 'at': ts}`; on exit 2 return 2 and record nothing (retried
  next tick). Tail, from `dict(waiting)` and the config:
  - PR in `waiting`, autostart on: ` Shepherd starts: <ACTIONS[state][0]>.`
  - PR in `waiting`, autostart off: ` Shepherd autostart is off; nothing started.`
  - otherwise no tail.
  All tails pass the outward lint as fixed text (the test in `tests/test_remote.py` style).
- `run`: `tags = {}`; `delay = min(config['listen']['poll_seconds'], CLOCK_SECONDS,
  PROBE_SECONDS, config['pr']['poll_seconds'])`; `lambda root: tick(root, tags)`.

### `cli/wuwei/shepherd.py`

- `HEADLESS` (new dict, state to brief body, `{ref}` formatted):
  - `conflicted`: run `wuwei pr act {ref} --run`; if it stops on a conflict, resolve the
    conflict in the item worktree named in this brief and run `wuwei pr act {ref} --complete`.
  - `ci_red`: run `wuwei pr act {ref}`; it opens the fix round brief with the failed checks as
    feedback. Do not build the fix.
  - `changes_requested`, `threads_unanswered`: run `wuwei pr act {ref}`; for a `reply` action
    run `wuwei pr act {ref} --reply "<one-line acknowledgement>"`, which is stored as a draft;
    for `owner_decision` or `fix_round` stop.
  - `review_stale`: run `wuwei pr act {ref}`; it re-requests review and drafts the channel
    post.
  Every body ends: `Never run wuwei merge. Stop after this action and report what ran.`
- `pending(root)` (new): from `watch.saved(root).get('actions', {})`, the `(ref, episode)`
  pairs whose `episode['state']` is in `HEADLESS`, whose PR is not parked
  (`state.read_state(root).get('pr_dispositions', {}).get(ref, {}).get('kind') != 'parked'`)
  and with no `shepherd.dispatched` today carrying the same `pr` and `episode`
  (`created_at`), sorted by `created_at`.
- `headless(root, ref, episode, *, runtime=None)` (new), returns 0, 1 or 2:
  1. `record = {'pr': ref, 'state': episode['state'], 'episode': episode['created_at']}`;
     `state.append_event('shepherd.dispatched', record, root)` first (a crash drops an
     episode, never runs it twice).
  2. `item, tree = pr_actions._item(root, ref)`; `name = 'shepherd-' + uuid4().hex[:12]`;
     `relative = brief.write('shepherd', item, name, HEADLESS[...].format(ref=ref), pr=ref,
     root=root)`.
  3. `runtime = runtime or registry.load('runtime', {'adapters': {'runtime': 'claude'}})`
     (fixed, as `remote._turn`); `job = runtime.dispatch('shepherd', str(root / relative),
     str(tree), True, root=root)`; a nonzero exit or non-dict data finishes with that exit
     (2 when 0 with bad data).
  4. `code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {'subagent_type':
     'wuwei:shepherd', 'name': name, 'description': f'shepherd {ref}', 'prompt':
     job.data['prompt']}})`; nonzero finishes with `code` and `reason` (memory floor,
     `host.seats`, MCP gate, runtime policy). This reserves the seat exactly as an Agent launch.
  5. `tools = json.loads((registry.ADAPTERS.parent / 'agents/allowlist.json').read_text())
     ['shepherd']`; `try: result = runtime.headless(job.data['prompt'], None, tools,
     root=root, variables={'WUWEI_SEAT_ROLE': 'shepherd'})` `finally: state.stop_seat(name,
     root)`.
  6. Exit 2 or non-dict data finishes with 2. Otherwise `sessions.touch(root, sid,
     hook=f'shepherd {state}', cwd=str(root), role='shepherd')` and finish with
     `result.exit` and `session`.
  `_finish(root, record, code, text, **extra)` writes the outcome once, through
  `watch.mark_wake(root, prs=[ref], summaries=[f'PR {ref}: shepherd {state}: {text}'],
  kind='shepherd.finished', payload={**record, 'exit': code, **extra})`, with text
  `turn ended (exit <n>, session <8 hex>)` or `not started: <reason>`. `watch.ERRORS` and
  `brief.Refused` after step 1 finish with 2 (1 for `Refused`) and the reason.

### `cli/wuwei/sessions.py`

`ROLES = ('adhoc', 'seat-host', 'remote', 'shepherd')`.

### `cli/wuwei/merge.py`

First lines of `execute`:

```python
if os.environ.get('WUWEI_SEAT_ROLE') == 'shepherd':
    return Result(1, None, 'merge refused: a shepherd seat never merges; '
                  'the planner or the owner runs wuwei merge')
```

(`import os`). No lock, no event. `check` (the policy read) is unchanged.

### `cli/wuwei/outward.py`

First line inside `classify`'s `try`:
`if os.environ.get('WUWEI_SEAT_ROLE') == 'shepherd': return FINDINGS, 'draft'` (`import os`).
This covers `registry.outward_operation` (chat `post` and `dm`, code host `comment`, tracker
text), `check_call` (the MCP outward hook and the `gh` text guard) and `pr_actions._thread`.

### `adapters/runtime/claude.py`

`headless(prompt, session, tools, *, root=None, variables=None)`: refuse (exit 2,
`invalid headless call`) unless `variables` is `None` or a dict whose keys match
`WUWEI_[A-Z_]+` and whose values are strings; the child env is
`{**env.child_environment(), **(variables or {})}`. Nothing else changes; `remote._turn`
passes no variables.

### `cli/wuwei/registry.py`

`'code_host'`: add `'probe': ('ref', 'tags')`.

### `adapters/code_host/github.py`

- `_THREADS`: add `path` to the review thread node selection (`nodes{id isResolved isOutdated
  path comments(...)...}`); `threads` adds `'path': v.get('path')` validated as `str` or
  `None` (recorded fixtures without it keep passing).
- `_run`: in the generic `['api', endpoint, *options]` case with `payload is None`, also allow
  `options == ['--include']` and `options == ['--include', '-H', header]` where `header`
  fullmatches `If-None-Match: (?:W/)?"[\x21\x23-\x7e]*"`. After the process returns: when
  `'--include' in args` and stdout matches `HTTP/\S+ 304\b` at its start, return stdout
  whatever the exit code; any other nonzero exit raises as today. Conditional calls pass
  `json_output=False`.
- `_conditional(endpoint, etag)` (new): runs the call above, splits headers from body at the
  first blank line, reads the status code and the `ETag` header; 304 returns
  `(False, etag, None)`; 200 with a valid ETag returns `(True, <etag>, <parsed JSON after
  _errors>)`; anything else raises `ValueError('conditional read unavailable')`.
- `probe(ref, tags, root=None)` (new, `@_operation`): `tags` must be a dict; conditional read
  of `repos/{repo}/pulls/{number}` with `tags.get('pr')`; head from the 200 body or from
  `tags['head']` on 304 (missing raises, so the listener reads fully); then conditional reads
  of `repos/{repo}/commits/{head}/check-runs?per_page=100` and `.../statuses?per_page=100`
  with the stored ETags only when the head is unchanged. Returns
  `{'modified': any 200, 'tags': {'pr', 'head', 'checks', 'statuses'}}`.

### `adapters/code_host/none.py`

`def probe(ref, tags, root=None): return record_none('code_host', 'probe', root, measurement=True)`.

### `cli/wuwei/commands/status.py`

- `scan`: before the `if kind in SILENT: continue`, handle `session: wake-seen`:
  `current = {k: v for k, v in current.items() if k[0] != 'pr.changed'}; continue`. For
  `pr.changed` with a dict payload, key `('pr.changed', payload.get('pr'))` and reason
  `payload.get('summary') or f'{pr} changed: {", ".join(fields)}'` (events written before
  this feature). Return the rows with `pr.changed` first:
  `rows = sorted(current.values(), key=lambda row: row['source'] != 'pr.changed')` (stable).
- `snapshot`: `result['prs_changed'] = sum(row['source'] == 'pr.changed' for row in active)`.
- `line`: after the nudges part, `if data.get('prs_changed'): parts.append(f'prs
  {data["prs_changed"]} changed')`.

### `cli/wuwei/signal.py`

Add `shepherd.dispatched` and `pr.notified` to `SILENT`; add
`if kind == 'shepherd.finished': return ('silent' if payload.get('exit') == 0 else 'nudge'), lane`.

### `cli/wuwei/commands/event.py`

`EVENT_PRODUCERS`: `'pr.changed': 'wuwei watch or wuwei listen'`,
`'shepherd.dispatched': 'wuwei listen'`, `'shepherd.finished': 'wuwei listen'`,
`'pr.notified': 'wuwei listen'`. They are not in `FREE_KINDS`, so `wuwei event` refuses them.

### `cli/wuwei/workspace.py` and `templates/workspace/config.toml`

`SCHEMA['shepherd']['autostart'] = (bool, False)`; template line
`autostart = false # Start a headless shepherd seat for mechanical PR actions when the listener sees them (wuwei listen).`

### Docs

- `docs/site/configuration.md`: row `` `shepherd.autostart` `` (`false`, what it does, that
  merges never happen there and posts are drafts); `pr.poll_seconds` row: "Interval between
  full reads of raised and claimed PRs. With the listener running, conditional probes every
  30 s trigger a full read at once on a change."; `listen.poll_seconds` row: the listener ticks
  at most every 30 s.
- `docs/site/daily.md` section 4: a short paragraph "PR changes": the Stop message, `nudges`
  and `prs <n> changed` carry the summary; an idle interactive planner learns at its next
  turn; the shepherd and the DM cover the gap; the Claude Code desktop PR monitor is the
  complement for CI events in the owner's own session.
- `docs/site/remote.md` section 5: the listener also probes owned PRs every 30 s with
  conditional requests and takes over PR polling from the watch; the DM nudge and its fixed
  fallback line; `shepherd.autostart`. Section 8 Limits: no webhooks or tunnels; a shepherd
  turn blocks the listener poll while it runs, like a command turn; the idle planner gap.
  Keep every string `test_remote_runbook_matches_the_code` checks.

## What must not change

- `pr.changed` stays the only event for a PR change; `fields` stays in its payload.
- The fingerprint snapshot, its comparison, and "save the wake before the baseline".
- A wake marker without summaries, and `watch.wake` output for it.
- `merge.check`, the merge policy, the PR guard's `gh pr merge` refusal.
- The outward lint and tiers for every caller without the seat marker.
- `remote._turn` and `remote.handle`; the listener's inbound cursor and inbox wake.
- `agent_launch.check` itself (called, not changed).

## Test plumbing

- `tests/fakes/code_host.py`: add `probe(self, ref, tags, root=None)` through `_call`.
  `tests/test_adapters.py` `CALLS`: add `('code_host', 'probe', ('ref', 'tags'), ...)` in the
  same shape as its neighbours.
- Listener tests reuse the `case` fixture of `tests/test_listen.py` plus the code host fake
  and vcs fake from `tests/test_watch.py` (one owned PR `example/project#7`). DM tests keep the
  real `remote.TRANSPORT` and fake the chat port behind `registry.load('chat', ...)`, as the
  `chat` fixture in `tests/test_remote.py` does, so `remote.dm` still runs the security check
  and the outward lint (the fallback line depends on the lint refusing).
- Shepherd tests seed an approved item linked to the PR with a worktree as
  `tests/test_pr_actions.py` does, monkeypatch `mcp.cached` and `mcp.launch` clean as
  `tests/test_agent_launch.py` does, the host port's `free_memory` above the floor, and pass a
  fake runtime with `dispatch` (returning the real `brief.launch_prompt`) and `headless`
  (recording calls, returning a fixed session id).
- No test runs `gh` or `claude`; adapter tests stub `subprocess.run`.

## Implementation notes

- The shepherd unit tests (T030) and the listener acceptance tests (T032) both live in
  `tests/test_listen.py`, sharing its `prs` fixture (fake code host, vcs and chat port);
  `tests/test_shepherd.py` already has an unrelated `case` fixture.
- T022 drives the draft tier through a chat port wrapped by `registry.outward_operation`;
  the decorator and `outward.classify` are the same for the code host `comment` port.
- The review-thread query gained `path`, so the recorded GraphQL input and the recorded
  `threads` data in `tests/fixtures/code_host/recordings.json` carry it (`null`).
- Existing test plumbing adjusted, no assertion changed: two monkeypatched stubs accept the
  new parameters (`watch.health(..., name=)`, `listen.tick(root, tags)`), and the expected
  config defaults include `shepherd.autostart`.
