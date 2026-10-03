# Feature Specification: MCP findings warn by default under guarded, block only under strict

**Feature Branch**: `351-mcp-warn-default`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #351, "feat(security): MCP findings warn by default under guarded,
block only under strict, and the owner accepts a baseline in one command". Owner policy
(2026-10-03): warn, do not block everything by default; the posture decides. Evidence: the
second first-day trial (development build of 0.12.0) stopped the day before the first seat on
one `critical` registry finding (a `tool_redirect` heuristic hit on a server the owner
installed). Builds on #331 (posture profiles) and #325 (attached servers, `scanner.mcp.block`).

## Root cause (reproduced on main, ed28ab4)

Reproduction (read-only; a throwaway workspace under the session scratchpad built with the
`configured` and `fake_scanner` helpers of `tests/test_mcp.py`, default config, the fake
scanner returning one `critical` finding):

```
posture  ('guarded', {... 'mcp': 'warn', ...})
block    ['critical']
check    exit 1  'MCP registry findings: owner decision required in .wuwei/days/<date>/decisions/D-1.md'
cached   exit 1  '... D-1.md (mcp: warn, floor: scanner.mcp.block)'
propose  StateError '... D-2.md (mcp: warn, floor: scanner.mcp.block)'
```

The posture table already says `mcp = warn` under guarded, but the warn is overridden:

1. `cli/wuwei/workspace.py:55`: `scanner.mcp.block` defaults to `["critical"]`, and
   `templates/workspace/config.toml:108-109` writes `block = ["critical"]` into every new
   workspace.
2. `cli/wuwei/mcp.py:284-306` (`cached`): under guarded (mcp `warn`, posture not `observe`)
   the `scanner.mcp.block` list acts as a floor (`note = 'floor: scanner.mcp.block'`, line
   305), so a pending `critical` finding returns exit 1 from `_gate` (line 279-280).
3. `cli/wuwei/plan.py:115-117` turns that exit 1 into a `StateError`: the morning plan
   refuses, and `agent_launch.check_mcp` refuses every seat.

So under the default posture one heuristic hit at `critical` stops the day. The same exit 1
names only the decision file (`mcp.py:271` and `:280`), never what was found or the command
to run, and the board's attention row for each `mcp.finding` reads only `mcp.finding`
(`commands/status.py:125`: the payload has no `reason`).

Related, not this issue: the second check inside `plan propose` queued D-2 for the same
finding (one decision per check); #350 owns report and decision hygiene.

## User Scenarios & Testing

### User Story 1 - Guarded warns on a finding and the day proceeds (Priority: P1)

The owner runs the default posture. A registry finding, at any severity, is recorded, shown
with what was found and the command to review it, and does not stop the plan or a seat.

**Independent Test**: `tests/test_mcp.py` with the `configured` fixture, default config,
`fake_scanner` returning one `critical` finding.

**Acceptance Scenarios**:

1. Given guarded and a `critical` first-measurement finding, when `mcp check` runs, then it
   exits 1 and its reason is the one-line summary: the severities found, the decision record
   and `bin/wuwei mcp decide`.
2. Given the same, when `plan propose` runs, then it returns the plan path, prints the
   summary on stderr, and the plan's `mcp` sweep line carries the summary.
3. Given the same, when the launch gate runs (`mcp.cached`, `agent_launch.check_mcp`), then it
   exits 0.
4. Given the same, then the board's attention rows (`status.attention`, read by `wuwei_board`
   and the dashboard) show the finding (severity, type, server) and `bin/wuwei mcp decide`;
   the summary line is what the planner relays to the owner's DM (A5).

### User Story 2 - Strict blocks critical and high until the owner decides (Priority: P1)

**Independent Test**: as US1 with `[security]\nposture = "strict"\n`.

**Acceptance Scenarios**:

1. Given strict and the same `critical` finding, then `mcp.cached` exits 1 and
   `agent_launch.check_mcp` and `plan propose` refuse, each reason holding the summary and
   `(mcp: block, security.areas.mcp)`.
2. Given strict and a `high` finding, then the same.
3. Given strict and that pending finding, when the owner accepts it with `mcp decide`, then
   the gate exits 0 (existing `decide` path, unchanged).

### User Story 3 - The block list is per posture and says when it has no effect (Priority: P2)

**Independent Test**: `tests/test_posture.py` `checked` fixture; the template read from
`templates/workspace/config.toml`.

**Acceptance Scenarios**:

1. Given the default template, then `[scanner.mcp]` has no `block` key and its comment
   explains the per-posture defaults (observe and guarded: none; strict: critical, high and
   unmeasured) and that the key overrides them.
2. Given observe with `scanner.mcp.block = ["critical"]`, when `config check` runs, then it
   prints one line saying `scanner.mcp.block` has no effect under observe, and the exit code
   is the same as without the key.
3. Given guarded with `scanner.mcp.block = ["critical"]` (a workspace created from the old
   template), when `config check` runs, then it prints one line naming the list as an
   override of the guarded default, and the launch gate still blocks a `critical` finding.

### Edge Cases

- A registry check that could not run (invalid input, interrupted, stale or missing record)
  still blocks under guarded and strict and warns under observe (unchanged, fail closed).
- An unmeasured server warns under guarded (unchanged: `unmeasured` was never in the default
  list) and blocks under strict.
- A v0.11.0 status record with a pending decision and no `severities` field: under guarded it
  now warns (no default severity blocks); under strict it blocks.
