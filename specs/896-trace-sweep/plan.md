# Implementation Plan: the trace sweep reads only new spans, and the scanner audit's polish

**Branch**: `896-trace-sweep` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`trace_sweep` keeps a byte offset in the day directory, parses the day's spans once, and
gives ZIRAN only new spans in windows of at most 20 spans per session, each window preceded
by the last earlier span of each tool its sessions used. Events and state are read once per sweep. The dedup key
gains the window start, so a resumed seat's repeat is a new finding. A failed sweep leaves
the offset, records its reason, and doctor shows it. Discovery renders relative paths with a
threshold and a cap; `why`, the version probe and the docs get their small fixes.

## Technical Context

Python 3.11+ stdlib. Files: `cli/wuwei/scanner.py`, `adapters/scanner/ziran.py`,
`cli/wuwei/discovery.py`, `cli/wuwei/workspace.py` (two schema keys),
`cli/wuwei/guards/protect_state.py`, `cli/wuwei/commands/doctor.py`,
`cli/wuwei/commands/why.py`, `templates/workspace/config.toml`, `docs/site/security.md`,
`docs/site/configuration.md`. No dispatch change (another builder works there).

## Constitution Check

- II: a failed window keeps the offset and the day unmeasured, with a doctor row; a damaged
  offset restarts from 0 (more analysis, never less).
- III: the window, offset and dedup live in `trace_sweep`, the one function receive and close
  call.
- IV: failing tests first for each change.
- V: one JSON file beside `scanner-audit.json`, one set in `registry`, `tempfile`; no new module.
- VII: #870 and #878 keep their behaviour; the offset file is protected from seat writes.

## Changes

1. `scanner.trace_sweep`: read `traces.jsonl` as bytes once. Read the offset from
   `trace-sweep.json`; use it only when it is an int in `[0, size]` at a line start, else 0.
   Parse each complete line: its sessions and whether a span names a credential path
   (`_credential_path` on `file_path`, `path`, `command`), keyed by raw id and sha256.
   Lines before the offset feed `carry[session] = line`; lines after it are cut into
   windows (`PER_SESSION = 20`). Each window: write carry lines of its sessions plus its
   lines to a temp file, call `traces`, raise on unmeasured, respond with `since`/`until`,
   then write the offset. Events and state load lazily once per sweep and the in-memory
   events list is appended as findings are recorded.
2. `_trace_response(finding, root, context)`: same branches; seat dedup on session, chain and
   `since`; the local-chain check compares the session's last credential read offset with
   the latest `until` of its recorded credential-read findings; a recorded chain parks again only
   when its source and sink tools are both in the window's new spans. The mark keeps the
   per-session last credential read and per-tool carry ranges, so a sweep parses new lines only.
3. Failure: the `except` writes `{offset, unmeasured: reason}` and appends
   `scanner.unmeasured` when the stored reason differs; stderr as before.
4. `doctor._day`: a `trace sweep` row from `trace-sweep.json`: `unmeasured` with the reason
   and the fix, else `ok`.
5. `protect_state._protected_name`: add `trace-sweep.json`.
6. `discovery.discover`: `Path(file).relative_to(checkout)` for absolute paths; filter by
   `scanner.discovery_threshold`; sort by severity; keep `scanner.discovery_rows`; append
   `<repo>: <n> more past scanner.discovery_rows` to the source line.
7. `workspace.SCHEMA['scanner']`: `discovery_threshold` (`"low"`), `discovery_rows` (50, min 1);
   template and configuration docs.
8. `why.EVENT_PRODUCERS['scanner.finding']`: the trace sweep or the honeytoken hook.
9. `ziran._version`: return early when `'ziran' in registry.CHECKED`, add it after a passed
   check (`registry.load` runs a fresh module per call, so the memo lives in `registry`);
   `tests/conftest.py` clears it per test.
10. `docs/site/security.md`: discovery, trace sweep, doctor row, switching off.
