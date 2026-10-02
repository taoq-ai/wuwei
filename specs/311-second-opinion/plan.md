# Implementation Plan: A second-opinion gate on a different model

**Branch**: `311-second-opinion` | **Date**: 2026-10-02 | **Spec**: `specs/311-second-opinion/spec.md`

## Summary

Make the second opinion one more gate in the item's recorded gate set, named `<role>@<runtime>`
(for example `quality@codex`). Because the gate set is the single shared spot that dispatch,
receive, the fix round, the delta, the PR guard and the merge policy all iterate, the disagreement
rule of the issue falls out of existing code. New code is limited to: the config key, recording
the second opinion at tiering, one blocking CLI runner that launches the gate through the runtime
adapter (the Codex polling pattern `build run_loop` already uses), the model and own-file lint in
the Codex adapter, per-verdict usage, and one retro section.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Tests run with `python -m pytest -q` from the
repository root. No real Codex call in tests: a fake runtime object through
`monkeypatch.setattr(registry, 'load', ...)` (pattern of `tests/test_runtime_cli.py` and
`tests/test_build.py`), and the fake companion of `tests/test_runtime.py` for adapter tests.

## Constitution Check

- Stdlib only, adapters behind the port: yes; the core never imports subprocess.
- Three-state exits, fail closed: the runner exits 2 on adapter errors, timeouts and unreadable
  state; a verdict is never recorded without lint.
- One behaviour, one function: the gate set stays in `dispatch.gate_set`; polling and usage
  normalization are extracted from `commands/build.py` and shared, not copied.
- Test first: every task below has its failing test first.
- Ponytail: no port change, no new state key, no new event kind, no new module.
- Security: no new trust. The Codex seat keeps its sandbox; the verdict it produces passes the same
  lint and receive checks; the Agent guard refuses the second-opinion brief.

## Design

### 1. Config (`cli/wuwei/workspace.py`, `templates/workspace/config.toml`, `docs/site/configuration.md`)

- `SCHEMA` gains a top-level table:
  `"gates": {"second_opinion": (str, "off"), "second_opinion_role": (str, "quality", ("arch", "quality", "security"))}`.
- `load_config`, after the cruise-level checks: when `second_opinion != "off"`, require
  `re.fullmatch(r'([a-z]+):([A-Za-z0-9][A-Za-z0-9._-]*)', value)` and the runtime in
  `registry.known('runtime')` and not in `('claude', 'none')`; else
  `ConfigError('gates.second_opinion: use "off" or "<runtime>:<model>" with a polling runtime (...)')`.
- Template: a `[gates]` table with commented `# second_opinion = "off"` and
  `# second_opinion_role = "quality"` lines and a one-line comment
  (`For STANDARD and FULL items, run one gate again on another runtime, for example "codex:<model>".`).
- `configuration.md`: `[gates]` in the Sections table and rows for `gates.second_opinion` and
  `gates.second_opinion_role` (existing `tests/test_docs.py` checks enforce both).

### 2. Tier and gate set (`cli/wuwei/dispatch.py`)

- `tier(root, config, row)` (return at lines 82 and 83): build the dict as today, then, when
  `effective != 'light'` and `config['gates']['second_opinion'] != 'off'`, add
  `second_opinion = {'role': config['gates']['second_opinion_role'], 'runtime': runtime, 'model': model}`
  from `value.partition(':')`. Off or light: the key is absent, so existing tier assertions hold.
- `gate_set(row)` (lines 15 to 22): after the roles check, read
  `second = (row.get('gates') or {}).get('second_opinion')`; when present it must be a dict whose
  `role` is in the returned roles and whose `runtime` and `model` match the config patterns, else
  `ValueError('invalid recorded gate set')`; return `(*roles, f"{role}@{runtime}")`.
- A one-line helper `base(gate)` returns `gate.partition('@')[0]`; used by receive and the PR guard.

### 3. Dispatch next (`dispatch._seats`, lines 205 to 237)

- Initial-round primary filter (lines 211 to 214): add `and not row['payload'].get('second_opinion')`
  so the second-opinion brief is never offered as an Agent launch.
