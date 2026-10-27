# Validation

Source head after the combined review fix: `2864b109cfe976478fff039a7cd992d59c00ec51`.
Corrected stack parent: `c450f433661ad0c65e0cdd55d31f1caa2c540ca6` (item 1259).
Initial source: `084c3bee9f8622a8452bd8eb35638e842ba560bc`; initial parent: `fa46883c`.
Original main: `3feedf5ca60ad78ac602cb1a44c165e2aade0263`.
Later evidence commits change prose only.

## Initial red and green

`uv run --no-project --with pytest python -m pytest -q tests/test_hook.py -k
'three_stops or final_report_matching or identical_latest or notified_latest or real_no_report'`
failed before implementation: 4 failed, 2 passed, 618 deselected. The failures exposed all pending
versions being emitted, the latest A disappearing in A/B/A, and an older version blocking Stop
after the latest version had been notified. After implementation: 6 passed, 618 deselected.

`uv run --no-project --with pytest python -m pytest -q tests/test_hook.py tests/test_setup.py`:
668 passed in 84.44 seconds. This includes the unchanged outside-auto refusal guidance and
notification frame, cancellation, repeated-stop, session-isolation, runtime, and vendor tests.

The focused report/notification/handback and runtime/vendor selection also passed:
206 passed, 462 deselected in 52.03 seconds.
`bin/wuwei agents check` and `git diff --check` passed.

System python3 has no pytest module; pytest is also absent from PATH. Plain `uv run` cannot read
the repository's versionless project table. `uv run --no-project --with pytest` used cached pytest.
No runtime dependency was added.

## Combined review fix

The native review found that claiming B before retiring A let overlapping delivery, or a temporary
archive error, make A current again. Four deterministic consumer tests failed before this fix:

`uv run --no-project --with pytest python -m pytest -q tests/test_hook.py -k
'overlapping_report_delivery or temporary_archive_failure or moved_while_listing or synthetic_role_change'`

Result: 4 failed, 624 deselected. The same command then passed all four cases. They cover a nested
Stop immediately after B's claim, PermissionError archiving A, moving B while the two folders are
listed, and the review's synthetic role change. Native role reuse remains unproven, but sorting
by timestamp removes role spelling from version order.

Delivery now reads pending names before archive names and sorts both by timestamp. An archived
latest version suppresses older pending files even if retiring them failed. Listing pending first
keeps the latest version visible when another call moves it between the two listings.
No parallel store was added; original archive bytes and latest pointers remain.

Two additional retention interleavings then reproduced at e341ab45:
`uv run --no-project --with pytest python -m pytest -q tests/test_hook.py -k
'claim_during_retention or claim_before_retention'` failed both cases, 628 deselected. Root-first
listing missed claimed B and lost returning A; moving B immediately before its read raised
FileNotFoundError and also lost A. Retention now scans pending first, then archive, and reads the
archived copy if a claim moved the selected immutable version. All six review/race tests passed,
624 deselected. The local delivery map records the first filename instead of adding the same
identity in two branches, keeping the implementation within the reallocated line budget.

Before merging the corrected parent, hook/setup passed 672 tests in 81.41 seconds.
After merging c450f433, `uv run --no-project --with pytest python -m pytest -q tests/test_hook.py
tests/test_setup.py tests/test_codex.py` passed 720 tests in 81.11 seconds.
At final source 2864b109, the same combined command passed 722 tests in 85.82 seconds.
`bin/wuwei agents check` and `git diff --check` also passed.

## Route differential

Each source was copied with `git archive <sha>` into a separate empty directory under
`.wuwei/scratch/builder-1254/`. For each tree:

```sh
uv run --no-project --with pytest python -I specs/gates-at-push/route_diff.py \
  .wuwei/scratch/builder-1254/<source>-tree tests \
  .wuwei/scratch/builder-1254/cases-<source> \
  > .wuwei/scratch/builder-1254/routes-<source>.json
```

`<source>` is `parent`, `main`, or `head`. The combined-fix run used `review-parent-tree` at
c450f433, the original `main-tree` at 3feedf5c, and `final-head-tree` at 2864b109; its case
folders and JSON outputs use `review-` for parent/main and `final-` for the final head. The existing route runner uses approved fake PASS
fixtures and fake green, running, red, and excepted hosts. It makes no live code-host calls.

`python3 -I specs/gates-at-push/route_diff.py compare <base>.json <head>.json` produced
[parent versus head](routes-parent-head.txt) and [original main versus head](routes-main-head.txt).
Each comparison has 288 routes, 1,152 host cases, and zero verdict or reason changes.
There are no moved routes to list.

Corpus SHA256: `de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1`.

## Sweep

- AUTH PASS: hook/setup tests retain launch and notification-frame verification; both route comparisons have zero moves.
- VAL PASS: hook tests cover latest versions, repeated bodies, planted file types, carriage returns, and cancellation. No command parser changed.
- TEST PASS: 722 combined hook/setup/Codex tests reach the actual consumers, including the new delivery interleavings.
- ERR PASS: the exact reported no-delivery error grants no credit; existing guard decisions retain their outcome.
- STATE PASS: repeated stops, A/B/A, Stop-to-call replays, overlapping claims, failed archival, and listing interleavings. Retention scan/claim and selected-file read/rename interleavings also pass deterministic consumer tests.
- CON PASS: seat_transcript and notified fixtures pass through retention and planner delivery, across sessions and agents.
- INF N.A.: no secrets, environment keys, permissions, workflows, or entry points changed.

Runtime measured with `python3 -c` summing splitlines for `cli/wuwei/*.py`: 3,766 lines,
eleven above the corrected 3,755-line parent source and within the approved cap of 3,800.
Full suite: unmeasured locally for this item; the planner schedules one final integrated run after all combined fixes.

Residual risk: timestamped filename ordering is retained. Native role reuse remains unproven.
The owner reaffirmed the approved 3,800-line cap after conflicting instructions were raised.
The planner reallocated this item to +11 runtime lines to close the retention races. No charter or generated-agent change was needed.
Rollback: revert this change.

Draft PR: https://github.com/taoq-ai/wuwei/pull/1264 (stacked on item 1259). CI unread at handoff.
