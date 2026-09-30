# Implementation Plan: The daily path runs without operator repairs

**Branch**: `238-daily-path` | **Date**: 2026-09-30 | **Spec**: `specs/238-daily-path/spec.md`

## Summary

`dispatch next` becomes the gate flow's `build next`: it opens the fix round itself
(reusing `build.open_fix`) and returns `wuwei build next <item>`, and its `gates` result
carries ready seat actions (`launch` for a logged gate brief, `continue` for the delta)
from the same formatter `build next` uses for the builder launch. A merged PR observation
also moves post-PR `fix` and `delta` items to `merged`. Docs gain one daily path page and
one recovery page; the "planned" statements for implemented features go. No new modules,
state keys, event kinds or configuration.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in process. Fixtures to reuse: `tests/test_dispatch.py` `root` and
`record`; `tests/test_pr_actions.py` `linked` and `completed_build`; the scripted-day
driver `tests/fakes/day.py` (`Day`, `Runtime`); `tests/test_docs.py` page checks.
**Constraints**: three-state exits (a failed `open_fix` is exit 2 with its reason), no
guard loosened, invoke the CLI only as `bin/wuwei` or `python3 -P -m wuwei`.

## Constitution Check

- One behaviour, one function: the seat action shape lives in one formatter
  (`brief.seat_action`), used by `build next` and `dispatch next`; the day event read lives
  in one reader (`brief.events`); the fix round opens only through `build.open_fix`; phase
  legality stays `state.PHASES` and `_check_transition`.
- Test first: tasks.md orders each test before its change.
- No forgeable trust: nothing new is trusted. Phases and build records are still written
  only by CLI producers under the state lock. The launch guard still decides every launch
  and resume (`cli/wuwei/guards/agent_launch.py` unchanged); `dispatch next` only offers
  actions the guard would accept.

## `dispatch next` result (the contract the planner reads)

```text
{"action": "gates", "roles": ["arch", "quality", "security"], "seats": [
  {"action": "launch", "brief": "<abs brief>", "worktree": "<abs tree>", "runtime": "claude",
   "agent_type": "wuwei:sentinel-arch", "prompt": "WUWEI brief: ...\nRead instructions ...",
   "receive": "wuwei dispatch receive A arch arch-1"}]}

{"action": "fix", "roles": ["quality"], "command": "wuwei build next A"}

{"action": "gates", "roles": ["quality"], "seats": [
  {"action": "continue", "brief": "...", "worktree": "...", "runtime": "claude",
   "agent_type": "wuwei:sentinel-quality", "resume": "<seat agent_id>",
   "feedback": "Delta review: ...", "prompt": "<launch prompt>\n\n<feedback>",
   "receive": "wuwei dispatch receive A quality quality-1 --round delta"}]}
```

`raise` and `escalate` are unchanged. `seats` is always present on `gates` (possibly
empty). Command strings use `shlex.quote` for each argument, as `build check` does.

## Changes by file

### `cli/wuwei/brief.py` (shared helpers, moved not copied)

- `events(root)`: the day event read now inline in `build.next_action`
  (`cli/wuwei/commands/build.py` lines 116 to 119): read today's `events.jsonl`, parse each
  line, raise `ValueError('invalid build event record')` (keep the message) unless every row
  is a dict with a dict `payload` and a str `kind`; return the rows.
- `seat_action(role, brief_path, worktree, root)`: the launch dict now inline in
  `build.next_action` (lines 138 to 142): `{'action': 'launch', 'brief': str(path),
  'worktree': str(tree), 'runtime': registry.runtime_config(role, config, root)
  ['adapters']['runtime'], 'agent_type': 'wuwei:' + role, 'prompt': launch_prompt(path,
  security.agent_path(root, role), root=root)}`, with `config = workspace.load_config(root)`.
  Paths are passed already resolved by the caller.

### `cli/wuwei/commands/build.py`

- `next_action`: use `brief.events(root)` for the builder brief lookup and
  `brief.seat_action('builder', path, tree, root)` for the launch. Behaviour and output
  identical (existing `tests/test_build_next.py` covers it).
- `open_fix`: the phase check at line 180 accepts `('gate', 'raised')`. In the no-resume
  branch (line 187) name the feedback brief `f'{item}-gate-fix'` when the phase is `gate`
  and `f'{item}-pr-fix'` otherwise. Nothing else changes (budget check, resume, record
  reset, `build.fix_opened` write, final `next_action`).

Must not change: `check`, `complete_checks` (its `implement -> gate`, `fix -> delta`
moves), `stopped`, `record_result`, `run_loop`, the Codex path.