- For a gate containing `@`: initial round, ready when a first-model gate brief for
  `sentinel-<base>` is logged; delta round, ready when its initial record is FIX (the caller
  already filters). Append `{'action': 'run', 'gate': gate, 'runtime': ..., 'model': ...,
  'command': 'wuwei dispatch opinion ' + shlex.quote(item)}` (no `receive`: the runner receives).
  No `run` action is offered while the second-opinion seat is `running`, so the planner never
  starts two runners on one job.
- Extract the delta feedback string (lines 230 and 231) into `_delta_feedback(first)` and use it
  from `_seats` and the runner.
- `next_step` itself does not change: `roles = list(gates)`, the fix branch, the delta branch and
  the escalate rules already take the second-opinion gate from `gate_set`.

### 4. Receive (`dispatch.receive`, lines 244 to 332)

- Replace the `role not in ROLES` and gate-set checks (lines 249 to 252) with one check:
  `role in gate_set(row)`; `base = base(role)`.
- Seat role check (line 262), lint role (line 271) and the two scanner conditions (lines 298 and
  330) use `base` instead of `role`.
- Sibling HEAD check (line 295): iterate `gate_set(row)` instead of `ROLES`.
- Value (lines 315 to 318) adds:
  - `'findings': [block.strip() for block in blocks]`;
  - `'usage'`: the seat's recorded `usage` when present (second opinion), else
    `build.normalize_usage({'duration': seconds} if both seat times else {}, model)` where
    seconds is `stopped_at - started_at` and model is `seat_policy['sentinel-<base>']['model']`
    when recorded;
  - for a second-opinion gate, `'runtime'` and `'model'` from the item's recorded `second_opinion`.
- The `gate.received` event payload is unchanged.

### 5. The runner: `dispatch.opinion(item, root=None)` and `wuwei dispatch opinion <item>`

In `cli/wuwei/dispatch.py`, about 50 lines, in this order:

1. `root`, `data`, `row = _item(data, item)`; `second = row['gates'].get('second_opinion')` (else
   `Refused('item has no second opinion')`); `gate = f"{role}@{runtime}"`; round is `initial` in
   phase `gate`, `delta` in phase `delta` (else `Refused`). If the record for the round exists,
   return it.
2. Seat name: initial, `f"{first}-{runtime}"` where `first` is the latest logged gate brief for
   `sentinel-<role>` without `second_opinion` (none: `Refused('write the <role> gate brief first')`);
   delta, the stem of the initial record's `file` without `gate-` (the initial record must be FIX).
