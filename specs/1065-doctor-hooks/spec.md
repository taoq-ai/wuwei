# Spec: doctor counts any hook that fired in this clone since init (#1065)

## In my words

`wuwei doctor` says `ok hooks` today only when `.wuwei/executable` exists, and only SessionStart
writes that file. When the hooks load after a session starts, PreToolUse and PostToolUse still
fire and record rows, yet doctor says the doors are off. After this change doctor also says
`ok hooks` when this clone's own ledger file holds a row only a hook writes, after the latest
`workspace.init` in that file.

Hook-only rows: `refused`, `asked`, `note`, `prompt`, `seat.started`, `seat.stopped`,
`stop.reminded`, `hook.error`. `attest` and `sent` do not count, because the CLI writes them too.
Rows in another clone's file do not count: the ledger travels on `wuwei/state`, so another
machine's hook says nothing about this one. `traces.jsonl` is not read; it exists only with
telemetry on.

## Acceptance scenarios

1. After init, a `refused` row in this clone's file and no `.wuwei/executable`: `ok hooks`.
2. A hook-only row only in another clone's file: `warn hooks`.
3. A hook-only row older than the latest `workspace.init`, no `.wuwei/executable`: `warn hooks`.
4. `.wuwei/executable` written by SessionStart: `ok hooks`, as today.
5. The runtime size test still passes at 3,000 lines or fewer.

## Requirements

- FR-1: doctor reads only `.wuwei/ledger/<ws.clone(root)>.jsonl` for hook evidence.
- FR-2: only rows after the last `workspace.init` in that file count; with no init row, every row counts.
- FR-3: `.wuwei/executable` still gives `ok hooks` on its own.
- FR-4: setup.py frees the lines it adds, so the runtime stays at 3,000 lines.

## Assumptions

- File order in this clone's file is append order, so "after the latest init" is file position,
  not `ts`. Overturned if a row could be written out of order (record() appends under a lock).
- A clone file with no `workspace.init` row (a clone id reset after init) counts every row.
  Overturned if the owner wants a missing init to mean warn.
- doctor reuses `ws._parse`, which skips an unparsable line as `ledger()` does.
