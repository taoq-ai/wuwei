# Implementation Plan: Headless shepherd

**Branch**: `511-headless-shepherd` | **Spec**: `spec.md`

## Summary

One sweep function, `shepherd.overnight(root)`, built only from what exists: it pins the
owning day so every existing reader and writer (`pr_actions.evaluate`, `merge.check`,
`merge.execute`, `shepherd.post_review_request`, `state`) works on the day that owns the PRs,
acts on `approved` (merge when the policy clears) and `review_stale` (ping), and records
everything else as queued with its evidence. It runs once from `sweep obligations
--headless` or in a loop from a new `wuwei shepherd` command that the existing
`watch install` machinery installs as a user service. One renderer turns the day's events
into `overnight.md` and into the first section of the next morning plan. Doctor gets one row.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures: the fake
code host and `case`, `own`, `REF` from `tests/test_stop.py` (as `tests/test_pr_actions.py`
does), `WUWEI_NOW` for the clock, monkeypatched `merge.check`, `merge.execute` and
`shepherd.post_review_request` recorders where their own suites already cover them, and the
install pattern of `tests/test_listen.py:337-360` (`service_platform` monkeypatched, fake
watch service) for `shepherd schedule`.

## Constitution Check

- I stdlib only: no new dependency. Pass.
- II three-state exits, fail closed: the sweep exits 0 clean, 1 queue not empty, 2 any PR
  unmeasured; an unreadable PR is `unmeasured`, never skipped as clean. Pass.
- III one behaviour one function: owning day, sweep, renderer, last run are one function
  each in `shepherd.py`; install reuses `commands.watch.service`; the loop and lock reuse
  `watch.serve`. Pass.
- IV test first: every task pair in `tasks.md` is test then implementation. Pass.
- V simplicity: no config key (fixed 900 s interval, `ponytail:` comment), no new template,
  no new guard, two scheduling variants deferred. Pass.
- VII security / no forgeable trust: the morning plan renders from `shepherd.overnight`
  events, a kind only the CLI writes (`EVENT_PRODUCERS`, `bin/wuwei event` refuses it;
  `events.jsonl` is protected by `protect_state`). The day pin is in-process, not an
  environment variable a seat could set. The sweep merges only through `merge.execute`
  (the 4.6 policy, under its lock) and posts only through `post_review_request` (outbound
  tiers). Pass.
- #530: no new refusal. #551: the session path returns an action with the exact command,
  why, then and the card. Pass.

## Changes

### `cli/wuwei/workspace.py` (shared spot for the day)

- Module global `_DAY = None` with `# ponytail: process-wide day pin for the headless
  sweep, which is its own process; pass the directory through if a long-lived caller needs
  two days`.
- `day_dir`: `return root / ".wuwei/days" / (_DAY or now().date().isoformat())`. Nothing
  else changes; with `_DAY` None it is byte-for-byte today's behaviour.

### `cli/wuwei/pr_actions.py`

- Extract the lookup at lines 405-408 of `_thread` into `_latest(measured, surface, target)`
  returning `(thread, latest)`; a `thread` or `bot-p1` surface finds the thread and its last
  comment, `review` and `comment` find the row by id. `_thread` calls it (it already skips
  `bot-p1` before the lookup, so its behaviour is unchanged).

### `cli/wuwei/shepherd.py` (all new behaviour)

- `HEADLESS_SECONDS = 900` (`# ponytail: fixed interval; a config key if an owner needs
  another`).
- `owning_day(root)`: today's `workspace.day_dir(root)` when
  `state.read_state(directory=today)['gate_approved']`; else the first of `watch.days(root)`
  other than today with a `state.json`; else None.
- `_live(root)`: `bool(state.read_state(root).get('planner_session_id')) and
  heartbeat._planner(root)[0] == 'ok'` (reuse; same rule the heartbeat probe uses).
- `_evidence(root, config, ref, current)`: one `watch.evidence(host, ref, root)` read, then
  strings: for `threads_unanswered` and `changes_requested`, one per key of
  `obligations._replies(measured['reviews'], measured['threads'], me, acks)` through
  `pr_actions._latest`: `f'{surface} {target} by {author}' + (f' on {path}') + f': {text}'`
  with the body whitespace collapsed; for `ci_red`, `f'check {name}: {conclusion}'` per red
  check; `conflicted` gives `conflicts with its base`; `closed` gives `closed without
  merge`.
