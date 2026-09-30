# Feature Specification: The scripted day runs every call through the hooks with the real launcher

**Feature Branch**: `212-e2e-through-hooks`
**Created**: 2026-09-30
**Status**: Draft
**Input**: Issue #212, design section 10 (end to end). Depends on #205, #206, #207, #208
(and #210 for the dead-watch page). Evidence: the v0.5.0 operator dry run of 2026-09-30.

## Root cause (reproduced read-only)

Two bugs shipped from v0.1.0 to v0.5.0 with a green scripted day:

1. **Launcher refused as opaque.** In the dry run steps log, step `next2` sends the
   planner's `<executable> build check DIVIDE-1` through PreToolUse and gets exit 2
   ("commit/push guard could not run: command substitution is unsupported ...", "opaque
   script deployment command", "opaque script command"). At `31a36cc^`,
   `cli/wuwei/shell.py:128` (`script_path`) returned the launcher as a local script and the
   guards read its text with `mentions()` (`shell.py:85`), which treats the launcher's own
   `$(...)` as a hidden command. Fixed by #205 on main.
2. **Close trap.** Dry run rows at `hook Stop` show a Stop with `stop_hook_active: true`
   still exiting 2 with the reasons of the first block. At `7b35aad^`,
   `cli/wuwei/guards/stop.py:36` ran `closing.check` whatever `stop_hook_active` said.
   Fixed by #206 on main.

Why CI stayed green: `tests/fakes/day.py:188` (`Day.run`) calls `main()` in process and
never sends the call through PreToolUse, and `tests/fakes/day.py:199` (`Day.hook`) always
sends `stop_hook_active: False`. Reproduced in scratch copies of `31a36cc^` and `7b35aad^`:
`tests/test_e2e_day.py` passes (3 passed) in both, while one launcher Bash payload through
`Day.hook('PreToolUse', ...)` is denied in both, and one Stop retry with
`stop_hook_active: true` added to the day fails at `7b35aad^` and passes on main.

## User Scenarios and Testing

### User Story 1 - A guard that refuses the plugin fails CI (Priority: P1)

As the maintainer, I need every CLI call the planner makes in the scripted day to pass
through PreToolUse as a Bash payload using the plugin's `bin/wuwei`, so a guard that
refuses the plugin's own commands turns CI red at the step it refuses.

**Independent test**: add a guard that refuses any Bash command naming the launcher; the
scripted day fails at its first CLI call and the failure names that command.

**Acceptance scenarios**:

1. **Given** the scripted day on main, **when** each planner CLI call is first sent
   through PreToolUse as `<plugin>/bin/wuwei <args>` with the workspace as cwd, **then**
   every hook exits 0 and the day passes.
2. **Given** the launcher refusal reintroduced (any PreToolUse Bash guard refusing the
   launcher), **when** the scripted day runs, **then** it fails and the assertion message
   names the refused CLI command and the refusal reason.
3. **Given** an owner-only action (`decision outcome`), **when** the day performs it,
   **then** PreToolUse refuses it through the launcher (exit 2) and the owner runs it on
   the host (in process) with host confirmation.

### User Story 2 - The day covers the wave D joints (Priority: P1)

As the maintainer, I need the scripted day to cover an owner decision answered and cleared,
a solo-owner raise, a delta round on the same sentinel, a dead-watch page, and close.

**Acceptance scenarios**:

1. **Given** an owner-routed decision record `D-1` routed by the planner, **when** close
   runs, **then** it lists `D-1: pending owner decision`; **after** the owner answers with
   `decision outcome D-1 A`, close no longer lists `D-1` and the report lists `- D-1: A`.
2. **Given** close requested with unresolved work, **when** Stop runs with
   `stop_hook_active: false`, **then** it blocks (exit 2); **when** Stop runs again with
   `stop_hook_active: true`, **then** it exits 0.
3. **Given** the close trap reintroduced (Stop ignoring `stop_hook_active`), **when** the
   scripted day runs, **then** it fails at the Stop retry and the message names that step.
4. **Given** quality returned FIX and the fix build is done, **when** the planner continues
   the stopped quality seat (`runtime continue` with the seat's job, Agent `resume` set to
   its recorded agent id) and receives `--round delta` for the same seat name, **then** the
   delta verdict is recorded, no new `quality-delta` seat exists, and `dispatch next`
   returns `raise`.
5. **Given** today's clock line older than `watch.dead_seconds`, **when** the planner runs
   `nudges`, **then** it lists a `watch: health` page; **after** a fresh clock line,
   `nudges` lists none.
6. **Given** a solo-owner workspace (`shepherd.min_reviewers = 0`, no lead, `adapters.chat
   = "none"`, the only authorship row is the owner's), **when** the planner raises the PR
   through the hook, **then** it exits 0, creates one PR, records an empty reviewer list,
   requests no reviewer and posts nothing to chat.

### Edge Cases

- A planner call whose command exits non-zero on purpose (for example `dispatch next A`
  before approval, exit 1) still expects PreToolUse exit 0: the guard allows it, the
  command refuses it.
- `hook` calls themselves are not wrapped in a second PreToolUse (no recursion).
- Seat launches keep going through Agent PreToolUse and SubagentStop as today.
- The fake git keeps refusing `git var` like a CI runner; no network.

## Requirements

- FR-001: Every CLI call the scripted day makes as the planner is first sent through
  `wuwei hook PreToolUse` as a Bash payload whose command is the plugin's `bin/wuwei`
  followed by the call's arguments, with the workspace root as cwd and the planner session;
  the hook must exit 0 before the call runs in process.
- FR-002: An owner-only action in the day is sent through the same payload and must be
  refused (exit 2); it then runs in process as the owner on the host.
- FR-003: Every assertion failure in the day helper names the step: the CLI arguments for
  a call, and the hook event with its fields (including the Bash command or
  `stop_hook_active`) for a hook.
- FR-004: The scripted day adds: a dead-watch page appearing and clearing, an owner
  decision routed, listed by close, answered by the owner, cleared from close and shown in
  the report, a Stop retry with `stop_hook_active: true` exiting 0, and the delta round as
  a continuation of the stopped quality seat.
- FR-005: A second day test raises a PR in a solo-owner workspace with no reviewers.
- FR-006: A test reintroduces each bug (a guard refusing the launcher; a Stop guard
  ignoring `stop_hook_active`) and asserts the scripted day fails naming the step.
- FR-007: No production code changes. The release smoke is unchanged.

## Success Criteria

- SC-001: `tests/test_e2e_day.py` passes on main with every planner call through
  PreToolUse, and the whole file runs in under 30 s.
- SC-002: Each reintroduced bug turns the scripted day red with a message naming the step.
- SC-003: The full suite passes.

## Assumptions

- "The real launcher path" is the plugin's own `bin/wuwei` in the repository (resolved from
  `tests/fakes/day.py`), which `shell._launcher` recognises; the recorded-executable path is
  already covered by `tests/test_launcher_relevance.py` and is not repeated in the day.
- The owner-only call in the day is `decision outcome`; `plan approve --goals-confirmed` is
  a planner call after the owner confirms in chat and already passes the hook. The owner's
  host confirmation is simulated by patching `wuwei.integrity._host_confirm`, as
  `tests/test_stop.py` does.
- The watch clock line is written with `state.append_event('watch: clock', ...)` as
  `tests/test_quiet_sweeps.py` does; the watch service itself is not run (it is the owner's
  background process, not a planner call). Time advances by setting `WUWEI_NOW`.
- The solo-owner raise is its own short test on a `Day(..., solo=True)` workspace; the main
  day keeps its two reviewers so ping and channel post stay covered. Close is covered by the
  main day.
- The owner decision record reuses `VALID` from `tests/test_decision.py`, made one-way and
  owner-decided.
- The release smoke (`_pipeline/release.sh`) is outside the repository and already probes
  `$W state get` through PreToolUse; the repository has no shared launcher-probe script, so
  it is left as is.
- The fault-injection tests simulate the reintroduced bugs by replacing a guard module's
  `GUARDS` list with `monkeypatch` (discovery reads `GUARDS` on every hook), because
  disabling `shell._launcher` alone no longer reproduces the refusal after #205's
  `mentions(..., script=True)` change.
- The existing time assertion (`< 20` s) stays; the day runs in about 2 s today.
