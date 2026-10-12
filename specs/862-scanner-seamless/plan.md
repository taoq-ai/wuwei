# Implementation Plan: the scanner runs once per repository per day and never re-parks a resumed item

**Branch**: `862-scanner-seamless` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

Fix the shared spots the audit named: the adapter contract, one discovery cache in the day
directory, the brief lock, the propose order, the trace dedup, one close card, a diff filter
on the S4 rows and the error texts. No new module, no config.

## Technical Context

Python 3.11+ stdlib. Files: `adapters/scanner/ziran.py`, `cli/wuwei/discovery.py`,
`cli/wuwei/brief.py`, `cli/wuwei/plan.py`, `cli/wuwei/scanner.py`, `cli/wuwei/closing.py`,
`cli/wuwei/dispatch.py`. Tests: `tests/test_ziran.py`, `tests/test_plan.py`,
`tests/test_brief.py`, `tests/test_traces_seats_only.py`, `tests/test_close_parked.py`,
`tests/test_dispatch.py`.

## Constitution Check

- II: a cached reason stays unmeasured; a missing merge base is unmeasured; nothing turns
  clean that was not measured.
- III: the cache lives in `discover`, the one function every caller routes through.
- IV: each change has its failing test first.
- V: plain JSON file in the day directory, existing dedup and park code, existing
  `vcs.diff_stat`; no new module.
- VII: diff-only keeps every finding in a changed file blocking; the #870 and #878 checks
  are untouched.

## Changes

1. `ziran._report` (S1, S2): `line` is `None` or an int >= 1; `files_analyzed` an int >= 0,
   and 0 only with no findings.
2. `discovery.discover` (S3, S4, P1): per repo, read HEAD with `vcs.head`; reuse
   `scanner-audit.json[name]` when its `head` matches; else run `scanner.audit`, timed with
   `time.monotonic`, and store `{'head', 'rows'}` (measured) or `{'head', 'reason'}` (when
   it took 10 s or more). No `break`: measured rows are kept, unmeasured repos are joined into
   the source line after `dedupe`, followed by `run {scanner.OFF} to switch the scanner off`.
   A null line renders as the file (id line 0).
3. `brief.write` (S5): `lead = candidates(root) if role == 'lead' else ''` before the
   `brief.lock` block; the block appends `lead`.
4. `plan.propose` (P4): the `gate_approved` refusal moves to the top.
5. `scanner._trace_response` (S6): before the local-chain check, return False when
   today's events hold a `scanner.finding` with this `session_id` and `chain`.
6. `closing.scanner_hold` (S7): collect today's critical findings, one card naming the
   distinct chains (first five, then a count), token over the sorted JSON of the findings.
7. `scanner.rows(tree, item, flags, config, root, changed)` (S8): skip findings whose path
   relative to the worktree is not in `changed`; a null line renders as `:1` (verdict lint
   needs `file:line`). `dispatch.receive` reads the brief's
   `Merge-base:` line and passes the `vcs.diff_stat` paths from it to the measured HEAD.
8. Texts (P1): `scanner.OFF` is `bin/wuwei config set adapters.scanner '"none"'`;
   `scanner._unmeasured(tree, item, reason)` names the worktree, then a rerun of
   `dispatch receive` or `plan park <item>` (switching the scanner off does not clear an
   agent_surface gate); `trace_sweep` names the reason, the retry and `OFF`. No
   "run bin/wuwei doctor" in `scanner.py`.
