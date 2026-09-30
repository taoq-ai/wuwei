# Implementation Plan: Operator records and owner-action consistency after the fourth dry run

**Branch**: `247-records-after-dryrun4` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

Seven small fixes, each at the one function its callers already route through: `status.scan` clears `steward.due` on `steward.run`; `state._move` marks `merged` items `done`; `steward.run` owns the once-per-day close check that `close.py` holds today; `workspace.load_config` names `config.toml` and the integrity guard stops relabelling it; `report` and `build check` print JSON; `drafts.approve` confirms through `integrity._host_confirm` like every other owner action; `init` prints two hints. Plus help text, the retro skill step and the reference page.

## Technical Context

Python 3.11+ stdlib runtime (`json`, `hashlib`), pytest for tests. Reuse: `integrity._host_confirm` and `integrity.HOST_TERMINAL` (the shared owner confirmation, #227), `watch.records` (event reader `close.py` already uses), `state._move` (every phase move), `workspace.ConfigError`, test helpers `cli` and `day` in `tests/test_signal_status.py`, the `seat` fixture in `tests/test_build_next.py`, the `root`/`port` fixtures in `tests/test_drafts.py`, the `/dev/tty` patch pattern in `tests/test_decision.py:600-617`. No new dependency, adapter operation, config key, state key or event kind.

## Constitution Check

Stdlib only. Exits stay 0/1/2: the drafts no-terminal path is exit 2 with its reason, a declined digest exit 1. No guard refuses less: the integrity guard still refuses (exit 2) on a config error, only its message changes; `steward.run` is reserved to its producer (`commands/event.py:49`), so the close no-op cannot be forged by a seat. One behaviour, one function: the close-review check moves from `close.py` into `steward.run`. Test first. Passes before and after design.

## Design

### 1. `steward.due` clears on a run (`cli/wuwei/commands/status.py`, `scan`)

Insert before `if kind in SILENT: continue` (line 67), next to the existing `draft.*` pop at lines 61-63, the same shape as the `mcp.checked` clear at line 52-54:

```python
if kind == 'steward.run':
    current = {key: value for key, value in current.items() if key[0] != 'steward.due'}
```

`steward.run` stays silent and falls through to the `continue`. A later `steward.due` is added again by the normal path. One comprehension on a rare event keeps `scan` inside the latency budget. Do not touch `signal.py` or `nudges.py`.

### 2. `steward ack` ids (`cli/wuwei/commands/steward.py`, `docs/site/reference.md`)

- `register`: `actions.add_parser('ack', help='acknowledge a steward steering note')` and `ack.add_argument('id', help=...)` naming: the id is a steering note id of the form `<item>-fix-3`, named by the refusal `steward note <id> requires planner acknowledgement`; a `steward.due` nudge is not a note and clears when `wuwei steward run` records a run. No `%` in the help string (argparse formatting).
- `docs/site/reference.md`: add a short `## Steward` section between `## Retro and merge configuration` (line 38) and `## Codex companion protocol` (line 44); #238's hunks are at lines 92-110. The section covers `steward run --trigger sweep|close|tool-calls` printing `steward_launch`, the once-per-day close review (section 4 below), and the `steward ack` id text above.

### 3. Merged items are done (`cli/wuwei/state.py`, `_move`)

After `current['phase'] = phase` (line 372):

```python
if phase == 'merged':
    current['status'] = 'done'
```

Every move to `merged` goes through `_move`: `state.transition` (CLI `state transition`) and `pr_actions.observe` (line 222). `_validate` already accepts `done` (`STATUSES`, line 39). Do not change `ITEM_DEFAULTS`, `_validate`, `retro.py` or `report.py`; the retro Cycle row then reads `merged | done` (already asserted by `tests/test_report_retro.py:36`). #238 edits `PHASES` in this file, not `_move`.

### 4. One close steward review per day (`cli/wuwei/steward.py`, `cli/wuwei/commands/close.py`, `skills/wuwei-retro/SKILL.md`)

- `steward.run`: right after `day = workspace.day_dir(root)` (line 111), before `review`, `decision_queue` and `brief.write`:

  ```python
  if trigger == 'close':
      prior = [row['payload'] for row in watch.records(day / 'events.jsonl')
               if row['kind'] == 'steward.run' and row['payload'].get('trigger') == 'close']
      if prior:
          print(f"steward: close review already ran today (brief {prior[0].get('brief')})")
          return 0
  ```

  `watch` is already imported. No brief, no dispatch, no event on the no-op.
- `commands/close.py`: replace lines 23-25 with an unconditional `steward.run(root, trigger='close')`; the `watch` import goes if unused. The first `close` still prints `steward_launch`; a repeated `close` prints the no-op line before its findings.
- `skills/wuwei-retro/SKILL.md` step 1: replace the "Run `wuwei steward run --trigger close` if today's close review has not run" sentence with: run `wuwei close` first if it has not run today; it runs the close steward review once and prints `steward_launch` (launch that steward with Agent exactly as returned), then refuses until the retro exists. Do not run `wuwei steward run --trigger close` yourself; a second close review the same day writes no brief and says so. Keep "Read captured role notes, verdicts, events and the steward metrics." Steps 2-4 unchanged.
- Do not touch `charters/`, `agents/`, `docs/site/concepts.md` or `scripts/headless_e2e.py` (#238, #239 in flight); the headless prompt already runs `close` before the retro.

### 5. `config.toml:` messages (`cli/wuwei/workspace.py`, `cli/wuwei/guards/integrity.py`)

- `workspace.load_config` line 430: `raise ConfigError(f"config.toml: {exc}") from exc`. The `path` variable stays for reading and resolving repos.
- `guards/integrity.py`, both `except (OSError, ValueError, TypeError) as exc:` blocks (lines 14-15 and 27-28): return `2, str(exc) if isinstance(exc, workspace.ConfigError) else f'integrity unmeasured: {exc}'`. `workspace` is already imported. `integrity.cached` and `integrity.check` in `cli/wuwei/integrity.py` are unchanged.
- Leave the other guards' prefixes, `commands/config.py` (#243), `commands/hook.py` and `guards/__init__.py` (#240) alone.

### 6. JSON instead of reprs (`cli/wuwei/report.py`, `cli/wuwei/commands/build.py`)

- `report.build`: add a local `def shown(value): return json.dumps(value, sort_keys=True, allow_nan=False) if isinstance(value, dict) else value` and wrap both the measured value and the baseline value in the four Outcome lines (34-37). `json` is already imported.
- `commands/build.py` line 360: `feedback = '\n'.join(f'{name}: {json.dumps(data)}' for name, data in failures)`. `json` is already imported. `_signature` is unchanged. #238's hunks in this file are elsewhere (`next_action`, `open_fix`).

### 7. `drafts approve` confirms (`cli/wuwei/drafts.py`, `docs/site/reference.md`)

In `approve`, change the local import to `from wuwei import integrity, registry, security`. After `size` is computed (line 143) and before `def claim`:

```python
digest = sha256((draft_id + '\n' + text).encode()).hexdigest()
try:
    confirmed = integrity._host_confirm(digest, prompt=(
        f"Send this draft to {row['destination']}:\n{text}\nTo confirm, type:"))
except OSError as exc:
    return registry.Result(2, reason=str(exc))
if not confirmed:
    return registry.Result(1, reason='drafts: owner confirmation declined')
```

(`from hashlib import sha256` local import.) The lint and security checks still run first; the claim (`current != row`) still guards a change during confirmation. The inner `except OSError` returns the owner-action sentence unchanged instead of the generic `drafts: cannot read, edit, validate or record approval`. Look up `integrity._host_confirm` at call time so tests can patch `wuwei.integrity._host_confirm` as they do for `decision outcome`. `commands/drafts.py` already prints the reason to stderr on a nonzero exit; no change there. `drop` is unchanged.

`docs/site/reference.md` host terminal table (line 179): split into `| \`bin/wuwei drafts approve <id>\` | yes |` and `| \`bin/wuwei drafts drop <id>\` | no |`, and in the paragraph under the outward draft queue table (line 59) say approval asks for a typed digest of the draft on the host terminal.

### 8. `init` hints (`cli/wuwei/commands/init.py`)

- Add `_status_line(executable)` that prints the existing `statusLine` JSON line and then one line: `Status line: put the "statusLine" key above in .claude/settings.json (this project) or ~/.claude/settings.json (every project).` Use it at lines 84-85 (`run`) and 227-228 (`upgrade`), replacing both duplicated `print(json.dumps(...))` calls. The JSON stays the second line of fresh `init` output (`tests/test_signal_status.py:185-187` and `:387`).
- In `run`, after `_status_line`, when `(destination.parent / '.git').exists()`: print `This project is a Git repository; add these lines to its .gitignore:`, then `.wuwei/` and `.claude/`. Stdlib path check only; the core never runs `git` here.
- Do not write any settings file.

## What must not change

- Guard verdicts: every refusal stays a refusal with the same exit code.
- `steward.run` for `sweep` and `tool-calls`; `steward.maybe_run_for_tool_calls`; the `steward.run` payload.
- The `statusLine` JSON content and its line position; the `status --line` format.
- `drafts drop`, the drafts queue schema and the `draft.*` events.
- Files owned by in-flight issues: `docs/site/daily.md`, `docs/site/concepts.md`, `tests/test_e2e_day.py`, `scripts/headless_e2e.py`, `cli/wuwei/guards/__init__.py`, `cli/wuwei/commands/config.py`, `tests/test_docs.py`, `tests/test_state.py`.

## Files

| File | Change |
|---|---|
| `cli/wuwei/commands/status.py` | clear `steward.due` on `steward.run` in `scan` |
| `cli/wuwei/commands/steward.py` | `ack` help text |
| `cli/wuwei/state.py` | `_move`: `merged` sets `done` |
| `cli/wuwei/steward.py` | `run`: once-per-day close no-op |
| `cli/wuwei/commands/close.py` | call `steward.run` unconditionally |
| `skills/wuwei-retro/SKILL.md` | step 1 text |
| `cli/wuwei/workspace.py` | `config.toml:` prefix |
| `cli/wuwei/guards/integrity.py` | pass `ConfigError` through |
| `cli/wuwei/report.py` | JSON for mapping values |
| `cli/wuwei/commands/build.py` | JSON check feedback |
| `cli/wuwei/drafts.py` | host confirmation in `approve` |
| `cli/wuwei/commands/init.py` | status line and `.gitignore` hints |
| `docs/site/reference.md` | Steward section, drafts approve digest |
| `tests/test_records_after_dryrun4.py` | new acceptance tests |
| `tests/test_drafts.py` | confirmation stub in fixtures, no-terminal and declined tests |
| `tests/test_steward.py` | rewrite `test_close_retry_uses_existing_steward_run` for the moved check |
| `tests/test_build_next.py` | JSON feedback assertion |
