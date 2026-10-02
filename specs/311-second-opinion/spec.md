# Feature Specification: A second-opinion gate on a different model for STANDARD and FULL items

**Feature Branch**: `311-second-opinion`
**Created**: 2026-10-02
**Status**: Ready
**Input**: GitHub issue #311, "feat(gates): a second-opinion gate on a different model for
STANDARD and FULL items". Owner agreement 2026-10-02. The three sentinels run on the same model
family as the builder and share its blind spots; on 2026-09-30 a Codex review of the whole
system found issues four Claude dry runs had not.

## Problem (read on `main`, b420c12)

There is no dry-run workspace for this issue; it is a new gate, so the root causes below are read
from the code with file and line. Each one would stop a second-opinion verdict from ever reaching
the gate set.

1. No config key and no gate record for a second model. `cli/wuwei/workspace.py` `SCHEMA` (lines
   38 to 156) has no top-level `gates` table; `cli/wuwei/dispatch.py` `tier` (lines 82 and 83)
   records only `roles`, and `gate_set` (lines 15 to 22) refuses any role outside `ROLES`.
2. A non-Claude sentinel can never be received. `dispatch.receive` (lines 261 to 263) requires a
   stopped seat record; the only writer of a sentinel seat is the PreToolUse Agent guard
   (`cli/wuwei/guards/agent_launch.py` line 162), which refuses any role whose runtime is not
   Claude (line 107). `wuwei runtime dispatch` (`cli/wuwei/commands/runtime.py`) starts a Codex
   job but registers no seat, and nothing polls a Codex sentinel to completion.
3. The Codex adapter cannot be told which model to run. `adapters/runtime/codex.py` `dispatch`
   (lines 51 to 55) passes `--fresh --background [--write]` only; the companion accepts
   `--model`. The port signature `dispatch(role, brief_path, worktree, write)` is fixed by
   `registry.PARAMETERS` and `tests/test_adapters.py`.
4. A Codex sentinel running beside the Claude sentinels would fail on their files.
   `codex.result` (lines 131 to 138) lints every `gate-*.md` written since the job started with
   the job's role; with role `sentinel-quality` an arch verdict written in parallel is linted as a
   quality verdict and fails for its missing `Simplicity:` row, so the Codex result exits 1 and a
   rejection is recorded against the arch file.
5. A Codex seat runs in the item worktree (`worktrees/<item>`), and the verdict path is
   `.wuwei/days/<date>/decisions/gate-<name>.md` outside it; the write sandbox (unchanged by this
   issue) may refuse that write, so the seat's verdict can arrive only as its final message.
6. Nothing compares two verdicts on the same item. `cli/wuwei/retro.py` (lines 97 to 108) lists
   one row per verdict file with its decision only, and receive (lines 315 to 318) keeps the text
   of non-blocking findings only, so a delta that rewrites the file loses the initial findings.
7. Gate verdict records carry no cost or time. `seat.usage` is emitted for builders only
   (`cli/wuwei/commands/build.py` line 249).

