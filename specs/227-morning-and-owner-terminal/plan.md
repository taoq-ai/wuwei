# Implementation Plan: The morning before the first plan, owner actions on a terminal, and operator records

**Branch**: `227-morning-and-owner-terminal` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

Twelve small fixes, each at the one function every caller already routes through. The morning: `status` stops refusing a day without `state.json` (it already has `state.read_state` for that) and says `no plan yet` until the gate is approved; the obligations empty-day check accepts the `prs_seen` marker that every CLI state write already records, whatever its event kind; `status.scan` itemises the shorter `sweep obligations` event. Owner terminal: `integrity._host_confirm`, the one confirmation helper, raises one sentence instead of an errno. Records: report JSON, build check output, rejection dedupe by file content, the recovery nudge text, answered threads, draft bodies out of SessionStart, `rank` accepting a lead JSON, and docs.

## Technical Context

Python 3.11+ stdlib runtime (`json`, `hashlib`), pytest for tests. Reuse: `state.read_state` (absent file handling and snapshot check), `state._write_state` (`prs_seen` marker), `commands.event.FREE_KINDS`, `obligations._time`, `obligations._owner_login`, `obligations._replies` logic (extracted, not copied), `drafts.read`, `integrity._host_confirm`, the `metrics` command's serialisation, and test helpers `tests/test_watch.py` (`case`, `advance`, `events`), `tests/test_obligations.py` (`case`, `sweep`, `sweep_event`), `tests/test_state.py` (`corrupt`, `events`), `tests/test_integrity.py` (the `builtins.open` pty pattern in `test_host_confirmation_uses_a_nonseekable_terminal`), `tests/test_templates_errors.py` (`cli`, `workspace`). No new dependency, adapter operation, config key, state key or event kind.

## Constitution Check

Stdlib only. Exits stay 0/1/2; every new failure is exit 2 with its reason. No guard refuses less: a lost state (snapshot present) still fails closed everywhere; the empty-PR contradiction check is unchanged; the only trust widened is `prs_seen` from reserved event kinds, which only `state._write_state` writes (`wuwei event` refuses every kind but `note`, and `note` stays excluded). Test first. Passes before and after design.

## Design

### 1. Status before the plan (`cli/wuwei/commands/status.py`)

- `scan` (lines 27-28) and `snapshot` (lines 123-124): delete the two `if not (directory / 'state.json').is_file(): raise FileNotFoundError(...)` guards. `state.read_state(directory=directory)` already returns defaults for an absent file and raises `ValueError` (naming `wuwei state recover`) when `state.snapshot.json` exists, which `run` already turns into `WUWEI ? unmeasured`, exit 2.
- `snapshot`: add `'gate_approved': data['gate_approved']` to `result`.
- `run`, line mode: the first part becomes `WUWEI no plan yet | pages N` when `not data['gate_approved']`, else `WUWEI pages N` as today. Example before the plan: `WUWEI no plan yet | pages 0 | nudges 0 | watch off | meeting unmeasured`. Pages and nudges stay visible so a page before the plan is never hidden.
- `scan` sweep itemisation (lines 81-88): read each count as `payload.get(field, 0)` in both the validity check and the loop, so the `sweep obligations` event (which has no `stale_owed`, `watch_dead`, `scanner_owed`) is itemised by source instead of falling to `classify` with reason `watch: sweep`. A present but non-integer count still falls through to `classify` as today. Itemisation also requires that the counts cover `owed` when `owed` is an integer: an event whose `owed` exceeds the sum of its known counts (an unknown cause) still falls through to `classify`, so no owed cause is hidden (kept `test_nudges_show_current_conditions` green).
- Do not touch `cli/wuwei/commands/nudges.py`: its `FileNotFoundError` branch still covers "not in a workspace" (`workspace.find_workspace`).

### 2. Obligations with no PR yet (`cli/wuwei/obligations.py`)

