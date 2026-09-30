# Feature Specification: The loop's remaining joints

**Feature Branch**: `225-loop-joints`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #225, "fix(team): the loop's remaining joints: continue, gate role
names, phases after raise and merge, decisions from pr act". Design spec sections 4.2.1,
5.2, 5.3 and 5.8. Depends on #208, #206 and #222 (all merged on `main`).

## Evidence (v0.6.0 operator dry run, 2026-09-30)

Reproduced read-only against the dry-run workspace by calling
`wuwei.guards.protect_state.check_bash` in process on the recorded payloads, and from
the step log of the same run.

1. `wuwei runtime continue '<job JSON>' '<feedback>'` is refused by the state guard with
   "State and config files are protected". The job JSON's `prompt` field contains
   `Read instructions <workspace>/.wuwei/generated/agents/sentinel-quality.md`. Root
   cause: `_write_targets` in `cli/wuwei/guards/protect_state.py` (line 344,
   `return protected`) treats every argument of any program not on its short reader list
   as a potential write target. `_protected` then resolves the whole JSON string as a path
   (`cwd / '<json>'`), whose parts contain `.wuwei` then `generated`, so
   `_protected_name` matches. The same happens for `bin/wuwei verdict lint
   <workspace>/.wuwei/generated/agents/x.md`. The `"$(cat job.json)"` form passes only
   because the argument is dynamic.
2. `wuwei runtime dispatch arch <brief> <worktree>` exits 2 with "workspace instructions
   unavailable; run wuwei agents build", though the generated agents exist.
   `sentinel-arch` works. Root cause: `cli/wuwei/commands/runtime.py` (lines 31 to 33)
   passes `args.role` unmapped, while `wuwei brief` maps `arch|quality|security` to
   `sentinel-<role>` (`cli/wuwei/commands/brief.py` line 42, `dispatch.ROLES`). Then
   `security.agent_path` (`cli/wuwei/security.py` lines 72 to 75) raises the
   "run wuwei agents build" message for any role whose generated file is absent, known
   role or not.
3. After `wuwei pr raise` the item stays in `delta` (step `state-phase`); after `pr state`
   reports `merged` the item stays in `raised` until a manual `state transition ...
   merged`. Root cause: `state.record_pr` (`cli/wuwei/state.py` lines 335 to 362) links
   the PR but never moves the phase, and `pr_actions.observe`
   (`cli/wuwei/pr_actions.py` lines 147 to 220) records the observed `merged` state but
   never touches the linked item.
4. `pr act` writes `D-1` for a scope disagreement; `wuwei nudges` and the status line do
   not list it, and `wuwei decision outcome D-1 defer` refuses with "route this pending
   owner decision first". Even after `wuwei decision route D-1`, `nudges` still does not
   list it. Root cause: `pr_actions._thread` (lines 368 to 391) calls `decision.write`
   without routing; routing lives only in `commands/decision.decide` (lines 38 to 49);
   `owner_outcome` (line 82) requires a route; and `decision.routed` is a silent event
   (`cli/wuwei/signal.py` line 14) while no code emits the `decision.one_way` event that
   `status.scan` and `signal.classify` would surface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Continue a stopped sentinel through the hook (Priority: P1)

The planner continues a sentinel with `wuwei runtime continue '<job JSON>' '<feedback>'`,
the documented form. The job JSON quotes the generated instructions path under
`.wuwei/generated/agents/`. The call passes PreToolUse.

**Why this priority**: every delta round depends on it; today the documented form is
refused and the planner must fall back to `"$(cat file)"`.

**Independent Test**: pipe a PreToolUse Bash payload with that command through
`wuwei hook PreToolUse` in a secured test workspace; exit 0.

**Acceptance Scenarios**:

1. **Given** the job JSON from `runtime dispatch` (its `prompt` names
   `<ws>/.wuwei/generated/agents/sentinel-quality.md`), **When**
   `bin/wuwei runtime continue '<json>' 'feedback'` goes through PreToolUse, **Then** the
   hook exits 0.
2. **Given** the same workspace, **When** a `wuwei` command redirects its output into a
   protected file (`bin/wuwei state get > .wuwei/config.toml`), **Then** the hook still
   refuses (exit 2).
3. **Given** the same workspace, **When** a non-CLI program writes a protected path
   (`cp x .wuwei/generated/agents/a.md`, `tee .wuwei/config.toml`), **Then** the hook
   still refuses.

