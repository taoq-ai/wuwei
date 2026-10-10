# Feature Specification: the seat limit is not read from host memory when seats are subagents of one process

**Feature Branch**: `658-seats-not-memory`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #658 (owner, 2026-10-10, item 15): within one hour the memory-based
estimate said room for 8, 4, 6, 8 and 4 seats at 0.7, 3 and 1.5 GB per seat. Seats here are
subagents inside one Claude process, so free host memory does not track seat count.
Deliver: the memory estimate applies only when the runtime launches separate processes (the
Codex companion or a configured external runtime); with the Claude subagent runtime the
limit is `host.seats` and the pace, with no memory term. When the estimate applies, it is
smoothed (median of the last five readings) and the brief and status line say which rule
set the number.

## Root cause

Reproduced in-process with the worktree's code (a fresh temporary workspace, default config:
`adapters.runtime = "claude"`, `host.seats = 0`, a 10-core host), calling `calibrate.host`
with the free memory the owner saw and passing the result through
`pace.seats('steady', ...)`:

```text
9216 MiB free -> (8, 'host') cap 8 (host): 9 GB free, 1 GB per seat, 10 cores
5120 MiB free -> (4, 'host') cap 4 (host): 5 GB free, 1 GB per seat, 10 cores
7168 MiB free -> (6, 'host') cap 6 (host): 7 GB free, 1 GB per seat, 10 cores
9216 MiB free -> (8, 'host') cap 8 (host): 9 GB free, 1 GB per seat, 10 cores
5120 MiB free -> (4, 'host') cap 4 (host): 5 GB free, 1 GB per seat, 10 cores
host.seats=6 3072 MiB free -> (2, 'host') cap 2 (host): 3 GB free, 1 GB per seat, 10 cores
```

The owner's sequence 8, 4, 6, 8, 4 comes straight out. `cli/wuwei/calibrate.py:504`, in
`host`, computes the fit from free memory for every runtime:

```python
fit = max(1, min(running + max(0, (free - config['host']['free_memory_mb']) // seat_mib), cores))
```

and line 508 takes `cap = min(fit, seats)`, so even a configured `host.seats = 6` is only a
ceiling: the cap still follows free memory (the last row). `host` never looks at the seat
runtime. Every caller inherits the swing: plan propose (`plan.py:189`), each
`dispatch next --all` sweep (`dispatch.py:396`, which writes `cap.derived` and the day's
`cap`), the agent-launch guard (`guards/agent_launch.py:185`, the CAP and `host.seats`
refusals), `dispatch opinion` (`dispatch.py:736`) and `wuwei pace` (`commands/pace.py:15`).
`pace.seats` (`pace.py:39`) only passes `limits['cap']` and `limits['bound']` through, so
the pace is not the cause. Each reading is also used alone: nothing remembers the earlier
estimates, so one noisy free-memory sample moves the cap.

The status line does not say which rule set the number: `_groups`
(`cli/wuwei/commands/status.py`) renders `seats N/CAP` with no bound (#521 moved `bound` to
`wuwei status` only), and the bound `host` reads the same whether memory or a configured
value set it.

No orchestrator notes file exists for #658 and none names a dry-run workspace, so the
reproduction ran read-only in a temporary workspace against the worktree's code.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What decides "separate processes"? A: The seat runtimes of the day: `adapters.runtime`
  and every `runtime` in the seat policy (the day's approved one, or the proposal's at plan
  propose). Any runtime other than `claude` (and `none`, which launches nothing) launches
  its own process, so the memory estimate applies. All seats on `claude` means the
  subagent rule.