- `evaluate` (lines 210-211): delete the `if not (directory / 'state.json').is_file(): raise ValueError('day state missing')` guard; `state.read_state(directory=directory)` on the next line keeps the snapshot check.
- `_check_empty_day(directory)`: keep the loop and the contradiction rule byte for byte, change only what counts as proof and when events must exist:
  - `written = (directory / 'state.json').exists()`.
  - Read `events.jsonl` when `written` or when the file exists; when neither, the day is fresh and there is nothing to read (return). A written state with no events file still raises `FileNotFoundError` (unreadable), as today.
  - `recorded_state |= kind not in FREE_KINDS and type(payload.get('prs_seen')) is bool`, evaluated for every row, not only `state.*` kinds. Import `FREE_KINDS` from `wuwei.commands.event` (precedent: core modules already import from `wuwei.commands`).
  - Raise `no recorded PR state for today` only when `written and not recorded_state`.
- `_replies` (lines 103-110): extract `answered(thread, me)` returning True when the latest human (non-bot) comment of the thread, sorted by `(_time(created_at), id)`, is by `me`. `_replies` keeps its behaviour: `humans and not answered(...)` owes a reply, and the bot-P1 branch is unchanged. Keep the sorted comment list local where `_replies` still needs `comments[0]`.

### 3. Owner terminal sentence (`cli/wuwei/integrity.py`)

- Add `HOST_TERMINAL = 'this is an owner action: run it in a host terminal'` next to `_host_confirm`.
- `_host_confirm`: when opening `/dev/tty` (either handle) raises `OSError`, raise `OSError(HOST_TERMINAL) from None`; when either handle is not a tty, raise `OSError(HOST_TERMINAL)` instead of returning False. Close anything opened. The prompt and comparison are unchanged.
- No caller changes: `decision outcome` and `state recover` surface it through `__main__` as `wuwei decision: ...` / `wuwei state: ...` with exit 2 (`state.recover` calls `confirm` before any write); `reconfirm` returns `Result(2, 'host confirmation unmeasured: ' + ...)`; `mcp decide` keeps its `_failure` wording.
- Do not add a terminal check to `drafts approve` (spec Assumptions).

### 4. Report metrics as JSON (`cli/wuwei/report.py`)

Line 70: replace `str(measured)` with `json.dumps(measured, sort_keys=True, allow_nan=False)` (the `wuwei metrics` serialisation); add `import json`.

### 5. Build check prints the failing output (`cli/wuwei/commands/build.py`, `run`)

In the `check` branch, after `code == 1` reads `action`: if `action.get('action') == 'continue'`, print `action['feedback']` to stderr. The park message stays as is. `complete_checks`, the feedback format and `_signature` do not change.

### 6. One rejection per verdict file version (`cli/wuwei/verdict.py`, `cli/wuwei/metrics.py`)

- `verdict.record_rejection`: before `append_event`, compute `sha256` of `Path(path).read_bytes()`, `None` on `OSError`; add `'sha256': digest` to the `verdict.rejected` payload. Callers (`lint_file`, `guards/verdict.py`) do not change.
- `metrics.collect` line 428: `verdict_lint_rejections` becomes the number of distinct `(str(payload.get('file')), payload.get('sha256'))` pairs over `verdict.rejected` events. Older events without `sha256` dedupe per file. `tests/test_metrics.py` (one event, count 1) stays green.
- `cli/wuwei/decision.py` `record_rejection` (decision records) is a different metric source and does not change.

### 7. Recovery nudge text (`cli/wuwei/state.py`, `recover`)

Line 418: payload becomes `{'snapshot': digest, 'reason': f'state recovered from snapshot {digest[:12]}', 'error': reason}`. `status.scan` shows `reason`, so the nudge now names the recovery; the old error stays in the event for audit.

### 8. Answered threads are not candidates (`cli/wuwei/discovery.py`, `discover`)

