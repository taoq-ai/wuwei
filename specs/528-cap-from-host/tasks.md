# Tasks: CAP and host.seats come from the measured host and a token budget

Test first: each test task is written, run and seen to fail for the expected reason before
its implementation task. Fixtures are neutral (items `A`..`D`, goals `G-1`, `G-2`, the #474
fixture day in `tests/fakes/day.py`). Run `python -m pytest -q` from the repository root.

## Phase 0: fixture (test infrastructure, no behaviour)

- [X] T000 In `tests/fakes/day.py`: keep the host fake reachable as `day.memory` (today it is
  built inline in the ports dict) and pin `os.cpu_count` to 4 with the fixture's monkeypatch,
  so derived capacity is deterministic on any machine.

## Phase 1: config and the shared helper (FR-001, FR-002, FR-003)

- [X] T001 Test in `tests/test_workspace.py`: a config without `cap`, `[host] seats` or
  `[budget]` loads with `cap == 0`, `host.seats == 0`, `budget.tokens_per_day == 0`; negative
  values are config errors; the workspace template parses with `cap = 0` and `seats = 0`.
- [X] T002 Implement in `cli/wuwei/workspace.py` (`SCHEMA`: `cap`, `host.seats`, new
  `budget.tokens_per_day`) and `templates/workspace/config.toml` (comments and values).
- [X] T003 Test in `tests/test_metrics.py`: `metrics.seat_tokens` returns input plus output
  per `seat.usage` row, skips rows with `unmeasured` tokens and ignores other kinds.
- [X] T004 Implement `seat_tokens` in `cli/wuwei/metrics.py` next to `seat_cost`.
- [X] T005 Test in `tests/test_calibrate.py` (table over `calibrate.host` with the host fake
  and `os.cpu_count` pinned): 8 GiB free, floor 1024, no seat history, 4 cores gives cap 4,
  seats 4, bound `host`, text with `8 GB free`, `1 GB per seat`, `4 cores`; 3 GiB free gives
  2; `running=2` with 2 GiB free gives 3; owner `cap = 1` gives 1 `owner` and the text names
  what the host fits; owner `host.seats = 2` gives cap and seats 2; free memory unmeasured
  gives the fallback (`cap` 1, `seats` 4, bound `unmeasured`, the reason in the text);
  `os.cpu_count` None gives `unmeasured`.
- [X] T006 Test in `tests/test_calibrate.py`: with `tokens_per_day = 200000` and a prior day
  holding two `seat.usage` rows of 100000 tokens, cap 2 bound `budget`; with 150000 of those
  tokens used today, cap 1 `budget` (never 0); with a budget and no `seat.usage` rows, the
  budget does not bind and the text says per-seat tokens are unmeasured.
- [X] T007 Implement in `cli/wuwei/calibrate.py` (`host(root, config, running=0,
  free=None)`): fit, seats, owner, budget, unmeasured fallback and text, with the
  `ponytail:` comment on the budget.

## Phase 2: calibrate measures and never proposes cap (FR-009)

- [X] T008 Test in `tests/test_calibrate.py`: `calibrate.propose(raw, results)` on a config
  without `cap` adds no `cap` line; `wuwei calibrate` writes a report whose host section
  shows `derived: cap ...`. Update the existing cases that expected a `cap` proposal.
- [X] T009 Implement in `cli/wuwei/calibrate.py` (`proposal`, `propose`, `report`),
  `cli/wuwei/commands/calibrate.py:55` and `cli/wuwei/commands/config.py` (`proposal`,
  `promote`): remove the `host` parameter and the cap addition.

## Phase 3: plan and gate (FR-004, FR-005, FR-010)

- [X] T010 Test in `tests/test_parallel_dispatch.py` (US1 scenario 1, first half): the
  fixture day with no `cap` in config, `os.cpu_count` pinned to 4, host fake at 8 GiB:
  `plan propose` with a lead JSON whose `cap` is 1 writes `CAP: cap 4 (host): 8 GB free` in
  `plan.md` and `cap == 4` in `proposal.json`; `plan gate`'s `Approve` description carries
  the same text and `Change something` names CAP; after `plan approve` the day state has
  `cap == 4` and `cap_bound == 'host'`.
- [X] T011 Test in `tests/test_parallel_dispatch.py` (US3 scenarios 1 and 3): `approved(day,
  1)` gives `CAP: cap 1 (owner)` naming what the host fits; the existing
  `test_owner_cap_one_stays_sequential` still passes. Test that `plan template` prints the
  derived cap.