---

### User Story 2 - Dispatch a gate with the role names dispatch next returns (Priority: P1)

`wuwei dispatch next` returns gate roles `arch`, `quality`, `security`. `wuwei runtime
dispatch arch <brief> <worktree>` launches the `sentinel-arch` seat, as `wuwei brief
arch ...` already does.

**Why this priority**: the planner follows `dispatch next` literally; every gate launch
failed with a misleading "run wuwei agents build".

**Independent Test**: in-process `runtime.run` with a fake adapter records the role it
receives; and the Claude adapter in a secured workspace with generated agents returns
`agent_type: wuwei:sentinel-arch`.

**Acceptance Scenarios**:

1. **Given** `runtime dispatch arch <brief> <worktree>`, **When** it runs, **Then** the
   adapter receives `sentinel-arch`, the seat policy for `sentinel-arch` selects the
   runtime, and the Claude job carries `agent_type: wuwei:sentinel-arch`.
2. **Given** a secured workspace with generated agents, **When**
   `runtime dispatch nosuchrole ...` runs, **Then** the result is exit 1 "unknown role,
   brief or worktree", not the "run wuwei agents build" message.
3. **Given** a secured workspace whose `generated/agents/sentinel-arch.md` is missing,
   **When** `runtime dispatch arch ...` runs, **Then** it exits 2 naming
   `run wuwei agents build`.

---

### User Story 3 - Phases follow raise and merge (Priority: P2)

`wuwei pr raise` moves the item to `raised`. A merge observed by `pr state` (the same
observation `pr act` and the watch poll use) moves it to `merged`. `report` and the status
line agree with no manual `state transition`.

**Why this priority**: report, status and close read the phase; manual bookkeeping was
missed in the dry run.

**Independent Test**: raise through the shepherd fakes and read the item phase; then set
the fake PR to merged, run `pr state`, and read the phase and the report.

**Acceptance Scenarios**:

1. **Given** an item in `delta` (or `gate`), **When** `pr raise` succeeds, **Then** the
   item phase is `raised`, the build record's `fix_rounds` resets as a manual
   `delta -> raised` transition would, and the `pr.raised` event carries
   `phase_changes: {item: raised}`.
2. **Given** that raised item, **When** `pr state` observes the PR merged, **Then** the
   phase is `merged`, the `pr.action` event carries `phase_changes: {item: merged}`, and
   `wuwei report` lists the item under Merged.
3. **Given** an item not in `raised` (for example `fix`), **When** its PR is observed
   merged, **Then** the phase is unchanged (no illegal transition, no error).

---

### User Story 4 - Decisions from pr act reach the owner (Priority: P2)

A decision created by `pr act` is routed when it is created, is listed by `wuwei nudges`
and counted in the status line while pending, and `wuwei decision outcome` answers it
directly.

**Why this priority**: an owner decision the owner never sees stalls the PR; the dry run
needed an undocumented `decision route` step.

**Independent Test**: fake a scope-disagreement thread, run `pr act`, then `nudges`,
`status --line` and `decision outcome` (host confirmation stubbed) with no
`decision route` call.

**Acceptance Scenarios**:

1. **Given** `pr act` creating an owner decision `D-n`, **When** it returns, **Then**
   `decision_routes` holds `D-n` and a `decision.routed` event was recorded.
2. **Given** that pending decision, **When** `wuwei nudges` runs, **Then** it lists a row
   for `D-n` in the Decisions lane, and `status --line` counts it as a nudge.
3. **Given** that pending decision, **When** the owner runs `wuwei decision outcome D-n
   defer` on the host, **Then** it records the outcome with no "route this pending owner
   decision first" refusal, and the next `nudges` no longer lists `D-n`.

### Edge Cases

- A `wuwei` command whose argument is a bare protected path (`bin/wuwei verdict lint
  .wuwei/generated/agents/x.md`) is data too: the CLI is the only state writer and
  validates its own inputs.
- The owner-action guard (`_owner_action`) runs before write targets and is unchanged:
  `bin/wuwei decision outcome ...` from agent tools is still refused.
- `python3 -m wuwei ...` without `-P` whose arguments mention `.wuwei` stays refused as an
  opaque interpreter (existing rule, out of scope).
- `echo` or other programs quoting a protected path in text are out of scope and keep
  their current behaviour.