In the code-host branch, before the ref loop: `me = obligations._owner_login(config)`, set to `None` on `ValueError` (answered cannot be decided without one owner login; today's behaviour then holds). Line 149: `if not row['resolved'] and not (me and obligations.answered(row, me)):`. Threads without a `comments` list (fakes, older payloads) are not answered: `answered` must treat a missing or empty comment list as not answered. Import `obligations` inside `discover` or at module top, whichever avoids a cycle (`obligations` does not import `discovery`).

### 9. SessionStart without draft bodies (`cli/wuwei/memory.py`, `session_payload`)

After `data.pop('watch', None)`: `data['drafts'] = {key: row['destination'] for key, row in drafts.read(data).items()}` (import `drafts` inside the function). `drafts.read` validates the queue and raises `ValueError` on a bad record, which `lifecycle.session_start` already reports as `memory unmeasured` (exit 2). A day with no drafts shows `"drafts": {}`.

### 10. Rank accepts a lead JSON (`cli/wuwei/commands/rank.py`, `run`)

After `rows = json.loads(source)`: `if isinstance(rows, dict): rows = rows.get('candidates')`. A dict without a list then fails in `rank.rank` with `candidates must be a list` (exit 2). `cli/wuwei/rank.py` does not change.

### 11. Docs and skill

- `docs/site/reference.md`:
  - New section `## Host terminal actions`: a table of commands the agent hooks refuse and that the owner runs in a host terminal: `wuwei decision outcome`, `wuwei state recover`, `wuwei integrity reconfirm`, `wuwei mcp decide`, `wuwei drafts approve` and `drafts drop`, `wuwei goals edit` and `voice edit`, `wuwei watch uninstall`; mark which ask you to type a digest (decision outcome, state recover, integrity reconfirm, mcp decide) and say that without a terminal they exit 2 with `this is an owner action: run it in a host terminal`.
  - Lead plan JSON section: `bin/wuwei rank FILE` (or `-`) accepts a candidate list or a whole lead JSON, such as `plan template` output or today's `.wuwei/days/<date>/proposal.json`, and ranks its `candidates`.
  - Watch state section: before the morning gate is approved the line starts `WUWEI no plan yet` and exits 0; with a lost state (snapshot present) it stays `WUWEI ? unmeasured`, exit 2.
  - New `## Raising a PR` (or a row next to PR ownership): `bin/wuwei pr raise OWNER/REPO --base BRANCH --title TEXT --body-file PATH --item ITEM`, all required; the body file must be a regular file; the item must be approved with a recorded worktree; the pre-PR gate runs first.
- `docs/site/concepts.md`: a short `## Host terminal actions` paragraph naming the same commands and linking to the reference section.
- `skills/wuwei-plan/SKILL.md` line 13: replace "Propose ranks with `wuwei rank`." with "Save the lead JSON to `.wuwei/days/<date>/lead.json` and order it with `wuwei rank .wuwei/days/<date>/lead.json`; `rank` reads the `candidates` of a lead JSON."

## What must not change

- `state.read_state`, `state._write_state`, the snapshot and `state recover` flow, and every guard in `cli/wuwei/guards/`.
- The obligations contradiction rule (any `prs_seen` true, a `state.set` of `raised_prs`/`claimed_prs`, an obligations sweep with PRs, or a `reply: acknowledged` makes an empty PR set unreadable).
- `signal.classify`, `SILENT`, and the `watch.sweep` payload.
- Builder feedback text, `_signature` and the stuck-loop rules.
- `drafts approve` behaviour and the cockpit.
- `rank.rank` and `rank template` output.

## Existing tests that change on purpose

- `tests/test_signal_status.py::test_unreadable_state_fails_closed`: the `None` (absent `state.json`) case now exits 0 with `no plan yet`; keep `{broken}` at exit 2 and add the snapshot-present case at exit 2.
- `tests/test_state.py::test_recover_restores_last_written_state`: may additionally assert the new `reason` and `error`.

## Test locations

Tests go next to the module they cover (fixtures already exist there): `tests/test_signal_status.py`, `tests/test_obligations.py`, `tests/test_watch.py`, `tests/test_integrity.py`, `tests/test_decision.py`, `tests/test_state.py`, `tests/test_report_retro.py`, `tests/test_build_next.py`, `tests/test_metrics.py`, `tests/test_goals_rank.py`, `tests/test_templates_errors.py`, `tests/test_docs.py`. Note for the fresh-day watch test: the `case` fixture in `tests/test_watch.py` has no `runtime` port, so `steward.run` inside `watch.sweep` reports `watch steward unmeasured: 'runtime'` on a fresh day; stub `steward.run` (or add the port) the way other sweep tests in that file do, and assert the sweep's own obligations fields as well as the exit code.