- [X] T012 Implement in `cli/wuwei/plan.py` (`propose`, `gate_widget`, `approve`),
  `cli/wuwei/commands/plan.py` (`template`) and `cli/wuwei/state.py` (`DAY_DEFAULTS`
  `cap_bound`, `STATE_PRODUCERS`).

## Phase 4: launch set re-derives (FR-006)

- [X] T013 Test in `tests/test_parallel_dispatch.py` (US1 scenario 1, second half): after
  approval, `dispatch next --all` returns four `start` entries and no `wait`, with `bound`
  `host` in the output.
- [X] T014 Test in `tests/test_parallel_dispatch.py` (US1 scenario 3): host fake at 3 GiB at
  approval and the first sweep gives two `start` and two `wait` naming `CAP 2`; set the fake
  to 8 GiB, the next sweep gives four, the day state `cap` is 4 and exactly one
  `cap.derived` event was written for the change; a third sweep with no change writes no
  event.
- [X] T015 Test in `tests/test_parallel_dispatch.py` (US2 scenario 1): `[budget]
  tokens_per_day = 200000` and a prior day directory with two `seat.usage` rows of 100000
  tokens: `plan.md` says `(budget)`, two items start and two wait.
- [X] T016 Implement in `cli/wuwei/dispatch.py` (`launch_set`): derived cap and ceiling,
  snapshot write on change, `bound` and `capacity` in the result.
- [X] T017 Test in `tests/test_parallel_dispatch.py` (pattern of `test_reserved` in
  `tests/test_outbound_learn.py`): `main(['event', 'cap.derived', '{}'])` exits 1 naming
  `wuwei dispatch next --all`; `state.set_state('cap_bound', 'host', root)` after approval
  raises `reserved`; `'cap.derived' in signal.SILENT`.
- [X] T018 Implement in `cli/wuwei/commands/event.py` (reserved map) and
  `cli/wuwei/signal.py` (`SILENT`).

## Phase 5: launch guard and opinion (FR-007)

- [X] T019 Test in `tests/test_parallel_dispatch.py`: on the T013 day, A, B and C launch
  through the PreToolUse hook; then the host fake drops to 1 GiB free (the floor), so the live
  fit is the three running seats, and the `guard()` call for D's builder brief gets
  `code == 1` naming `CAP 3` (the derived value at launch, not the day's 4). The existing
  `test_owner_cap_one_stays_sequential`, `test_first_dispatch_turn_launches_cap_builders_and_the_fourth_waits`
  and `test_gate_seats_wait_when_host_seats_cannot_hold_them_together` keep passing.
- [X] T020 Implement in `cli/wuwei/guards/agent_launch.py` (`reserve`) and
  `cli/wuwei/dispatch.py` (`opinion`, the ceiling check at :506-507).

## Phase 6: status line (FR-008)

- [X] T021 Test in `tests/test_parallel_dispatch.py`: after approval the line contains
  `seats 0/4 (host)`; with three builders running `seats 3/3 (owner; G-1 2, G-2 1)` for the
  `approved(day, 3)` day (update the existing assertion); in `tests/test_signal_status.py` a
  day state without `cap_bound` shows `seats n/cap` with only the goal split.
- [X] T022 Implement in `cli/wuwei/commands/status.py` (`snapshot`, the line builder).

## Phase 7: docs and the full suite (FR-012)

- [X] T023 Test: run `python -m pytest -q`; the docs tests that read
  `docs/site/configuration.md` (the `cap` row must keep `calibrate` and `morning gate`) and
  the config-documentation coverage test must pass with the new `budget.tokens_per_day` row.
- [X] T024 Update `skills/wuwei-plan/SKILL.md`, `charters/lead.md`, `charters/planner.md`,
  `docs/site/configuration.md`, `docs/site/concepts.md`, `docs/site/reference.md` and design
  5.3 in `docs/specs/2026-09-24-wuwei-design.md` (dated `Amended (owner, 2026-10-05, #528)`).
- [X] T025 Fix fixture fallout: add `cap = 1` only where a test depends on one builder; update
  default assertions in `tests/test_workspace.py`, `tests/test_calibrate.py`,
  `tests/test_signal_status.py`, `tests/test_agent_launch.py`. Run the full suite green.
- [X] T026 Check every file written for em-dashes and emojis and remove any; no absolute
  local paths.

## Phase 8: review fixes (528-findings.md)

- [X] T027 F1 test and fix: `calibrate.host` with a damaged past-day events.jsonl falls back
  to `SEAT_MIB`, budget per-seat tokens unmeasured, and a warning in `text`.
- [X] T028 F2 test and fix: the derived seat ceiling is at least `len(dispatch.ROLES)`; in
  `dispatch.launch_set` a gate waiting for seats makes every planned item wait.
