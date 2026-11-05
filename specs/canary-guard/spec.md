# Feature Specification: one canary reader a broken file cannot raise, and the canary behind the ledger door

**Feature branch**: `fix/canary-guard`
**Item**: canary-guard, tier full, goal G-2
**Input**: the security gate on #1278 (probes `probe_canary_file.py` and `probe_write_canary.py`). A
`.wuwei/canary` that is not UTF-8 makes `seat.started` error and `_seat_stop` raise before it records
`seat.stopped` or keeps the report. The hook lets a seat write `.wuwei/canary` with Write or a Bash
redirect, while a ledger write is denied.

## The promise in my words

The hook reads the workspace canary in five places (#1285 moved every mask onto `hook.mask`, which
takes the canary as an argument). Each place reads the file inline with `read_text(encoding='utf-8')`,
so a file that is not UTF-8, or that the process cannot read, raises. The raise lands in
`hook.handle`, which records `hook.error` and drops the rest of the handler: no `seat.started`, no
`seat.stopped`, no kept report. One reader, `ws.canary(root)`, replaces all five. It returns the
stripped text, or `''` when the file is missing, not a regular file, unreadable or not UTF-8, and
masking goes on with the secrets alone.

The guards treat `.wuwei/canary` like the ledger. The leak check refuses any outward call holding the
canary, so a session that rewrites or removes the file turns that check off. The ledger door's path
list (`guards.LEDGER`, and `CACHE`, which extends it) gains `canary`, so every route that refuses a
ledger write now refuses a canary write in the same words: Write, Edit, MultiEdit, NotebookEdit, a
Codex apply_patch, a redirect target, a writer program's argument (rm included), and any write from
a shell working inside `.wuwei`. The raw-text door word for the ledger
(`\.wuwei[/.]*(/ledger|...)`) gains `/canary`, so a multi-line or unreadable command naming the canary
is refused as one naming the ledger is, and `hook.door` keeps such a call shut when the hook fails.

The acceptance scenarios, restated:

1. With a `.wuwei/canary` of invalid UTF-8, a seat launches and stops: `seat.started` and
   `seat.stopped` are recorded and its report is kept (and delivered to the planner).
2. A Write to `.wuwei/canary`, or a Bash redirect into it, spelled in each path class (`//`, `%xx`,
   `/./`, `/../`) and under each wrapper (`cd`, `env -C`, and `sudo -D` from the brief), is refused as
   a ledger write.
3. Every route in `tests/fixtures/routes.json` reads the same at main and at the head, except the
   new canary rows.

## How this fails

1. A seat reads the canary (`cat .wuwei/canary`) and pastes it into a file the owner later sends
   from outside a session. Reading stays allowed, as reading the ledger does; the leak check still
   refuses it on any outward call the hook sees. Rotating the canary is outside this item.
2. A spelling the ledger door misses misses the canary too, because the canary now shares the
   ledger's list. The probe found one class: `sed -i.bak` (a suffix glued to `-i`) passes for both the
   ledger and the canary at main and at the head. #1288 (config-door) changes the sed writer test to
   match `-i<suffix>`, which closes it for both once it merges.
3. An unreadable canary (mode 000, not UTF-8) now masks no canary where it used to stop the record.
   A report that holds the canary text would then be kept with it. That text cannot be valid in a
   non-UTF-8 file, and a mode-000 file needs a session write to the canary, which this item refuses.

## Clarifications

### Session 2026-11-05

- Q: Where does the reader live? A: `ws.canary(root)`, beside the other workspace readers, so the
  guards' leak check can call it later. Only hook.py calls it in this item.
- Q: Does the leak check in `guards.leak` change? A: No. The promise names the reads in hook.py, and
  the lead keeps this item's guards.py change to the ledger door's path list so a merge with #1288
  stays mechanical. A broken canary still makes the leak check raise, and `hook.handle` then shuts a
  network or door call. That is a follow-up candidate.
- Q: Is `rm .wuwei/canary` refused? A: Yes. `rm` reads `LEDGER`, and the canary is on it: removing the
  canary turns the leak check off, unlike removing a cache file.
- Q: What does the `%xx` class mean for a local path? A: sh and the harness never decode `%xx`, so
  `.wuwei/%63anary` names another file; the guard passes it, as it passes `.wuwei/%6cedger.jsonl`.
  The probe's `%xx` input holds the escape in a folder that `..` leaves (`x%2F/../.wuwei/canary`),
  which does reach the canary and is refused.
- Q: Is the refusal text changed to name the canary? A: No. `LEDGER_DENIED` stays as it is, so the
  refusal is the ledger's word for word; the lines next to it change in #1288.

## Requirements

- FR-001: `ws.canary(root)` returns the canary text, or `''` when the file is missing, not a regular
  file, unreadable or not UTF-8. It never raises `OSError` or `UnicodeError`.
- FR-002: Every canary read in hook.py goes through `ws.canary`.
- FR-003: `guards.LEDGER` and `guards.CACHE` name `canary`; the ledger door word names `/canary`.
- FR-004: No route of the corpus moves except the new canary rows.

## Assumptions

- A non-regular file at `.wuwei/canary` (a FIFO, a folder) reads as no canary, as at main: the
  `is_file()` check stays so a FIFO never blocks the hook. Overturned if setup ever writes another type.
- The refusal reuses `LEDGER_DENIED`, which names the ledger and the cache, not the canary.
  Overturned if a seat report shows the wording confused a seat.
- `wuwei init`'s permission rules (`setup.DENY`) are not extended to the canary: the hook guard holds
  the door, and setup.py is outside the item's files. A candidate for a follow-up.
- Runtime grows by 6 lines (the reader and its two blank separators) against the item's budget of 3:
  the five inline reads were one line each and stay one line each.

## Rollback

Revert the commit and re-vendor `.claude/`. No config key, ledger kind or file format changes.