### `cli/wuwei/dispatch.py`

- `next_step(item, root=None)`: set `root = workspace.find_workspace(root)` first (the CLI
  passes `None`; `open_fix` and the seat helpers need a path).
- Gate-phase FIX (lines 101 to 103): build `feedback` with one line per failing role,
  `f'Gate {role} FIX: fix only the blocking findings (blocks: yes) in {record["file"]}.'`,
  call `build.open_fix(item, feedback, root=root)` (lazy `from wuwei.commands import
  build`, as `pr_actions` does), then return `_fix(item, failures)`.
- Fix phase (lines 74 to 81): return `_fix(item, roles)` instead of the bare dict.
- `_fix(item, roles)`: `{'action': 'fix', 'roles': roles, 'command': 'wuwei build next ' +
  shlex.quote(item)}`.
- Missing roles (lines 95 to 97): return `{'action': 'gates', 'roles': missing,
  'seats': _seats(root, data, item, missing, round_name)}`.
- `_seats(root, data, item, roles, round_name)`. For each role:
  - initial: from `brief.events(root)`, the latest row with `kind == 'brief written'`,
    payload `item == item`, `role == 'sentinel-' + role`, `gate is True`, and
    `payload['name'] not in data['seats']` (a launch reserves the seat in the same write as
    its `seat launched` event, so an absent seat means never launched); if found, append
    `{**brief.seat_action('sentinel-' + role, root / payload['path'],
    payload['worktree'], root), 'receive': receive}`.
  - delta: `first = _record(data, item, role, 'initial')`; `name =
    Path(first['file']).stem.removeprefix('gate-')`; `seat = data['seats'].get(name)`;
    only when `seat` is stopped, has an `agent_id`, and still sits at the first verdict's
    HEAD (`str(seat.get('head') or '').lower().startswith(first['head'].lower())`, the
    comparison `receive` uses; the continuation's reservation moves the seat head to the
    fixed HEAD, so a continued seat is not offered again):
    `feedback = f'Delta review: the fix round changed {first["head"]}..HEAD. Re-check your
    findings at the current HEAD and rewrite {first["file"]}.'`; `action =
    brief.seat_action('sentinel-' + role, root / seat['brief'],
    data['items'][item]['worktree'], root)`; append `{**action, 'action': 'continue',
    'resume': seat['agent_id'], 'feedback': feedback, 'prompt': action['prompt'] + '\n\n' +
    feedback, 'receive': receive + ' --round delta'}` (the same `prompt + '\n\n' +
    feedback` join as `complete_checks` and the Claude adapter's `continue_job`).
  - `receive = 'wuwei dispatch receive ' + ' '.join(map(shlex.quote, (item, role, name)))`.

Must not change: `receive` (all its checks), `_item`, the escalate rules and their order,
the `raise` result, `ROLES`, `discovery`, `tracker_call`.

### `cli/wuwei/state.py`

- `PHASES['fix'] = ('delta', 'merged', 'parked', 'escalated')` and
  `PHASES['delta'] = ('raised', 'fix', 'merged', 'parked', 'escalated')`.

Must not change: every other edge, `_move`, `_validate`, `record_pr`.

### `cli/wuwei/pr_actions.py`

- `observe`, line 221: `item['phase'] in ('raised', 'fix', 'delta')`. The existing
  `pr.action` write carries `phase_changes`.

Must not change: `classify`, actions, deadlines, `_fix`, `_thread`, `act`.

### `cli/wuwei/commands/event.py`

- `EVENT_PRODUCERS['build.fix_opened']`: `'wuwei pr act or wuwei dispatch next'` (the
  producer hint names both callers of `open_fix`).

### Nothing changes in `cli/wuwei/report.py` or `cli/wuwei/commands/status.py`

Both read the item phase; with the phase right they agree with the host. The acceptance
tests prove it.

### Docs, skill and charter

- New `docs/site/daily.md` (front matter `---\nlayout: default\n---\n`, `[Home](index.html)`):
  sections Install (signed asset, `curl -fL`, `tar -xzf`, `/plugin marketplace add`,
  `/plugin install`, `bin/wuwei init .`, `plugin integrity: clean`), Configure
  (`.wuwei/config.toml`, `bin/wuwei config check`, `bin/wuwei goals edit` on the host),
  Plan (`/wuwei plan`, the morning gate questions, what `plan approve` records), Through
  the day (the status line and `bin/wuwei nudges`; the planner's loop: `worktree add`,
  `brief`, `build next` / `build check`, `dispatch next` and its `seats`, `command` and
  `receive`, `pr raise`, `pr state` and `pr act`; phases move by themselves, with the
  phase list), Owner decisions (host terminal: `decision outcome`, `drafts approve` /
  `drafts drop`, `mcp decide`), Close (`retro`, `close --check retro`, `report`, `close`,
  the Stop hook), and one closing line: anything else is on the recovery page. Name every
  command the scripted solo run issues (T013 checks it). Do not name `state transition`,
  `runtime dispatch`, `runtime continue` or `integrity reconfirm`.
- New `docs/site/recovery.md`: one short section each for `state transition` (move a
  phase by hand when evidence and state disagree; the legal phase table stays in the
  reference), `runtime dispatch` and `runtime continue` (the planner uses them for lead and
  shepherd seats; by hand only to relaunch a lost seat, return a rejected verdict to its
  seat, or continue a Codex seat with its job), `integrity reconfirm` (development
  checkouts and changed installs), plus pointers to `state recover` and the host terminal
  actions in the reference. Each is named "recovery, not daily use". Move the
  `docs/site/concepts.md` "Seat launch contract" section here (lines 17 to 37).
- `docs/site/index.md`: add `- [Daily path](daily.html)` first and
  `- [Recovery](recovery.html)` to the page list; "Start here" ends with a pointer to the
  daily path. Keep every phrase `tests/test_docs.py` requires.
- `docs/site/concepts.md`: line 11 drop the "Planned:" sentence (say `/wuwei plan` runs
  the day and link the daily path); line 58 replace the paragraph with the day flow as it
  runs today and a link to the daily path; replace the moved launch-contract section with
  one sentence linking recovery; Builder steps (line 125) keep.
- `docs/site/security.md` line 50: the signed manifest, workspace integrity, prompt canary
  and honeytoken are current tamper-evidence controls (spec 7.1), not tamper-proofing
  (9.1); link `docs/integrity.md` content via the repository URL as the page already does
  for the design spec. Line 48 ("more hardening for Claude seats") is not about these and
  stays.
- `docs/site/reference.md`: "Automatic phases" row: `dispatch next` moves `gate` to `fix`
  when it returns `fix`; an observed merge moves `raised`, `fix` or `delta` to `merged`.
  "Delta continuation" row: `dispatch next` returns the `continue` action with `resume`.
  Phase table rows for `fix` and `delta` gain `merged` (the table test reads
  `state.PHASES`). "Item phase order" intro: `state transition` is a recovery command, link
  recovery.
- `skills/wuwei-plan/SKILL.md` lines 26 and 44 to 48: gates are launched from `seats`
  (`launch`: Agent with `prompt`, `agent_type`; `continue`: Agent with `resume` too), then
  run each action's `receive` after its seat stops; `fix`: run `command` and the builder
  step loop, no transition; delta continuation comes from `seats`; `runtime continue` only
  for recovery. Keep the phrases `tests/test_docs.py` checks (`wuwei worktree add`,
  `wuwei rank .wuwei/days/`).
- `charters/planner.md` line 14: gates come from `dispatch next` `seats`; `runtime
  dispatch` stays for lead and shepherd seats. Then regenerate `agents/planner.md` with
  `bin/wuwei agents build` from the repository root (the golden test
  `tests/test_agents.py::test_checked_in_agents_match_charters_and_allowlist` fails on
  drift).

Must not change: README and `docs/site/index.md` install phrases, the host terminal
actions sections, `docs/site/configuration.md`, `templates/`, `scripts/headless_e2e.py`.

## Tests

- `tests/test_dispatch.py`: new tests for FR-001 to FR-005; the two exact-dict asserts on
  `gates` (lines 34 and 76) gain `'seats': []`; `test_fix_pass_then_only_quality_delta` and
  `test_agent_surface_delta_rescans_and_keeps_manual_findings` reach `fix` from `gate`, so
  they add a completed build record (`test_pr_actions.completed_build`) and drop the manual
  `state.transition('A', 'fix', root)` that follows `next_step`.
- `tests/test_pr_actions.py`: FR-006 and User Story 2.
- `tests/test_state.py` `test_all_transition_edges`: `fix` and `delta` edges gain `merged`.
- `tests/fakes/day.py` and `tests/test_e2e_day.py`: the driver records each planner and
  owner CLI call; `Day.gate` writes the brief with the gate role name and executes the
  `seats` action from `dispatch next`; the fix round runs `command` then executes the
  builder `continue`; the scripted day drops `day.transition('fix')`; a new solo run is the
  fourth dry run.
- `tests/test_docs.py`: daily and recovery pages, index links, no "planned" for
  implemented protections.
