# Feature Specification: a seat counts as started only when the harness launched it, and once

**Feature branch**: `claude/seat-count`
**Item**: seat-count, tier standard, goal G-2
**Input**: PreToolUse records `seat.started` for every Agent call, including the launches the
harness then rejects (two today). `running()` subtracts stop rows from start rows, so a rejected
launch, a stop that fires more than once, or a resumed seat skews the count, and the Stop hook stays
quiet or speaks at the wrong time.

## The promise in my words

A seat is started when the harness says it launched one, not when the model asks for one. The
harness runs PostToolUse for Agent and Task only after a launch succeeds, so `seat.started` moves
there and carries the `agentId` from the tool response. `running()` stops counting rows: it takes the
set of agent ids started today and removes every id that has a `seat.stopped` row today. A rejected
launch writes nothing; a seat stopped three times or resumed is one id, so it counts once.

The Codex `spawn_agent` mapping only carries the spawned agent's id into the same `agentId` field.
report.py and the rest of the Codex mapping stay as they are.

The acceptance scenarios, restated:

1. An Agent call with an unknown agent type gets no PostToolUse. After the hooks run there is no
   `seat.started` row.
2. A background launch returns a tool response holding `agentId: 'a1'`. PostToolUse records
   `seat.started` with agent `a1`.
3. Seat `a1` has three start and stop pairs (blocked stops and a resume) and seat `a2` has a start
   and no stop. `running()` returns 1.
4. The runtime size test still passes at 3,000 lines or fewer.

## Requirements

- FR-001: PreToolUse writes no `seat.started` row.
- FR-002: PostToolUse for Agent or Task writes `seat.started` with role, description, session and
  agent, only when the response's `agentId` is a non-empty string.
- FR-003: `running()` counts today's started string agent ids with no `seat.stopped` row under that id.
- FR-004: A Codex `spawn_agent` PostToolUse carries a string `agent_id` from its response as
  `agentId`; any other response carries none, so no seat is recorded.
- FR-005: The runtime stays at 3,000 lines or fewer.

## Clarifications

- Order does not matter: a foreground seat's SubagentStop comes before the Agent tool's
  PostToolUse, so its stop row precedes its start row. A set difference counts it as stopped either
  way.

## Assumptions

- The Agent tool response's `agentId` equals the `agent_id` that SubagentStop carries for that seat.
  Overturned by: a SubagentStop payload whose id differs from the launch's `agentId`; the seat would
  then count as running all day.
- A Codex `spawn_agent` response is a dict or a JSON string holding `"agent_id"`. Overturned by a
  real Codex payload without that key; the seat then records with no agent, as an unknown id would.
- A launch whose response has no non-empty string `agentId` (missing, empty, a list, or a response
  that is not a dict) records no `seat.started`. No stop row could clear it, so recording it would
  keep `running()` at 1 or more all day and silence the Stop hook. Overturned by a harness that
  launches seats without returning an id; such seats would then not hold the Stop hook back.
- `running()` counts only string agent ids, so rows written before this change (no `agent`) and a
  stop row with a non-string id neither raise nor keep the count up.
- Line numbers in the promise predate #1081 and #1082; the code was located by name.
