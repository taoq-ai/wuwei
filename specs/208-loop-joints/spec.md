# Feature Specification: The loop's joints between build, gates, delta and push

**Feature Branch**: `208-loop-joints`
**Created**: 2026-09-30
**Status**: Draft
**Input**: Issue #208, design sections 5.2 and 5.3. Depends on #161 and #22. Evidence: the
v0.5.0 operator dry run of 2026-09-30 (steps log rows 12, 17, 18, 24, 25, 26, 27).

## Root causes (reproduced from the dry run steps log, read-only)

Each joint below failed in the dry run with the v0.5.0 install; the cause is in `main`.

1. Build done leaves the item where dispatch refuses it (row 17). Steps `next5` then
   `dnext0`: `build next` returned `{"action": "done"}` and `dispatch next` exited 1 with
   `item phase planned is not dispatchable`; the operator needed `state transition` to
   `implement` then `gate`. Later `next-fix3` returned done in `fix` and the operator ran
   `state transition delta` by hand. Cause: `next_action` in
   `cli/wuwei/commands/build.py` (lines 100-150) starts a build without moving a `planned`
   item, and `complete_checks` (lines 361-364) only moves `fix -> delta` when
   `fix_rounds == 1`, which only the PR fix path `open_fix` sets. Nothing moves
   `implement -> gate`. `dispatch.next_step` (`cli/wuwei/dispatch.py` line 64) accepts
   only `gate`, `fix` and `delta`.
2. `wuwei brief` rejects the role names `dispatch next` returns (row 18). Step
   `brief-arch-try`: `brief --gate ... arch DIVIDE-1 s-arch` exited 2 with
   `unknown charter: arch`. Cause: `brief.write` (`cli/wuwei/brief.py` lines 160-171) looks
   the charter up by the literal role, while `dispatch.ROLES` (`cli/wuwei/dispatch.py`
   line 10) is `arch`, `quality`, `security`.
3. A delta cannot continue the same sentinel (row 24). Step `rt-continue` then the
   PreToolUse Agent call with `resume: agent-s-quality` and the original brief
   `s-quality.md` was denied `brief already used for a seat launch`; the operator had to
   write a fresh brief `s-quality-d`. Cause: in `cli/wuwei/guards/agent_launch.py`
   `reserve` (lines 112-126) `continuing` is only true for a builder with a matching build
   record; no non-builder seat records the agent id it stopped with (`state.stop_seat`,
   `cli/wuwei/state.py` lines 368-373). Two further defects sit on the same path: a
   continuing gate seat reaches `brief.status(vcs, ...)` at line 150 with `vcs` unbound
   (it is only assigned at line 136 when not continuing), and `dispatch.receive`
   (`cli/wuwei/dispatch.py` line 146) requires the verdict Head to appear in the original
   brief text, so a delta verdict at the new HEAD from the continued seat would be refused.
