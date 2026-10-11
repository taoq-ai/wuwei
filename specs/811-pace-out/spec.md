# Feature Specification: delete pace; the tier alone sets the process depth

**Feature Branch**: `811-pace-out`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #811, part 8 of the #789 deletion pass: "chore(pace): delete pace; the tier alone sets the process depth".

## Context

Pace (#579) is one value per day (`careful`, `steady`, `fast`). The planner proposes it, the
owner picks it on the morning gate card and the planner may change it with
`wuwei plan set pace=<p>`. It feeds four places: the tier and depth `dispatch.tier` records,
the seat count `dispatch.launch_set` uses, the check list `fast_checks.commands` returns, and
the report, retro and steward card that compare paces. Each of those makes a model reason
about the process (which pace to advise, which label to answer, whether to change it
mid-day). The tier rule (diff, floor, docs-only, lead tier) and CAP (`calibrate.host`: owner
cap, host seats, memory, token budget) already exist and are deterministic in code. After
this change they are the only inputs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dispatch derives tier and seats without pace (Priority: P1)

The planner runs `wuwei dispatch next` or `wuwei next`. The item's tier and depth come from
the diff, the repository floor and the lead tier only. The launch set holds at most the CAP
`calibrate.host` derives. No day value changes either.

**Why this priority**: this is process control the owner keeps in code (pass plan, "Process
control kept": CAP and host seats; which gates). It must not move when pace goes.

**Independent Test**: write a stale `pace` value into the day state and compare the tier
record and the launch set with and without it.

**Acceptance Scenarios**:

1. **Given** a day state holding `pace: fast` and a plain standard diff, **When**
   `dispatch.tier` records the item, **Then** the record equals the one without the key:
   tier standard, no `depth` key, no reason that starts with `pace`.
2. **Given** a day state holding `pace: careful` and a host CAP of 4, **When** `launch_set`
   runs, **Then** the day state records `cap` 4 with the bound `calibrate.host` named.
3. **Given** a day state holding `pace: fast` and a load average over the core count,
   **When** `launch_set` runs, **Then** no launch becomes a `wait` because of load.
4. **Given** a gate record written before this change with `gates.depth = light` and
   `gates.tier = standard`, **When** `dispatch.depth` reads it, **Then** it returns standard.

---

### User Story 2 - The morning gate offers one approve option (Priority: P1)

The planner prints the gate with `wuwei plan gate`. The card has `Approve` and
`Change something`, and the record command is
`wuwei plan approve --items <ids> --goals-confirmed` with no `--pace`.

**Why this priority**: the gate is the owner's one daily decision; a pace row is a process
choice neither the owner nor the planner makes any more.

**Independent Test**: `plan.gate_widget` on a proposal, and `plan approve` through the CLI.

**Acceptance Scenarios**:

1. **Given** a proposed plan, **When** the gate widget is printed, **Then** the option labels
   are exactly `Approve` and `Change something` and the record has no `--pace`.
2. **Given** a proposed plan, **When** `plan.md` and `proposal.json` are written, **Then**
   `plan.md` has no `Pace:` line and `proposal.json` has no key that starts with `pace`.
3. **Given** an approved gate, **When** the day state is read, **Then** it has no `pace` key
   and the `plan.approved` payload has no `pace`, `recommended` or `wish`.
4. **Given** the CLI, **When** `wuwei plan approve ... --pace Approve` or
   `wuwei plan set pace=fast` runs, **Then** argparse refuses it (SystemExit 2) and nothing
   is written.

---

### User Story 3 - Checks are the configured fast checks (Priority: P2)

A builder's checks, `wuwei build check` and the push evidence guard read
`repos.<n>.fast_checks` only.

**Why this priority**: the push evidence guard is a kept process check (fast checks pass at
head before handoff). It must keep one input.

**Independent Test**: a repository with `fast_checks = []` and a stale day `pace: careful`
starts a build with no commands; a repository with `fast_checks = ["unit"]` needs evidence
for `unit` at HEAD whatever the day state holds.

**Acceptance Scenarios**:

1. **Given** `fast_checks = []` and a day state with `pace: careful`, **When**
   `build.next_action` starts the build, **Then** `commands` is `[]` and the
   `build.started` payload says `checks: none configured`.
2. **Given** a builder brief for a repository with no fast checks, **When** it is written,
   **Then** it carries the none-configured line and no `Checks:` line.
3. **Given** a repository with fast checks and no evidence at HEAD, **When** the push guard
   runs, **Then** it refuses as today, naming the check.

---

### User Story 4 - Nothing names pace (Priority: P2)

No module, command, config key, charter, skill or docs page refers to pace; the report and
retro have no `## Pace` section; the status line never shows a pace token.

**Independent Test**: `wuwei pace` is not a command; the report sections have no `## Pace`;
a whole-word grep for pace over the paths in SC-002 finds nothing.

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei pace` runs, **Then** argparse refuses it as an invalid
   choice (SystemExit 2).
2. **Given** a day, **When** the report and the retro are written, **Then** neither has a
   `## Pace` section and the DORA section follows `## Cycle time` in the report.
3. **Given** a day state with `pace: fast` left from before the upgrade, **When**
   `wuwei status --line` renders, **Then** no `pace` token appears.
4. **Given** a `config.toml` holding `[pace]` or a `repos` entry with `tests`, **When** it
   loads under the guarded posture, **Then** it loads with an unknown-key warning naming the
   key.

### Edge Cases

- A day started before the upgrade keeps `pace`, `pace_reasoning`, `pace_advice` and
  `pace_card` in `state.json` and `proposal.json`. Nothing reads them.
- The day's `events.jsonl` may hold `pace.set` or `pace.carded` rows. Their kinds leave
  `signal.SILENT`, so on the upgrade day they classify as a nudge (Assumption 5).
- An old gate record with `gates.depth` lighter than its tier now runs at its tier.
- A strict workspace whose config still holds `[pace]` or `repos.tests` fails to load until
  `init --upgrade` removes them (retired keys, plan.md) or pass part 2 makes unknown keys a
  warning under every posture.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `dispatch.tier` MUST derive the tier from the diff, the repository floor, the
  docs-only rule and the lead tier only, and MUST NOT write a `depth` key.
- **FR-002**: `dispatch.depth` MUST read the recorded tier, else the builder prediction (not
  for a gate reader), else standard; it MUST NOT read `gates.depth`.
- **FR-003**: `dispatch.launch_set` MUST take CAP and its bound from `calibrate.host`
  unchanged and MUST NOT hold launches on the load average.
- **FR-004**: `calibrate.host` MUST NOT read the load average and MUST NOT return `load`,
  `per_seat_tokens` or `used_tokens`; the token budget bound on CAP stays.
- **FR-005**: The morning gate card MUST offer `Approve` and `Change something` only; its
  record MUST NOT carry `--pace`; `plan approve` MUST NOT accept `--pace`.
- **FR-006**: `plan propose` MUST NOT advise a pace, write `pace*` keys to the proposal, write
  a `Pace:` line to `plan.md`, or write a pace card.
- **FR-007**: `plan set` MUST take `<item> <key>=<value>` only; `pace=<p>` is not a form and
  the guard keeps no planner allowance for it.
- **FR-008**: The checks a build runs and the push guard takes as evidence MUST be
  `repos.<n>.fast_checks` exactly.
- **FR-009**: `cli/wuwei/pace.py`, `cli/wuwei/commands/pace.py`, the config keys
  `pace.default` and `repos.tests`, the state keys `pace` and `pace_card`, the events
  `pace.set` and `pace.carded`, `metrics.by_pace`, the `pace` field of `metrics.cycles` rows
  and the report and retro `## Pace` sections MUST be gone.
- **FR-010**: No charter, skill, generated agent, docs page or design spec section MUST
  describe pace; the design spec 9.2 rows I15, I16 and I17 and their walk checks go.
- **FR-011**: The retired keys `pace` (table) and `repos.tests` MUST be listed for
  `init --upgrade` removal (`workspace.RETIRED` when the base has it, else plan.md "RETIRED
  at rebase").

### Key Entities

- **Tier record** (`items.<id>.gates`): `tier`, `computed`, `reasons`, `roles`, optional
  `second_opinion`; `depth` is no longer written.
- **Host limits** (`calibrate.host`): `cores`, the memory fields, `cap`, `seats`, `bound`,
  `text`.

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes; no test is loosened; only tests of deleted
  code are deleted.
- **SC-002**: A case-insensitive whole-word grep for `pace`, `paces` or `paced` over `cli/`,
  `charters/`, `skills/`, `agents/`, `hooks/`, `templates/`, `scripts/`, `.github/`,
  `docs/site/` and `docs/specs/2026-09-24-wuwei-design.md` returns nothing. The CHANGELOG and earlier `specs/` keep their history; tests
  may write a stale `pace` day key only to prove it is ignored.
- **SC-003**: The same diff and host give the same tier record and CAP whatever the day
  state holds.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. `repos.tests` is retired with pace. Its only readers were the pace check list and the
   pace advice; at steady, the only behaviour left, it never runs. CI runs the suite.
2. `budget.tokens_per_day` stays: it bounds CAP in `calibrate.host`, deterministically. Only
   the per-seat and used token figures returned for the pace advice go.
3. The load-average hold goes with the fast pace; CAP from cores, memory and budget is
   unchanged.
4. `dispatch.depth` stops reading `gates.depth`, since nothing writes it any more; an old
   lighter depth runs at its tier, the safer direction.
5. `pace.set` and `pace.carded` leave `signal.SILENT` so no module names pace; on the upgrade
   day an old row may show as a nudge (nudges go in pass part 4).
6. `test_candidate_paths_are_validated` stays: candidate `paths` still derive `repo` (#603).
7. The design spec edits (5.2 Pace paragraph, 5.6 per-pace bullet, 9.2 rows I15 to I17 and
   the I43 cross-reference) are part of the owner-approved #789 pass. If pass part 1 has
   already replaced the 9.2 table and the invariant walk, only the 5.2 and 5.6 edits remain.
8. `budget_classes.py` and concepts.md use "pace" as a plain word for a burn rate; both are
   reworded to "rate" so the SC-002 grep is clean (`budget_classes.py` itself goes in pass
   part 9).
9. The CHANGELOG keeps its #579 history.