- Q: The subagent limit when `host.seats` is 0 (unset)? A: One seat per core, the existing
  "one per core" term (design 5.2, #528), stable for the day. `host.seats` set means CAP and
  the ceiling are exactly that value. The owner's positive `cap` and the token budget still
  bound CAP as today; the pace still applies through `pace.seats`.
- Q: What are "the last five readings"? A: The current estimate plus the last four recorded
  today. Each `dispatch next --all` sweep under the memory rule records its reading on the
  `cap.derived` event it already writes (a reserved kind). The median is
  `statistics.median_low`, so two readings give the lower one and the value stays an
  integer.
- Q: Bound names? A: `memory` for the smoothed memory estimate (was `host`), `host.seats`
  for the subagent rule. `owner`, `budget`, `unmeasured`, `load` and `pace careful` are
  unchanged.
- Q: Where does the status line say the rule? A: On the seats token, the one place CAP is
  shown: `seats 2/6 by host.seats (builder)`. `wuwei status` drops its separate `bound X`
  token, which the seats token now carries. This supersedes #521's choice to keep the bound
  off the line, because the owner asks for it here.
- Q: Does the free-memory floor refusal stay for subagents? A: Yes. `host.free_memory_mb`
  in the launch guard protects the host from swapping; it is a floor, not a seat count. The
  heartbeat `memory` probe and the remote session floor stay too.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subagent seats keep a steady limit (Priority: P1)

The owner runs WUWEI with Claude subagent seats. The seat limit is the configured
`host.seats` (or one per core when unset) and the pace, and it never moves when free memory
does. The status line shows the cap and that `host.seats` set it.

**Why this priority**: the defect the owner reported, on the default runtime.

**Independent Test**: call `calibrate.host` on a workspace with the default runtime and
`host.seats = 6` at several free-memory values and check `pace.seats`; run a sweep and read
the status line.

**Acceptance Scenarios**:

1. **Given** the subagent runtime and `host.seats = 6`, **When** free memory reads 9, 5, 7,
   9 and 3 GB across calls, **Then** `pace.seats('steady', limits)` is
   `(6, 'host.seats', None)` every time and `calibrate.host` never calls the host
   free-memory port.
2. **Given** the subagent runtime and `host.seats = 6` on an approved day, **When**
   `dispatch next --all` runs, **Then** the day's `cap` is 6, `cap_bound` is `host.seats`
   and `status --line` contains `seats 0/6 by host.seats`.
3. **Given** the subagent runtime and `host.seats = 0` on a 10-core host, **Then** CAP is 10
   with bound `host.seats` and the text says `host.seats unset, 10 cores`; on a 2-core host
   the ceiling still holds one gate (seats 3, CAP 2).
4. **Given** the subagent runtime, CAP 4, three seats running and free memory exactly at the
   floor, **When** a fourth builder launches, **Then** the launch guard admits it (no memory
   term); below the floor it still refuses naming `host.free_memory_mb`.

### User Story 2 - Process seats use a smoothed memory estimate (Priority: P1)

When seats run as separate processes (the Codex companion or an external runtime), the
memory estimate applies, smoothed as the median of the last five readings, and the plan,
the gate card and the status line say the memory rule set it.

**Why this priority**: the issue's second acceptance; without smoothing the process runtime
swings the same way.

**Independent Test**: record four readings today, set free memory so the current reading is
the fifth, and call `calibrate.host` with a process seat policy.

**Acceptance Scenarios**:

1. **Given** the process runtime and readings 8, 4, 6, 8 recorded today, **When** the
   current reading is 4, **Then** CAP is 6 (the median, not the latest 4), bound `memory`,
   and the text contains `median of 8, 4, 6, 8, 4`.
2. **Given** the process runtime on an approved day, **When** `dispatch next --all` runs
   twice, **Then** each sweep appends a `cap.derived` event carrying its `reading`, and the
   second sweep's CAP is the median of both readings.
3. **Given** the process runtime and no reading recorded today, **Then** CAP is the single
   current reading and the text has no median clause (today's text, bound `memory`).
4. **Given** the process runtime, **Then** the `CAP:` line of `plan.md` and the gate card
   show the text naming the rule (`cap N (memory): ...`), and `status --line` shows
   `seats 0/N by memory`.

### Edge Cases

- Mixed policy (Codex builder, Claude sentinels): any process runtime means the memory rule.
- `gates.second_opinion` on Codex alone does not switch the day to the memory rule.
- Free memory unreadable under the subagent rule: not read, so CAP is not `unmeasured`;
  cores unreadable still is (`unmeasured`, as today).
- A damaged today event log under the memory rule: no history, the current reading alone,
  and the text carries the existing `warning:` clause.
- A malformed proposal `seat_policy` at plan propose: `calibrate.host` treats it as empty;
  `_proposal` then refuses it as today.
- Before the gate (`cap_bound` empty) the seats token has no `by` clause.
- `wuwei calibrate` under the subagent rule: the report omits the free memory and seat cost
  lines (not read) and keeps cores and `derived:`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `calibrate.host` MUST apply the memory estimate only when a seat runtime of
  the day (`adapters.runtime` or a seat policy `runtime`) is neither `claude` nor `none`.
- **FR-002**: Under the subagent rule `calibrate.host` MUST NOT read free memory or the
  seat cost; the fit is `host.seats` when set, else the core count; the ceiling holds at
  least one gate; bound `host.seats`; the owner's `cap` and the token budget bound CAP as
  today.
- **FR-003**: Under the memory rule the fit MUST be the `median_low` of the last four
  readings recorded today on `cap.derived` events plus the current reading; bound `memory`.
- **FR-004**: `dispatch.launch_set` MUST record the current reading on the `cap.derived`
  event at every approved sweep under the memory rule, and otherwise write it as today (on a
  CAP or bound change).
- **FR-005**: The capacity text MUST name the rule: `(host.seats)` with
  `subagent runtime, free memory not read`, plus `host.seats unset, N cores` when unset;
  `(memory)` with `median of a, b, ...` when more than one reading exists.
- **FR-006**: The status line seats token MUST carry the bound (`seats N/CAP by <bound>`)
  when the day has one; `wuwei status` MUST NOT repeat it as a separate token.
- **FR-007**: `pace.seats`, the free-memory floor refusal, the heartbeat `memory` probe,
  `metrics.seat_cost` and the budget bound MUST NOT change.
- **FR-008**: The design spec (5.2 CAP paragraph, step loop amendment, status line, 9.2 I20)
  and the owner docs (`docs/site/concepts.md`, `docs/site/configuration.md`) MUST describe
  the two rules; `tests/test_invariants.py` I20 MUST check both.

## Success Criteria *(mandatory)*

- **SC-001**: A test shows `pace.seats` constant across five free-memory values under the
  subagent runtime, with zero free-memory port calls from `calibrate.host`.
- **SC-002**: A test shows CAP 6 from readings 8, 4, 6, 8, 4 under the process runtime.
- **SC-003**: Sweep tests show `status --line` with `by host.seats` and `by memory` for the
  two runtimes.
- **SC-004**: The full suite passes; the launch-guard hook path adds no state read (the
  guard passes the seat policy it already holds).

## Assumptions

- "The runtime launches separate processes" is decided from the seat runtimes of the day
  (`adapters.runtime` plus the seat policy). The second opinion runtime is left out: one
  seat per gate, and counting it would put a day with a Codex second opinion back on the
  memory rule the owner reported.
- With `host.seats` unset under subagents, one seat per core is the stable default; the
  owner pins `host.seats` for a smaller number. The pace (fast holds at the core count) and
  the budget still apply.
- Readings are per day (today's event log) and recorded by the sweep only; plan propose, the
  launch guard, `dispatch opinion`, `wuwei pace` and `wuwei calibrate` read them and add the
  current reading without recording it.
- The memory bound is renamed from `host` to `memory` so the two rules read apart on the
  line; earlier days keep their recorded `cap_bound` (display only, no code branches on it).
- `metrics.seat_cost` keeps measuring from `seat launched` rows; recording free memory at
  Codex seat launches is out of scope (Deferred).
- The free-memory floor stays for every runtime (Principle V: never simplify away a safety
  floor).
- No orchestrator notes file exists for #658; the issue is the only input. The worktree was
  created by `item.sh start` from a fresh fetch of `origin/main` (the preceding `git pull`
  printed no merge candidates and changed nothing).
- The design spec is amended with the code, citing the owner's issue, as #631, #633 and
  #641 did.

## Deferred

- Record free memory at Codex and external-runtime seat launches so `metrics.seat_cost`
  measures process seats; today it measures only Claude launches.
