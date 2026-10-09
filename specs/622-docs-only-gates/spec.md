# Feature Specification: one reviewer for a docs-only item, read from the diff

**Feature Branch**: `622-docs-only-gates`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #622 (owner, 2026-10-09, a study day of a pre-registration, briefs and
annotation docs): "The review gates were the best part of today. The reviewers caught real
problems." And: "Lighter review for docs-only items. One reviewer at the first round, three
only for code or a trust surface." The tier comes from the measured diff at dispatch; the
lead's proposed tier is a hint the measurement overrides; the plan and the report show the
reason and the seats each item cost.

## Root cause

Reproduced in-process on `main` with `dispatch.tier` and a stubbed `dispatch._changes`
(a neutral `docs/prereg.md` diff, no flags, SLICE track):

| Diff | Floor | Lead tier | Today | Wanted |
|---|---|---|---|---|
| `docs/prereg.md`, 30 lines | `standard` (default) | none | standard: arch, quality, security | light: one gate |
| `docs/prereg.md`, 30 lines | `light` | none | light: quality | light: one gate (quality for a pre-registration) |
| `docs/prereg.md`, 30 lines | `light` | `full` | full: three gates | light: one gate, the lead tier overridden with a reason |
| `docs/big.md`, 400 lines | `light` | none | standard: three gates | light: one gate (goal) |

In `cli/wuwei/dispatch.py`:

- `tier()` lines 77-78: the size rule raises any diff over `repos.gates.light_max_lines` to
  standard, documents included.
- `tier()` lines 81-82: the repository floor (default `standard`) lifts every light diff to
  standard, so with the shipped default no item ever gets one gate.
- `tier()` lines 85-88: a lead tier above the computed one always raises the tier.
- `tier()` line 104: the single light gate is always `quality`; there is no `goal` gate.
- `gate_set()` line 24: a recorded gate set without `quality` is refused as damaged, so
  `['goal']` cannot be recorded.

In `cli/wuwei/commands/brief.py` line 42 only `dispatch.ROLES` map to `sentinel-<role>`, so
the brief command that `dispatch next` prints for a goal gate (`wuwei brief goal ...`) would
look for a charter named `goal`.

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which paths are documents? A: A path is a document when its name ends in `.md` or
  `.rst`, or in `.txt` under a top-level `docs/` or `specs/` directory, and it is not an
  agent instruction file (`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, or anything under a
  `charters/`, `skills/`, `agents/`, `commands/`, `.claude/` or `.agents/` directory). A diff
  is docs-only when it has at least one changed path and every changed path is a document.
- Q: Which single gate? A: `quality` when any changed path is a spec or a pre-registration
  (under `specs/`, or a name containing `spec`, `prereg` or `pre-registration`); `goal`
  otherwise. A misroute costs only which one seat reads it.
- Q: What still gives three gates? A: Anything that raises the computed tier today: a lead
  flag (`trust_surface`, `boundary_relevant`, `agent_surface`), a FULL track, a trust path, a
  never-auto path, a FULL-track path pattern, a binary change. Those keep today's tiers and
  today's class sweeps. Only a diff with none of them can be docs-only.
- Q: Does the size limit apply to a docs-only diff? A: No. A long document is still one
  reviewer; `light_max_lines` stays for code.
- Q: Does the repository floor apply? A: The default floor `standard` does not apply to a
  docs-only diff. A floor of `full` is an explicit owner choice above the default and still
  applies: the item gets three gates.
- Q: And the lead's tier? A: For a docs-only diff the lead's tier is a hint: a lead tier
  above light is overridden and the record says so (`lead tier full overridden: docs-only`).
  For any other diff the lead tier still raises, never lowers (#280 unchanged).
- Q: And the pace? A: Unchanged. `pace careful` still raises a light item, docs-only
  included, to standard; the pace is the owner's day setting. `fast` and `steady` leave a
  docs-only item at one gate.
- Q: What is the second round? A: The existing light path: the same seat continues with the
  re-read feedback (`_delta_feedback(light=True)`) and rewrites its `Verdict:` and `Head:`
  lines. Only the roles that wrote FIX get a delta, so the gate set never widens.
- Q: Which depth does a docs-only item run at? A: Light, as every one-gate item today: no
  class sweep, no step zero, the three-row verdict, no second opinion, docs exempt.
- Q: Where does the owner see the cost? A: The day report gets a `## Review seats` section,
  one line per tiered item: its gate seats launched (a delta continues a seat, so it is not
  counted twice), the gate set, the tier and its reasons. The section is absent when no item
  was tiered.
- Q: Where does the plan show the reason? A: In the tier record that `dispatch next` returns
  with its gates action and `bin/wuwei why <item>` prints from `gate.tiered`:
  `docs-only: 1 reviewer (goal)`.

## User Scenarios and Testing

### User Story 1 - A docs-only item gets one reviewer (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a docs-only item (`docs/guide.md`, default floor), **When** `dispatch next`
   tiers it, **Then** the record is tier `light`, roles `['goal']`, a reason
   `docs-only: 1 reviewer (goal)`, and the action asks for one gate seat with the command
   `wuwei brief goal A goal-A --gate ...`.
2. **Given** that item and a received goal PASS, **Then** `dispatch next` returns `raise`.
3. **Given** a received goal FIX, **Then** `dispatch next` returns `fix` for `goal` only;
   after the fix round the delta asks for `goal` only and continues the same seat with the
   re-read feedback.
4. **Given** a docs-only diff that touches a spec or pre-registration (`specs/622-x/spec.md`,
   `docs/prereg.md`), **Then** the single role is `quality`.
5. **Given** a docs-only diff of 400 lines, **Then** it is still one gate.
6. **Given** a goal brief written for that item with `wuwei brief goal ...`, **Then** the brief
   uses the `sentinel-goal` charter.

### User Story 2 - Code and trust surfaces keep three gates (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a code diff (`src/app.py`) at the default floor, **Then** three gates as today.
2. **Given** a docs diff at the default floor with a lead flag, a FULL track, a trust path, a
   never-auto path, a binary file or an agent instruction file (`charters/lead.md`,
   `AGENTS.md`), **Then** three gates as today, with today's reasons. Under an owner floor
   of `light` these keep today's light tier (`quality` alone for a small agent instruction
   edit); they are never docs-only.