- `security.areas.mcp = "off"`: unchanged (not checked); `config check` says a non-empty
  `scanner.mcp.block` has no effect.
- Scanner-supplied text on the board: server name, type and severity are shown only when they
  match `mcp.NAME`; tool names never reach the board (they stay in the reports).

## Requirements

### Functional Requirements

- **FR-001**: `scanner.mcp.block` defaults to `[]`. The posture's `mcp` level is the single
  source of the per-posture default: `warn` (observe, guarded) blocks no finding; `block`
  (strict) blocks `critical`, `high` and `unmeasured` (the existing union in `mcp.cached`).
  No second mode flag, no new table.
- **FR-002**: An explicit `scanner.mcp.block` keeps today's meaning: under guarded it blocks
  the listed severities; under strict it adds to the strict set; under observe at `warn` and
  with `mcp = "off"` it has no effect.
- **FR-003**: The template's `[scanner.mcp]` has no `block` key; a comment documents the
  per-posture defaults and the override.
- **FR-004**: `config check`, in the Posture section, prints one line when
  `scanner.mcp.block` is non-empty: "no effect" when the gate never reads it (mcp `off`, or
  observe at `warn`), otherwise the list as an override of the posture default. Reported, not
  a finding.
- **FR-005**: One helper builds the one-line summary for a pending finding batch: the
  severities, the decision record path and `bin/wuwei mcp decide`. `mcp check` (exit 1) and
  the launch gate (exit 1) both use it.
- **FR-006**: `plan propose` prints the check's reason on stderr when the check exits non-zero
  and the gate lets the plan proceed.
- **FR-007**: Each `mcp.finding` attention row reads `MCP <severity> <type> finding on
  <server>: run bin/wuwei mcp decide`; a value that does not match `mcp.NAME` is shown as
  `unnamed`. Tiers unchanged.
- **FR-008**: Docs: `docs/site/security.md` (S3 paragraph, MCP floor bullet, guarded line),
  `docs/site/configuration.md` (`scanner.mcp.block` paragraph), `docs/site/concepts.md` (one
  paragraph: why warn is the default), design spec S3 amendment and 9.1 MCP bullet, and a
  recovery entry in `docs/site/recovery.md` for a finding on a server the owner installed,
  linking the upstream scanner issue https://github.com/taoq-ai/ziran/issues/447.

### Out of scope (must not change)

- `mcp.check` queuing, events and report handling; `_queue` (decision text); `mcp.decide`;
  `_cached`; the scanner adapter; signal tiers; the hook posture; `agent_launch`.
- WUWEI does not change the severity the scanner reports.

## Success Criteria

- **SC-001**: Under the default posture, the trial's case (one `critical` first measurement)
  produces a plan and launches seats, with the finding and the command visible.
- **SC-002**: Under strict, the same case refuses launches until `mcp decide`.
- **SC-003**: The full suite passes.

## Assumptions

- A1 (scope vs acceptance conflict): the scope says "a first measurement is a warn in every
  posture", while acceptance 2 says strict refuses the same first-measurement `critical`
  finding until `mcp decide`. Acceptance is binding and fails closed (constitution II), so
  strict blocks `critical` and `high` whether first measured or drifted. Under observe and
  guarded every finding warns, so the first-measurement rule holds there by construction.
- A2: telling a first measurement from drift against an accepted baseline, and blocking a
  server that gained a publisher-capable tool, need the accepted-digest baseline that #350
  introduces (`mcp decide D-n proceed` stores it). Deferred to #350; "the owner accepts a
  baseline in one command" in the title is #350 and #354.
- A3: strict keeps `unmeasured` in its set (the #331 strict union, `mcp.py:296-297`), beyond
  the issue's `["critical", "high"]`: a server strict cannot measure is not trusted.
- A4: a registry check that could not run keeps blocking under guarded (the #325 and #331
  fail-closed floor); "warns on everything" applies to measured findings and unmeasured
  servers.
- A5: "the DM": the default control plane has no transport (`control_plane.py` docstring);
  the planner relays the `mcp check` and `plan propose` reason to the owner and Remote Control
  pushes it, so the summary with the command is what reaches the DM. Showing the pending MCP
  decision as one line through the Slack listener is #350's scope ("plan propose, the board
  and the DM show the pending MCP decision as one line with the command"); not duplicated.
- A6: existing workspaces keep the old template's explicit `block = ["critical"]`
  (`init --upgrade` only adds keys and never changes owner values). `config check` names it
  as an override and the docs say to delete the line. An upgrade rewrite that drops the old
  default belongs with #355's `init --upgrade` and `doctor --fix` rewrite (same files, chained
  after #353); flagged to the orchestrator, not done here.
- A7: the `config check` lines are reported, not findings: acceptance says "warns".
- A8: owner question relayed with this run ("the default security posture is better to be
  observe rather than guarded if we are running --shadow"): already true on main for a fresh
  `setup --shadow` and `init --shadow` (#331, #345); the remaining cleanup (a workspace that
  carries `posture = "guarded"` next to `guards.mode = "shadow"`) is #355. Under observe the
  MCP gate never blocks a finding, so `--shadow` users are covered without further change.
- A9: the upstream scanner issue is already filed by the orchestrator (taoq-ai/ziran#447);
  no seat runs `gh`.
- A10: the board shows severity, drift type and server name only; tool names come from the
  server under test and stay in the reports.