- `overnight(root)`: the sweep (FR-003, FR-005):
  1. `if _live(root): print(...); return 0` (today).
  2. `day = owning_day(root)`; None: print `shepherd: no owned PRs`, return 0.
  3. `workspace._DAY = day.name`; `try:` ... `finally: workspace._DAY = None`.
  4. Inside: `_live(root)` again (owning day) then return 0; `config`, `host, refs =
     watch.owned(root, config)`; no refs: print, return 0 (before `evaluate`, which would
     raise on an empty day).
  5. `code, rows = pr_actions.evaluate(root)`. `last` = latest `shepherd.overnight` payload
     per PR from `watch.records(day / 'events.jsonl')`.
  6. Per row: `exit == 2` gives `unmeasured` with `row['reason']`; skip parked and
     `waiting`; skip a PR whose last outcome is `merged`; `merged` gives `merged`;
     `approved` gives `merge.check(ref, root)` then, on exit 0, `merge.execute(ref,
     root=root)`: exit 0 `merged`, else `queued` with the result reason; `review_stale`
     gives `doctor._capture(post_review_request, root, ref)`: exit 0 `pinged`, 1 `queued`
     with the captured text, 2 `unmeasured`; every other state `queued` with
     `_evidence(...)` (an exception there gives `unmeasured` with the reason).
     `merge.check` first because a refused `merge.execute` writes a `merge.policy_blocked`
     event every time; a refused check writes nothing, so a night in the soak window or quiet
     hours does not fill the day's events. `execute` re-checks under its lock.
  7. Write `state.append_event('shepherd.overnight', payload, root)` only when `(state,
     outcome)` differs from `last[ref]`.
  8. Exit: 2 when any unmeasured this run, else 1 when the rendered queue is not empty,
     else 0. `state.append_event('shepherd.swept', {prs, merged, pinged, queued,
     unmeasured, exit}, root)`; `workspace.atomic_write(day / 'overnight.md',
     '\n'.join(overnight_lines(day)) + '\n')`; print `shepherd: sweep <json counts>`.
- `overnight_lines(directory)`: renderer (FR-007). From `watch.records(directory /
  'events.jsonl')`: `shepherd.overnight` rows and the `shepherd.swept` count and last
  timestamp. `[]` when there is no `shepherd.overnight` row. Otherwise:
  ```
  ## Overnight (days/<name>: <n> sweeps, last <ts>)
  - <ts> <pr> <state>: <outcome>[: <reason>]
  ...
  Morning queue (first items today):
  1. <pr> <state>: <reason or action>. Run: wuwei pr act <pr>
     - <evidence line>
  ```
  The queue holds PRs whose latest outcome is `queued` or `unmeasured`, ordered by that
  event's time; it ends with an empty line.
- `last_swept(root)`: the newest `shepherd.swept` timestamp in `watch.days(root)[:2]`, else
  None (`# ponytail: newest two days; the sweep writes to the owning day or today`).
- `loop(root=None, *, once=False)`: `watch.serve(workspace.find_workspace(root),
  'shepherd', overnight, 0 if once else HEADLESS_SECONDS, once=once)`.

### `cli/wuwei/commands/sweep.py`

- `obligations` parser gets `--headless` (help: one CLI-only shepherd sweep of the owning
  day). `func=lambda args: shepherd.loop(once=True) if args.headless else
  obligations.sweep()`.

### `cli/wuwei/commands/shepherd.py` (new, about 40 lines)

- `register`: parser `shepherd` (help `Run the headless PR sweep; schedule installs it`);
  subparsers dest `shepherd_action`: `schedule` with `--dry-run`, `unschedule`.