Already in place and reused: the tier computation and recorded gate set (#280); the single fix
round and delta rule in `dispatch.next_step`; the verdict lint and receive; the PR guard's
recorded-gate check (`cli/wuwei/guards/pr.py` `_recorded_gates`) and the merge policy, which both
iterate `dispatch.gate_set`; the Codex polling pattern in `commands/build.py` `run_loop`; the
usage normalization in `build.record_result`; `brief.write` for a logged, hashed brief.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A fourth verdict from a different model on STANDARD and FULL items (Priority: P1)

With `gates.second_opinion = "codex:<model>"`, every STANDARD or FULL item gets one more gate:
the configured role (default quality) runs again on that runtime and model with the same brief
body and verdict contract, and its verdict is a fourth record that carries its runtime and model.

**Why this priority**: it is the issue; a model with different blind spots reviews the change
before the PR.

**Independent Test**: with a fake runtime, tier a STANDARD item, log the three gate briefs, run
`wuwei dispatch opinion <item>`, receive the three Claude verdicts, and read `gate_verdicts`.

**Acceptance Scenarios**:

1. **Given** second opinion on and a STANDARD item, **When** its gates run, **Then** four verdict
   records exist (`arch`, `quality`, `security`, `quality@codex`), and the `quality@codex` one
   carries `runtime: codex` and `model: <model>`.
2. **Given** the same item with a blocking finding in the second-opinion verdict only, **When**
   `dispatch next` runs, **Then** it opens the single fix round naming that verdict file; after the
   fix, only that gate re-checks, on the same runtime and model; a blocking finding left after the
   delta escalates and the PR guard refuses `gh pr create`.
3. **Given** a FULL item, **Then** the same fourth gate runs.
4. **Given** a LIGHT item, **Then** no second opinion runs: the gate set is quality only and no
   `run` action is returned.
5. **Given** the option off (the default), **Then** the tier record, the gate set, `dispatch next`
   actions and every existing verdict, dispatch and mutation test are unchanged.

### User Story 2 - The retro says whether the second opinion pays (Priority: P2)

The owner reads, per item, the findings only the second opinion raised and the findings only the
first model raised, with the cost and time of each verdict, so they can turn the option off when
it stops paying.

**Independent Test**: record a first and a second-opinion initial verdict with one shared and one
unique finding each, compile the retro, and read its `## Second opinion` section.

**Acceptance Scenarios**:

1. **Given** the retro on a day with second-opinion verdicts, **Then** it lists the findings unique
   to each model for the day, and the model, cost and duration of both verdicts.
2. **Given** a day without second-opinion verdicts, **Then** the retro has no such section.

### User Story 3 - Cost and time per verdict (Priority: P3)

Every gate verdict record carries `usage` (input and output tokens, cost, model, duration), with
`unmeasured` where the runtime reports nothing.

**Acceptance Scenarios**:

1. **Given** a second-opinion verdict, **Then** its record carries the Codex-reported usage, with
   the run's wall time as duration when Codex reports none, and a `seat.usage` event is written.
2. **Given** a Claude sentinel verdict, **Then** its record carries the seat's duration from its
   launch and stop times, its seat-policy model, and `unmeasured` cost and tokens.

### Edge Cases

- Config `gates.second_opinion` not `off` and not `<runtime>:<model>`, an unknown runtime, or
  runtime `claude` or `none`: config load fails with a `ConfigError` naming the key.
- Config changed after an item was tiered: the item keeps the gate set recorded at tiering.
- The first-model brief for the role is not logged yet: no `run` action for the second opinion.
- An attempt to launch the second-opinion brief through Agent: refused by the launch guard.
- `wuwei dispatch opinion` rerun while the job runs: it polls the recorded job and dispatches
  nothing new; rerun after its record exists: it returns the record.
- The second-opinion verdict is rejected by the lint: exit 1 with the reason; a rerun continues the
  same job with the rejection as feedback.
- Codex error body, non-zero exit, timeout or missing job id: exit 2, nothing recorded as PASS.
- Host seat ceiling reached: the run is refused (exit 1) like any seat launch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Config gains `gates.second_opinion` (`"off"` default, or `"<runtime>:<model>"`) and
  `gates.second_opinion_role` (`arch`, `quality` or `security`, default `quality`). The runtime
  must be an installed runtime adapter other than `claude` and `none`; the model matches
  `[A-Za-z0-9][A-Za-z0-9._-]*`.
- **FR-002**: When the option is on and the computed tier is `standard` or `full`, the recorded
  tier carries `second_opinion: {role, runtime, model}`. With the option off, or a `light` tier,
  the record has no such key.
- **FR-003**: `gate_set` returns the recorded roles plus the second-opinion gate `<role>@<runtime>`
  when recorded; a malformed recorded second opinion fails closed. Every consumer of the gate set
  (dispatch, receive, the fix and delta rounds, the PR guard and the merge policy) therefore
  treats it like any gate: a blocking finding from either model blocks; a FIX from only the
  second opinion opens the same single fix round; the delta is checked by the gate that raised it.
- **FR-004**: `dispatch next` returns, in `seats`, one `run` action for the second-opinion gate
  when it is missing for the round and ready (initial: the first-model brief for its role is
  logged; delta: its initial verdict is FIX). The action carries `gate`, `runtime`, `model` and
  `command: wuwei dispatch opinion <item>`.
- **FR-005**: `wuwei dispatch opinion <item>` writes the second-opinion brief (the first-model
  brief body under its own name `<first seat>-<runtime>`, with a `Model:` header line), dispatches
  it through the runtime adapter with write access, polls it, collects its result, writes the
  seat's final message to its verdict file when the seat did not write the file, records the seat
  as stopped with its usage, and receives the verdict through `dispatch.receive`. In the delta,
  and after a rejected verdict, it continues the same job with feedback. It prints the record.
  Exit 0 recorded, 1 refused or rejected, 2 could not run.
- **FR-006**: The Codex adapter passes `--model <model>` when the brief header has a `Model:` line,
  and lints only the job's own verdict file in `result`.
- **FR-007**: The Agent launch guard refuses a logged second-opinion brief.
- **FR-008**: `dispatch.receive` accepts any gate of the item's gate set; it lints, scans and checks
  the seat against the base role; its record adds `findings` (all finding blocks), `usage`, and,
  for the second opinion, `runtime` and `model`.
- **FR-009**: The steward retro adds a `## Second opinion` section when today has a second-opinion
  verdict: per item, the initial-round findings only one model raised (matched on the first
  `file:line` citation, else on the normalized text), and the model, cost and duration of both
  verdicts.
- **FR-010**: Nothing new is trusted: no new state key, no new event kind; the existing producers
  (`seats`, `seat launched`, `seat stopped`, `seat.usage`) gain `wuwei dispatch opinion` as a
  named producer. The Codex seat runs in its write sandbox as today.

### Key Entities

- **Tier record** (`items.<id>.gates`): adds optional `second_opinion: {role, runtime, model}`.
- **Gate verdict record** (`gate_verdicts["<item>:<gate>:<round>"]`): `gate` may be
  `<role>@<runtime>`; adds `findings`, `usage`, and `runtime` and `model` for a second opinion.
- **Seat record** (`seats.<name>`): adds `stopped_at`; a second-opinion seat also holds
  `runtime`, `model`, `job` and `usage`.

## Success Criteria *(mandatory)*

- **SC-001**: With the option on, a STANDARD item reaches `raise` only with four passing records
  and is refused at `gh pr create` while the second-opinion record is missing or blocking.
- **SC-002**: With the option off, the full suite passes with no change to existing tests.
- **SC-003**: The retro names every finding unique to each model for each item with a second
  opinion, and both verdicts' cost and duration.
- **SC-004**: No test calls a real Codex; every second-opinion test uses a fake runtime.

## Assumptions

- One second opinion per item, on one role; a list of roles or runtimes is not needed by the
  issue. Overturn if the owner asks for a second opinion on several roles.
- `claude` is refused as the second-opinion runtime: the point is a different model family, and a
  Claude seat runs in the planner session through Agent, not through a polling adapter. Overturn
  by adding a Claude `model` to the gate `run` action if a same-family second opinion is wanted.
- The model reaches Codex through a `Model:` line in the CLI-written brief header rather than a new
  port parameter, so the fixed runtime port, its three adapters and their fakes stay unchanged.
  Overturn when a second caller needs a per-dispatch model.
- The delta continues the same Codex job through the adapter's existing `continue_job`
  (`--resume-last` in the worktree), as Claude deltas continue the same seat. With a Codex builder
  in the same worktree, resume-last could resume the builder's thread; that combination is not
  supported and is marked with a `ponytail:` comment.
- When the Codex seat cannot write its verdict file from its sandbox, its final message is the
  verdict; the runner writes it to the verdict path and the same lint decides. This trusts nothing
  new: both are the seat's own output, and receive lints either.
- The second opinion is frozen at tiering: changing the config mid-day does not change the gate
  set of an item already tiered.
- Claude sentinel cost and tokens are recorded as `unmeasured`: the SubagentStop payload for a
  sentinel is not parsed for usage in this issue; duration comes from seat launch and stop times.
- "Findings unique to a model" match on the first `file:line` citation of each finding, else on its
  normalized text. Two models citing different lines for the same defect count as two unique
  findings; marked with a `ponytail:` comment.
- The retro section is written as a table like the other retro sections; `owner.verbosity` does not
  shape the retro file today and is not changed here.
- The planner runs the `run` action's command through Bash in the background (it blocks up to
  `build.poll_timeout_seconds`), in parallel with the Agent launches of the Claude sentinels.
- No dry run reproduces this: the issue adds a gate; the root causes are cited from `main`.