3. Adapter: `registry.load('runtime', {**config, 'adapters': {**config['adapters'], 'runtime': runtime}})`.
4. Seat state:
   - no seat (initial only): when the brief is not yet written (a rerun after a failed dispatch
     reuses it), read the first-model brief file, take its body
     (`text.split('\n\n', 1)[1]`), call `brief.write('sentinel-' + role, item, name, body,
     gate=True, second_opinion=second, root=root)`; refuse at the host seat ceiling
     (`running seats >= config['host']['seats']`); `job = build._data(adapter.dispatch(
     'sentinel-' + role, str(root / relative), row['worktree'], True, root=root), 'dispatch')`;
     write the seat record `{id, role: 'sentinel-<role>', item, brief, head, status: 'running',
     started_at, runtime, model, job}` with event kind `seat launched`.
   - seat `running` with a `job`: poll that job (a rerun after an interruption).
   - seat `stopped`: delta feedback is `_delta_feedback(initial)`; initial (a rejected verdict)
     feedback is `Your verdict file was rejected by the verdict lint; rewrite <file> to the verdict
     contract in your brief.`; `job = build._data(adapter.continue_job(seat['job'], feedback,
     root=root), 'continuation')`; set the seat `running`, new `job`, `started_at` and `head` (the
     worktree's current HEAD through the vcs adapter), event `seat launched`.
5. `status = build.wait(adapter, job, config)` (extracted, see 6); `result =
   build._data(adapter.result(job, root=root), 'result')`.
6. Verdict path `day/decisions/gate-<name>.md`: if it is not a file written since
   `job.get('started_at')` (missing time counts as not written), `workspace.atomic_write(path,
   result['text'] + '\n')`; a symlink is refused (`Refused`).
7. One state write: seat `stopped`, `stopped_at`, `usage = build.normalize_usage(result.get('usage', {}),
   status.get('model') or model)` with `duration` set to the measured wall time when unreported;
   kind `seat.usage`, payload `{'item', 'role': 'sentinel-<role>', 'gate', 'usage'}`; then append
   `seat stopped` with `{'name': name}` (as `build.record_result` does).
8. `return receive(item, gate, name, round, root)`.

`cli/wuwei/commands/dispatch.py`: an `opinion` subparser with `item`; `run` calls `dispatch.opinion`
and prints the record. Exit mapping: `Refused` 1; `build.PortExit` its own code; `OSError`,
`ValueError`, `TimeoutError`, `RuntimeError` and the existing tuple 2.

A `ponytail:` comment on the continue call: resume-last resumes the latest Codex thread in the
worktree; a Codex builder in the same worktree is not supported with a second opinion.

### 6. Shared helpers extracted from `cli/wuwei/commands/build.py`

- `wait(runtime, job, config, root)`: the poll loop of `run_loop` (lines 439 to 450) moved verbatim,
  returning the last status dict; `run_loop` calls it. Same errors (`ValueError`, `RuntimeError`,
  `TimeoutError`).
- `normalize_usage(reported, model)`: the validation and five-key dict of `record_result` (lines
  221 to 237) moved verbatim; `record_result` calls it with `result.get('model') or model`.
- Existing `tests/test_build.py` stays green unchanged; this is a refactor under green.

### 7. Brief (`cli/wuwei/brief.py` `write`)

- New keyword `second_opinion=None` (the recorded dict). When set: header line
  `Model: <model>` after `Seat policy:` (line 233), and payload key
  `'second_opinion': '<runtime>:<model>'` (lines 283 to 286). Nothing else changes.

### 8. Codex adapter (`adapters/runtime/codex.py`)

- `dispatch`: read `brief.read_text().split('\n\n', 1)[0]`; when it has
  `^Model: ([A-Za-z0-9][A-Za-z0-9._-]*)$`, append `--model <model>` to `options`. Pass the brief
  path to `_started`.
- `_started(started, tree, role, started_at, root, brief)`: the job handle adds `'brief': str(brief)`.
  `continue_job` passes `job.get('brief')`.
- `result`: replace the glob over every `gate-*.md` (lines 133 to 135) with the job's own file,
  `decisions / f"gate-{Path(job['brief']).stem}.md"` when the job has a `brief`, linted only when
  it exists and was written since `started_at`. Jobs without `brief` (handles stored before this
  change) keep the old glob over every fresh `gate-*.md`, so they still fail closed.
- The port signature and the companion protocol in `docs/site/reference.md` stay as they are;
  the reference adds that a `Model:` brief header becomes `--model`.

### 9. Guards

- `cli/wuwei/guards/agent_launch.py`, after the hash check (line 102): a logged brief with
  `second_opinion` raises `brief.Refused('second-opinion brief runs through wuwei dispatch opinion, not Agent')`.
- `cli/wuwei/guards/pr.py` line 112: `quality=dispatch.base(role) == 'quality'`.
  `_recorded_gates` otherwise needs no change: it iterates `gate_set`.
- `cli/wuwei/merge.py` needs no change (iterates `gate_set`).

### 10. State producers and seat stop

- `cli/wuwei/state.py` `stop_seat` (lines 394 to 401): also set `stopped_at = workspace.now().isoformat()`.
- `STATE_PRODUCERS['seats']`: `'wuwei hook PreToolUse or wuwei dispatch opinion'`.
- `cli/wuwei/commands/event.py`: `seat.usage` `'wuwei build, wuwei dispatch opinion or SubagentStop'`;
  `seat launched` and `seat stopped` add `or wuwei dispatch opinion`. All three kinds stay reserved.

### 11. Retro (`cli/wuwei/retro.py` `compile`)

After the `## Gate verdicts` table, when any initial record in `data['gate_verdicts']` has a
`runtime`, append:

```
## Second opinion
| Item | Found only by | Finding |
| --- | --- | --- |
| A | quality@codex gpt-6-astra | P1 cli/x.py:3 fails when ... |
| A | quality | none |

| Item | Gate | Model | Cost | Duration |
| --- | --- | --- | --- | --- |
| A | quality | opus | unmeasured | 412 |
| A | quality@codex | gpt-6-astra | 0.42 | 380 |
```

Compare the second-opinion initial record with the initial record of its base role (same item).
Key per finding: first match of `verdict.CITATION` lowercased, else the whitespace-normalized
lowercase text. A finding row shows the block's first line with `|` replaced by `/`. A side with no
unique finding gets one `none` row. Records read with `.get('findings', [])` and
`.get('usage', {})`, so records written before this change render as `none` and `unmeasured`.
`ponytail:` comment: exact citation match; the same defect on different lines counts twice.

### 12. Planner docs

- `skills/wuwei-plan/SKILL.md` Item dispatch and receive: a role with `@` is a second opinion;
  never write a brief for it; a `run` entry in `seats` is executed through Bash in the background
  with the workspace executable; it writes its own brief and receives its verdict; call
  `dispatch next` after it exits. Exit 1 is a refusal or a rejected verdict (rerun continues the
  same seat); exit 2 is unmeasured.
- `docs/site/reference.md`: the `dispatch` command row names `opinion`; the Gate role names row
  adds `<role>@<runtime>`; the Codex companion section adds `--model` from a `Model:` header.
- `docs/site/concepts.md` Review tiers: one paragraph on the second opinion and the retro section.

## What must not change

- The runtime port (`registry.PARAMETERS`), the claude and none runtime adapters, and every fake
  runtime in tests.
- The tier rules, the recorded `roles` list, `ROLES`, `TIERS`, and the single fix round and delta
  rule in `next_step`.
- Verdict lint rules and the verdict shape; the `gate.received` and `gate.tiered` payloads.
- With `gates.second_opinion = "off"`: every action, record and event, byte for byte, apart from
  the added `findings` and `usage` keys on new verdict records and `stopped_at` on stopped seats.
- No new state key, no new event kind, no new module, no new dependency.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/workspace.py` | `gates` schema and validation |
| `templates/workspace/config.toml` | `[gates]` block |
| `docs/site/configuration.md` | section and two keys |
| `cli/wuwei/dispatch.py` | `tier`, `gate_set`, `base`, `_seats`, `_delta_feedback`, `receive`, `opinion` |
| `cli/wuwei/commands/dispatch.py` | `opinion` subcommand |
| `cli/wuwei/commands/build.py` | extract `wait` and `normalize_usage` |
| `cli/wuwei/brief.py` | `second_opinion` keyword |
| `adapters/runtime/codex.py` | `--model`, `brief` in job, own-file lint |
| `cli/wuwei/guards/agent_launch.py` | refuse second-opinion brief |
| `cli/wuwei/guards/pr.py` | base role for the quality lint |
| `cli/wuwei/state.py` | `stopped_at`, producer label |
| `cli/wuwei/commands/event.py` | producer labels |
| `cli/wuwei/retro.py` | `## Second opinion` section |
| `skills/wuwei-plan/SKILL.md`, `docs/site/reference.md`, `docs/site/concepts.md` | planner and reference text |
| tests | `test_workspace.py`, `test_dispatch.py`, `test_brief.py`, `test_runtime.py`, `test_agent_launch.py`, `test_pr_guards.py`, `test_report_retro.py`, `test_state.py` |

## Deferred

- Usage tokens and cost for Claude sentinels from the SubagentStop payload.
- A Claude-model second opinion, or several second-opinion roles.
- Resuming a specific Codex job id instead of `--resume-last`.