- `run(args)`: `action = {'schedule': 'install', 'unschedule': 'uninstall'}.get(...)`.
  When `action` and not `dry_run` and `sessions.current()`: print one JSON line
  `{'action': 'owner_terminal', 'command': f'bin/wuwei shepherd {args.shepherd_action}',
  'why': 'a scheduled shepherd merges and posts as you while no session runs; you start or
  stop it', 'then': 'bin/wuwei doctor shows the shepherd row'}` plus, for `schedule` when
  `workspace.day_dir(root) / 'plan.md'` is a file, `'widget': decision.widget(
  decision.gate(root) + QUESTION, 'Shepherd', [('Schedule (Recommended)', ...), ('Not now',
  'The shepherd keeps running only in a session.')], 'bin/wuwei shepherd schedule')`;
  return 1. Otherwise `return service.service(Namespace(shepherd_action=action, once=False,
  dry_run=getattr(args, 'dry_run', False)), 'shepherd', lambda once: shepherd.loop(once=once))`.
- `QUESTION`: `Schedule the overnight shepherd on this machine? Every 15 minutes while no
  planner session is live it merges what wuwei merge check clears, sends due review pings
  under the outbound tiers and queues the rest for your morning plan. No model runs.`

### `cli/wuwei/commands/event.py`

- `EVENT_PRODUCERS`: `'shepherd.overnight'` and `'shepherd.swept'`: `'wuwei sweep obligations
  --headless or wuwei shepherd'`.

### `cli/wuwei/plan.py` (`propose`)

- In the `lines` list (line 209-210), after the Finding line: `*(shepherd.overnight_lines(
  prior[0]) if prior else [])`, with `from wuwei import shepherd` local to `propose`.

### `cli/wuwei/commands/doctor.py` (`_day`)

- After the listener rows (before `heartbeat`, line 572): one row. `installed =
  workspace.unit_installed(root, name='shepherd')`; `last = shepherd.last_swept(root)`;
  value `f'scheduled ({"launchd" if sys.platform == "darwin" else "systemd"}), last swept
  {last or "not yet"}'` or `'runs only in a session; bin/wuwei shepherd schedule runs it
  overnight' + (f'; last headless sweep {last}' if last else '')`; status ok; a read error
  gives unmeasured with fix `wuwei state recover in a host terminal`.

### Registration and docs

- `cli/wuwei/__main__.py` `GROUPS`: add `shepherd` to the Owner group after `listen`.
- `cli/wuwei/commands/__init__.py` `WRITES`: add `shepherd schedule`, `shepherd unschedule`
  (and `shepherd` if `tests/test_cli_known_command.py` requires the bare path, as it
  decides for `watch` and `listen`).
- `docs/site/reference.md`: commands table row `bin/wuwei shepherd` after `bin/wuwei
  sweep`; add `shepherd` to the Doctor Day and sessions list.
- `docs/specs/2026-09-24-wuwei-design.md` 4.2.1: one bullet after "Wake outside the model":
  "Overnight, without a session (owner, 2026-10-08, #511)" stating the owning day, the
  actions (merge through 4.6, pings through 4.9), the queue into the next morning plan, and
  that it never replies, fixes, rebases, starts a seat or calls a model.

## What must not change

- `obligations.sweep` and `bin/wuwei sweep obligations` without `--headless`.
- `watch.tick`, `listen.tick`, the listener autostart and `shepherd.headless`/`pending`
  (model seats stay opt-in and separate).
- `merge.check`/`merge.execute` (the policy), `post_review_request`, the outbound tiers.
- `pr_actions._thread` behaviour (only the lookup moves into `_latest`).
- `day_dir` with no pin; `plan.md` with no `shepherd.overnight` event on the prior day.
- Doctor exit codes for an existing workspace (the new row is ok).
- The service templates and `commands.watch.service`.

## Not on the headless path (checked)

`watch.previous` and `watch.mark_wake` compare against `day_dir`; the sweep does not call
them (no `watch.poll`), so the pin cannot shift a watch baseline. The builder keeps it that
way: the sweep never calls `watch.poll`, `watch.tick` or `listen.tick`.

## Build notes (builder, 2026-10-08)

- `approved`: a check or execute result of exit 1 is `queued` and exit 2 is `unmeasured` (fail
  closed), both with the result reason.
- The morning queue line names the invocation form: `Run: bin/wuwei pr act <pr>`.
- T023: the byte-equality check for a plan with no Overnight section was dropped, because any
  prior day directory already adds the steward Finding line; the test asserts no Overnight
  section instead, and the existing plan tests run unchanged.
- `tests/test_doctor.py::test_day_rows` lists the new `shepherd` row (the one existing assertion
  this item changes).