3. **Given** a docs-only diff and `repos.gates.floor = "full"`, **Then** three gates.
4. **Given** a docs-only diff under `pace careful`, **Then** standard with three gates.
5. **Given** an empty diff, **Then** light with `quality`, as today.

### User Story 3 - The measurement overrides the lead and says why (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the lead proposes `full` for a docs-only item, **Then** the record is tier
   `light`, roles one gate, and its reasons include `lead tier full overridden: docs-only`
   and `docs-only: 1 reviewer (goal)`.
2. **Given** the lead proposes `full` for a small code diff at floor light, **Then** the tier
   is `full` as today (`lead tier full`).

### User Story 4 - The report shows what the day cost (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a docs-only item with one goal seat and a code item with three gate seats,
   **Then** the report's `## Review seats` lists each with its seat count, gate set, tier and
   reasons, for example `- A: 1 reviewer seat (goal); tier light: docs-only: 1 reviewer (goal)`.
2. **Given** no tiered item, **Then** the report has no `## Review seats` section.

## Requirements

- **FR-001**: `dispatch.tier` classifies a measured diff as docs-only when it has at least
  one path, every path is a document (Clarifications), and nothing else raised the computed
  tier.
- **FR-002**: For a docs-only diff the size rule and a floor below `full` do not apply, and a
  lead tier above light is overridden with the reason `lead tier <t> overridden: docs-only`.
- **FR-003**: When the final tier of a docs-only diff is light, the recorded roles are
  `['quality']` for a spec or pre-registration and `['goal']` otherwise, with the reason
  `docs-only: 1 reviewer (<role>)`. Every other record keeps today's roles.
- **FR-004**: `dispatch.gate_set` accepts a recorded `['goal']`; any other set without
  `quality`, or with an unknown role, stays refused as damaged.
- **FR-005**: `wuwei brief goal <item> <name> --gate` writes a `sentinel-goal` gate brief.
- **FR-006**: The second round of a docs-only item is the existing light delta: the same seat,
  only the FIX roles.
- **FR-007**: The report lists reviewer seats per tiered item with the gate set, tier and
  reasons under `## Review seats`.
- **FR-008**: Invariant I34 in design 9.2 and `tests/test_invariants.py`: a docs-only diff
  never lowers review for a flagged, FULL-track, trust, never-auto, FULL-pattern, binary or
  agent-instruction path, or under a `full` floor: at a standard or full floor those keep
  arch, quality and security.
- **FR-009**: Docs and charters say the new rule: `charters/_common.md` (gate set),
  `charters/lead.md` (the tier is a hint for docs-only), `docs/site/concepts.md` (Review
  tiers), `docs/site/reference.md` (lead `tier`), `docs/site/configuration.md`
  (`light_max_lines`, `floor`), `README.md` (tiers line); agents regenerated.

## Success Criteria

- **SC-001**: A docs-only item at the shipped defaults costs one gate seat at the first round
  and no more than that seat continued at the second.
- **SC-002**: No item with code, a lead flag, a trust or never-auto path or an agent
  instruction file gets fewer gates than today.
- **SC-003**: The owner reads each item's gate seat count and tier reason in the day report.

## Assumptions

- A small code diff under an owner floor of `light` keeps `quality` alone, as today ("three
  gates as today" in the issue covers code at the default floor).
- Document detection is by path, not content. A repository that keeps code under `docs/` or
  `specs/` lists those paths in `repos.gates.trust_paths`, which raises them to standard.
- Agent instruction files are a trust surface even without the lead's `agent_surface` flag,
  so they are never documents here.
- The goal sentinel already exists (`charters/sentinel-goal.md`, `agents/sentinel-goal.md`,
  the launch guard's generic `sentinel-*` handling and `verdict.lint_file`'s role handling);
  at light depth its verdict needs no class-sweep line, the same as quality's.
- `pace careful` with a lead tier `full` on a docs-only diff ends at standard (the lead tier
  was overridden before the pace raised it). The pace is the owner's lever for more review.
- Design spec 5.3's depth table lists the light gate as `quality` and `goal when docs` at full.
  That conflicts with the owner's newer decision in this issue; the conflict is raised in the
  PR body for the owner to amend 5.3. This feature adds only the 9.2 invariant row, as the
  constitution requires for a changed decision rule.

## Deferred

- None.