- `wuwei decision route D-n` on a decision `pr act` already routed stays a no-op exit 0.
- A routed decision answered by the owner drops out of `nudges`; an unreadable
  `decision_routes` ledger makes `nudges` and `status` fail closed (exit 2, unmeasured).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The state guard MUST NOT treat any argument of a `wuwei` CLI invocation
  (program basename `wuwei`, or `python -m wuwei`, as recognised by `_wuwei_action`) as a
  write target. Shell redirects on that invocation MUST still be checked.
- **FR-002**: The state guard MUST keep refusing every write form it refuses today for
  programs other than the `wuwei` CLI.
- **FR-003**: `wuwei runtime dispatch` MUST map `arch`, `quality` and `security` to
  `sentinel-<role>` (the mapping `wuwei brief` uses) before selecting the seat policy and
  calling the adapter.
- **FR-004**: The "run wuwei agents build" reason MUST be given only for a known role
  whose generated instructions file is missing; an unknown role MUST report
  "unknown role, brief or worktree" (exit 1).
- **FR-005**: `wuwei pr raise` MUST move the raised item from `gate` or `delta` to
  `raised` in the same state write that links the PR, applying the same side effects as
  `state transition` (the `fix_rounds` reset on `delta -> raised`).
- **FR-006**: An observation of a merged PR (`pr_actions.observe`, used by `pr state`,
  `pr act` and the watch poll) MUST move each linked item in `raised` to `merged` in the
  same state write as the observation.
- **FR-007**: A decision created by `pr act` MUST be routed at creation through the same
  routing writer `wuwei decision route` uses (records `decision_routes` and a
  `decision.routed` event).
- **FR-008**: `wuwei nudges` and the status line MUST list each routed decision that has
  no owner outcome, as a `nudge` in the `Decisions` lane, and drop it once the owner has
  answered.
- **FR-009**: `wuwei decision outcome` MUST keep its existing checks (owner terminal, host
  confirmation, already answered, unrouted decisions still refused); only decisions from
  `pr act` now arrive routed.

### Key Entities

- **Item phase** (`state.items.<id>.phase`): now also moved by `pr raise` and by merged
  observations, always through the same legality check as `state transition`.
- **Decision route** (`state.decision_routes.<D-n>`): unchanged shape
  (`reversibility`, `recommendation`), now also written at `pr act` creation.

## Success Criteria *(mandatory)*

- **SC-001**: The four acceptance scenarios of issue #225 pass as automated tests.
- **SC-002**: The full suite passes; the only existing test edited is the scripted day
  (`tests/test_e2e_day.py`), which drops its two manual transitions (`raised`, `merged`)
  and reads phase moves from `phase_changes`.
- **SC-003**: No new state key, event kind, config key, module or dependency.

## Assumptions

- #222 is merged (commit 7c2bb20); this work builds on its `_owner_action` and
  `_wuwei_action` helpers in `protect_state.py` without changing them.
- FR-001 covers every argument of the CLI, not only quoted ones: normalized argv carries
  no quote metadata, and the constitution makes the CLI the only writer of workspace
  state. A fake `wuwei` script in the working tree could write its arguments, but such a
  seat can already run any script that writes a hard-coded path, so no new bypass class
  opens.
- "Performed by `wuwei merge`" is covered by the observation path: `wuwei merge` records
  only `accepted` (which can mean enqueued); the actual merge is read by the next watch
  poll, `pr state` or `pr act`, all of which go through `pr_actions.observe`.
- Only `raised -> merged` is automatic. An item in `fix` or `delta` whose PR merges, or a
  claimed PR whose item never reached `raised`, keeps its phase; the planner transitions
  it, as today.
- `pr raise` moves only from `gate` or `delta`; any other phase (for example a manual
  `raised` before the raise) is left as is, so a PR already created on the host is never
  orphaned by a phase refusal.
- The pending-decision nudge applies to every routed decision without an owner outcome,
  whatever created it; that is the shared spot and matches spec 5.4 (the owner is asked
  for one-way decisions). A routed decision parked through a PR disposition keeps
  nudging until the owner records its outcome.
- The producer hints in `state.STATE_PRODUCERS` (`decision_routes`: "wuwei decision
  route"; item `phase`: "wuwei state transition") stay as they are; they name the owning
  command for a refused generic write and remain correct for manual writes.
- Docs: the `docs/site/reference.md` "Automatic phases" row gains the raise and merge
  moves and the gate alias for `runtime dispatch`. No config key is added, so
  `docs/site/configuration.md` and templates are unchanged.
