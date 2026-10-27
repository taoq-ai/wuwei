# Validation

Source head: `084c3bee9f8622a8452bd8eb35638e842ba560bc`.
Stack parent: `fa46883c1d0ca1c79cff9c4c0686e23364cec392` (item 1259).
Original main: `3feedf5ca60ad78ac602cb1a44c165e2aade0263`.
Later evidence commits change prose only.

## Red and green

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

## Route differential

Each source was copied with `git archive <sha>` into a separate empty directory under
`.wuwei/scratch/builder-1254/`. For each tree:

```sh
uv run --no-project --with pytest python -I specs/gates-at-push/route_diff.py \
  .wuwei/scratch/builder-1254/<source>-tree tests \
  .wuwei/scratch/builder-1254/cases-<source> \
  > .wuwei/scratch/builder-1254/routes-<source>.json
```

`<source>` is `parent`, `main`, or `head`. The existing route runner uses approved fake PASS
fixtures and fake green, running, red, and excepted hosts. It makes no live code-host calls.

`python3 -I specs/gates-at-push/route_diff.py compare <base>.json <head>.json` produced
[parent versus head](routes-parent-head.txt) and [original main versus head](routes-main-head.txt).
Each comparison has 288 routes, 1,152 host cases, and zero verdict or reason changes.
There are no moved routes to list.

Corpus SHA256: `de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1`.

## Sweep

- AUTH PASS: hook/setup tests retain launch and notification-frame verification; both route comparisons have zero moves.
- VAL PASS: hook tests cover latest versions, repeated bodies, planted file types, carriage returns, and cancellation. No command parser changed.
- TEST PASS: 668 hook/setup tests reach hook.handle, including the real report delivery consumer.
- ERR PASS: the exact reported no-delivery error grants no credit; existing guard decisions retain their outcome.
- STATE PASS: repeated stops, A/B/A, and Stop-to-call replays stay quiet after delivery. Concurrent writers are unmeasured; atomic rename is unchanged.
- CON PASS: seat_transcript and notified fixtures pass through retention and planner delivery, across sessions and agents.
- INF N.A.: no secrets, environment keys, permissions, workflows, or entry points changed.

Runtime measured with `python3 -c` summing splitlines for `cli/wuwei/*.py`: 3,759 lines,
five above the parent source and within the approved cap of 3,800.
Full suite: unmeasured locally for this item, deferred to CI while item 1259 owns the serialized slot.

Residual risk: timestamped filename ordering is retained. No charter or generated-agent change was needed.
Rollback: revert this change.

Draft PR: https://github.com/taoq-ai/wuwei/pull/1264 (stacked on item 1259). CI unread at handoff.
