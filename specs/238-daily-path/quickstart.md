# Fourth dry run: the daily path, scripted

The issue's first acceptance is the fourth operator dry run. It runs on the existing
scripted-day driver (`tests/fakes/day.py`), not a new one, as the solo test in
`tests/test_e2e_day.py` (T013).

## Run

From the repository root:

```sh
python -m pytest -q tests/test_e2e_day.py
```

## What the run does

A solo owner workspace (`Day(..., solo=True)`: `shepherd.min_reviewers = 0`, chat `none`)
with only `docs/site/daily.md` as the operator's guide:

1. Plan: `rank`, `plan propose`, `plan approve --items A --goals-confirmed`,
   `plan session`.
2. Build: `brief builder`, then `build next` / `build check` until `done` (item in `gate`).
3. Gates: `dispatch next` lists the roles; for each, `brief <gate role> ... --gate`, then
   `dispatch next` again and execute the returned `seats` `launch` action; after the seat
   stops, run its `receive` command. Quality returns FIX.
4. Fix: `dispatch next` returns `fix` with `command`; the item is already in `fix`. Run
   `build next`, execute the builder `continue` (resume), then `build next` / `build check`
   until `done` (item in `delta`).
5. Delta: `dispatch next` returns the quality `continue` in `seats`; execute it with
   `resume`, then run its `receive` (`--round delta`). `dispatch next` returns `raise`.
6. Raise and merge: `pr raise ... --item A` (item `raised`), `pr state` (waiting); the fake
   host reports the PR merged; `pr state` (item `merged`).
7. Check: `report` lists `- A (acme/widget#7)` under Merged; `status --line` shows
   `merged 1/1`.
8. Close: `retro`, `close --check retro`, `close`, the Stop hook.

The test asserts: no `state transition` and no `runtime` command among the recorded
calls; every recorded command is named on `docs/site/daily.md`; the `phase_changes`
sequence is `implement, gate, fix, delta, raised, merged`.

## Findings

Recorded by `test_solo_daily_path` on the scripted driver.

- Commands the solo operator ran (`day.calls`, by first two words): `rank`, `plan propose`,
  `plan approve`, `plan session`, `brief builder`, `build next`, `build check`,
  `brief arch`, `brief quality`, `brief security`, `dispatch next`, `dispatch receive`,
  `pr raise`, `pr state`, `report`, `status --line`, `retro`, `close --check`, `close`.
  Every one is named on `docs/site/daily.md`.
- No `state transition`, no `runtime dispatch`, no `runtime continue`, no rebuilt job JSON
  and no role translation. The phase sequence from `phase_changes` is `implement, gate,
  fix, delta, raised, merged`.
- Owner interventions: none in the solo run beyond the morning gate answers. The owner's
  host terminal actions (`decision outcome`, `drafts approve`, `mcp decide`) are on the
  daily page and are exercised by `test_scripted_day`.
- After `pr state` observed the merge, `report` listed `- A (acme/widget#7)` under Merged
  and `status --line` showed `merged 1/1`.
- Commands the page had to gain against the old index: `build check`, `dispatch receive`
  (as the `receive` of each seat action), `status --line` and `retro`.
- Remaining seam found by the run: the scripted runtime rewrote a resumed seat's
  transcript, so the builder's resumed stop looked like a duplicate of its first
  completion. A real resumed Agent appends to its transcript; the driver now appends too.
  No production change was needed.
- Out of scope and still recovery: a lost sentinel (no `seats` entry, fresh brief), a
  rejected verdict returned to its seat, and Codex sentinels (`runtime continue` with the
  job from `runtime dispatch`).