4. A passing `build check` does not satisfy the push guard (rows 26, 27). Steps
   `check-fix` (exit 0) then the shepherd's `git push`: denied `fast check has not passed
   for current HEAD: python3 -m pytest -q` until the operator ran `wuwei fast-checks`.
   Cause: `check` in `cli/wuwei/commands/build.py` (lines 368-374) runs the checks through
   the checks port directly; only `fast_checks.record` (`cli/wuwei/fast_checks.py`) writes
   the `fast_checks` state the push guard reads (`push_check`,
   `cli/wuwei/guards/commit_push.py` lines 113-126).
5. `wuwei brief` blocks on an interactive stdin (rows 12, 25). Step `brief-qd` exited 143
   (killed after hanging) because the body is always `sys.stdin.read()`
   (`cli/wuwei/commands/brief.py` line 30) and no body option exists.

## User Scenarios & Testing

### US1: Build done hands the item to the gates (P1)

As the planner, when the build loop says `done` I call `dispatch next` and get the gates,
with no manual state transition.

Acceptance scenarios:
1. Given an approved item in `planned` and a finished build loop, when I call
   `dispatch next`, then it returns `{"action": "gates", "roles": ["arch", "quality",
   "security"]}` without an intermediate `state transition`.
2. Given the item in `fix` after gate verdicts and a finished fix build, when I call
   `dispatch next`, then it returns the delta gates (the roles that gave FIX) without a
   manual `delta` transition.
3. Given repeated `build next` calls without a state change, then they return the same
   action and write no events (idempotence is unchanged).

### US2: Brief accepts dispatch role names (P1)

1. Given `dispatch next` returns `arch`, `quality` or `security`, when I run
   `wuwei brief --gate --worktree <tree> quality <item> <name> --body <text>`, then the
   brief is written for `sentinel-quality`, logged with role `sentinel-quality`, and a
   `wuwei:sentinel-quality` Agent launch with it is accepted.
2. Given the full names `sentinel-arch`, `sentinel-quality`, `sentinel-security`, then
   they keep working unchanged.

### US3: A delta round continues the same sentinel (P1)

1. Given `dispatch next` returning `[quality]` for delta and the quality seat stopped
   with agent id `agent-s-quality`, when the planner runs the documented continuation
   (Agent with the original brief prompt from `wuwei runtime continue` and `resume` set to
   that agent id), then the launch guard accepts it and re-registers the same seat.
2. Given that continued seat writes its verdict at the new HEAD, when the planner runs
   `dispatch receive <item> quality <seat> --round delta`, then the verdict is recorded.
3. Given a used brief launched again without `resume`, or with a `resume` that is not the
   agent id the seat stopped with, then the launch is still refused as a reused brief.

### US4: A passing build check satisfies the push guard (P1)

1. Given `build check` passed at HEAD, when that HEAD is pushed, then the push guard does
   not refuse it for fast checks.
2. Given `build check` failed or could not run, then the push guard still refuses that
   HEAD for fast checks.

### US5: Brief body without blocking (P2)

1. Given `--body TEXT`, then the brief body is TEXT.
2. Given `--file PATH`, then the body is read from PATH; `--file -` reads stdin.
3. Given neither option, then `wuwei brief` exits 2 at once with a reason naming
   `--body` and `--file`, and never reads stdin.

## Requirements

- FR-001: When a build starts for an item in `planned`, the item moves to `implement`.
- FR-002: When `build check` completes green, an item in `implement` moves to `gate` and
  an item in `fix` moves to `delta`, for every build, not only PR fix rounds. Other phases
  are left unchanged.
- FR-003: `wuwei brief` maps `arch`, `quality` and `security` to `sentinel-arch`,
  `sentinel-quality` and `sentinel-security` before any check, so the charter, gate flag
  and logged role are the full name.
- FR-004: A non-builder seat's SubagentStop records its `agent_id` on the seat. An Agent
  launch with `resume` equal to that recorded id, for a stopped seat whose logged brief it
  references, is a continuation and is not refused as a reused brief. All other launch
  checks (role, brief digest, gate readiness, clean tree, capacity, memory) still apply.
- FR-005: A second launch of a used brief without a matching `resume` is refused exactly as
  today. The builder continuation rule is unchanged.
- FR-006: The seat record's `head` is the worktree HEAD measured at launch or
  continuation. A fresh launch still refuses a HEAD that differs from the brief.
  `dispatch receive` accepts the verdict Head when it matches the brief HEAD or the
  seat's recorded HEAD; the current worktree HEAD and sibling checks are unchanged.
- FR-007: `build check` records its results through the existing fast-check producer so
  the push guard's `fast_checks` record for that repository and HEAD is written by the same
  function `wuwei fast-checks` uses. Exit codes, feedback, signature and parking are
  unchanged.
- FR-008: `wuwei brief` takes the body from `--body` or `--file` (mutually exclusive;
  `--file -` is stdin) and exits 2 with a reason when neither is given.
- FR-009: `skills/wuwei-plan/SKILL.md`, `docs/site/reference.md` and
  `docs/site/concepts.md` document the automatic phases, role aliases, sentinel
  continuation, the build-check push record and the body options.

## Success Criteria

- SC-001: The scripted day (`tests/test_e2e_day.py`) runs build, gates, fix and delta with
  no `implement`, `gate` or `delta` transition by the planner and still records the phase
  sequence `implement, gate, fix, delta, raised, merged`.
- SC-002: Each of the three issue acceptance scenarios has a test that fails on `main` and
  passes after the change.
- SC-003: The full suite passes; no guard accepts anything it refused before except the
  continuation named in FR-004.

## Assumptions

- A build started in `spec` (FULL track) is left in `spec` at done; the spec-done gate is
  not implemented in `dispatch` and moving the item is the planner's call. Only `planned`
  moves at launch and only `implement` and `fix` move at done.
- `gate -> fix` stays a planner transition after `dispatch next` returns `fix`; the issue
  names only the build-done joint.
- The continued sentinel overwrites its own `decisions/gate-<name>.md` with the delta
  verdict. The initial outcome stays in `gate_verdicts` and the `gate.received` event;
  the PR guard and merge policy already read the delta record's file for FIX roles.
- SubagentStop `agent_id` is trusted to the same degree the builder path already trusts
  it (spec 9.1 cooperative hook model); seats stay a PreToolUse/SubagentStop producer key.
- Piped callers must now pass `--file -`. The only callers are tests, `tests/fakes/day.py`
  and the headless e2e prompt in `scripts/headless_e2e.py` (which also runs
  `state transition A gate` after done); all are updated.
- A `build check` rewrites the repository's `fast_checks` record like `wuwei fast-checks`
  does (one record per repository, keyed by command).
- No new configuration keys.

## Deferred

- A spec-done gate and automatic `spec -> implement` handling for FULL items.
- Aliases for `wuwei runtime dispatch` roles; the issue names only `wuwei brief`.
