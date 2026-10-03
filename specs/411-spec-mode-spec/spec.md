# Feature Specification: Specification mode, a configured spec engine (spec-kit by default) whose steps the hooks enforce on every non-trivial item, with superpowers and OpenSpec as alternatives

**Feature Branch**: `411-spec-mode-spec`
**Created**: 2026-10-03
**Status**: Ready for implementation (spec-only: the amendment text is in plan.md)
**Input**: Issue #411, spec(spec mode). Owner request 2026-10-03: a configured spec engine,
spec-kit by default, every step (analyze and validate included) run strictly by default,
superpowers and OpenSpec as alternatives, trivial changes may skip the spec. References:
#280 risk tiers, #237 (design 4.5 and 9.1), #343 setup, #342 doctor, #279 interview, #358
orientation, `AGENTS.md` and `.specify/` (WUWEI's own use of spec-kit).

## Root cause (read on main, e0c32d1)

This is a spec gap, not a runtime failure; the orchestrator notes name no dry-run
workspace, so there is nothing to reproduce. Nothing in the design or the code says how a
seat specifies an item in the owner's repositories, and nothing checks it.

- `docs/specs/2026-09-24-wuwei-design.md:424-426` (5.3 Tracks): "spec and implementation in
  one builder session" with no engine, no steps and no artifact. 5.1 (line 388) gives the
  builder "spec and implementation in the item's worktree" and stops there.
- `docs/specs/2026-09-24-wuwei-design.md:165-183` (4.1 hook table): the only Write or Edit
  rule protects `state.json` and `events.jsonl`. A source edit in an item worktree is never
  checked against anything.
- `charters/builder.md:10-12`: the builder states the promise "in the item's spec" and works
  test first, but which spec format, which steps and in which order is left to the seat.
- `cli/wuwei/workspace.py:45-172` (`SCHEMA`): no `spec` table, so no engine or mode can be
  configured.
- `cli/wuwei/commands/build.py:343-365` (`complete_checks`): the build loop moves an item from
  implement to gate on green fast checks alone; `cli/wuwei/dispatch.py:159-180`
  (`next_step`) dispatches gates without reading any spec artifact.
- `cli/wuwei/brief.py:226-290` (`write`): the builder and gate briefs carry no spec step
  table and no artifact paths.
- What already exists and is reused: the lead tier `items.<item>.tier` and the diff tier
  `dispatch.tier` (#280, `cli/wuwei/dispatch.py:40-104`); item worktrees and their anchor
  (`wuwei worktree add`, `workspace.worktree_workspace`); owner actions refused from agent
  tools (`cli/wuwei/guards/protect_state.py:45-66`); `calibrate` already reads
  `.specify/memory/constitution.md` (`cli/wuwei/calibrate.py:24`).
- The issue's own section references are off by one: 5.9 already exists (Cockpit, signals
  and briefings, line 719), 4.5 is matching and bypass resistance (the hook table is 4.1),
  and the design spec has no configuration appendix (each section states its own keys, as
  5.8.1 does for `[decisions.cruise]`).

## Clarifications

### Session 2026-10-03

- No question was put to the owner (AGENTS.md); every open point is resolved by the
  recommendation and recorded under Assumptions.

## User Scenarios & Testing

### User Story 1 - One statement of specification mode (Priority: P1)

The owner, the builder of the implementation issue, or a reviewer reads design 5.10 and
finds the config keys with defaults, the three engines' step tables with each step's
artifact and command, the enforcement point for each hook event, and the skip rule by tier
with the per-item override, each stated once.

**Independent Test**: the phrase check in plan.md "Verification commands" fails on a
`git archive main` export and passes on the worktree.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given the amended design spec, then 5.10 defines `[spec]` with
   `engine` (default `speckit`; `superpowers`, `openspec`, `none`), `mode` (default
   `strict`; `advisory`, `off`) and `skip_tiers` (default `["light"]`).
2. Given 5.10, then the spec-kit table lists `specify`, `clarify`, `plan`, `tasks`,
   `analyze`, `checklist` and `implement` in that order, each with its artifact, followed by
   WUWEI's validation (fast checks and gates), and says every step runs under strict.
3. Given 5.10, then the superpowers table lists `brainstorming`, `writing-plans`,
   `executing-plans` with `test-driven-development`, and `verification-before-completion`;
   the OpenSpec table lists `proposal`, `specs` and `design`, `tasks`, `validate`, `apply`
   and `archive`; `none` is the behaviour before this section.
4. Given 5.10, then the enforcement points are stated per event: PreToolUse on Write, Edit,
   MultiEdit and NotebookEdit in an item worktree; PostToolUse recording `spec.step`; the
   build loop's move to the gates with `dispatch next` refusing a gap; SubagentStop on a
   builder's last message; the builder and gate briefs. `advisory` warns once per item and
   day; `off` checks nothing.
5. Given 5.10, then the skip rule is stated: a lead tier in `skip_tiers`, or the owner's
   `wuwei plan set <item> spec=skipped --reason <why>`, skips; `spec=required` forces a
   spec; both are recorded; a skipped item passes every check with one `spec.skipped` event;
   a lead-tier skip is re-checked against the diff's computed tier at the move to the gates.
6. Given 4.1, then the hook table carries the PreToolUse and PostToolUse rows and the
   SubagentStop clause, each pointing to 5.10; 3.3 lists the spec engine among the
   `config.toml` contents.

### User Story 2 - WUWEI itself runs under spec-kit strict (Priority: P1)

**Independent Test**: same check.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given `.specify/memory/constitution.md`, then its Workflow section
   says WUWEI itself runs under `engine = "speckit"` and `mode = "strict"`, names the seven
   steps in order, and says how a trivial change may skip; the version and amendment date
   change.
2. Given `AGENTS.md`, then its spec-kit line lists the same steps, so the agent entry point
   and the constitution agree.

### User Story 3 - The implementation issue needs no further design decision (Priority: P1)

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given 5.10 and this feature's plan.md "Deferred" map, then the
   implementation issue can name its files, functions, config schema, state field, event
   kinds and refusal texts without a new design decision; what is left open is recorded
   below under Assumptions.

### User Story 4 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the diff, then only `docs/specs/2026-09-24-wuwei-design.md`,
   `.specify/memory/constitution.md`, `AGENTS.md` and `specs/411-spec-mode-spec/` changed,
   and `python -m pytest -q` passes, including `tests/test_docs.py`.

### Edge Cases

- An item whose repository lacks the engine's files: the PreToolUse refusal adds the
  engine's install line; doctor fails the repository's engine row. Setting `engine = "none"`
  ends both.
- Two directories match the item (`specs/001-eng-7` and `specs/002-eng-7`): the step is not
  done and the reason names both, so the seat removes one rather than the CLI guessing.
- A lead tiers an item `light` to dodge the spec: at the move to the gates the diff's
  computed tier (#280 `computed`, before the floor and the lead tier) decides; above
  `skip_tiers` the spec is required after all and the gap goes back to the builder.
- A builder on the Codex runtime fires no hooks: the build loop's check at the move to the
  gates runs in the CLI for every runtime, so Codex items are still held to the engine.
- An item that reached `gate` another way (a manual `wuwei state transition`): `dispatch
  next` refuses its gates, naming the step.
- The owner's own session editing in an item worktree is refused too under strict: the
  worktree belongs to the item. The owner skips with `plan set` or sets `mode`.
- `security.posture = "observe"` (first week, `setup --shadow`): `strict` runs as
  `advisory`, so a first day never stops on a missing spec.
- Edits under the engine's own directories (`specs/`, `.specify/`, `docs/superpowers/`,
  `openspec/`) always pass: the seat must be able to write the spec before the code.

## Requirements

- **FR-001**: New design section `### 5.10 Specification mode (owner, 2026-10-03, #411)`
  after 5.9, stating: the `[spec]` keys with defaults; the three engines' step tables with
  artifact and command per step; how a step counts as done (artifact present and reading as
  stated; the next step is the first not done); the skip rule, the owner action `wuwei plan
  set` and the re-check against the diff tier; the enforcement points by hook event and the
  build loop; `advisory` and `off`; the observe-posture rule; which records are CLI-only;
  engine presence for setup, doctor and the interview; the agent-facing and owner-facing
  surfaces.
- **FR-002**: 4.1 hook table: one PreToolUse row and one PostToolUse row for spec mode, and
  a clause in the SubagentStop row, each pointing to 5.10. 3.3: `config.toml` lists the
  spec engine.
- **FR-003**: Constitution Workflow: one bullet saying WUWEI itself runs under `speckit`
  strict with the step order and the skip rule; Version 1.2.0, Last Amended 2026-10-03.
- **FR-004**: `AGENTS.md`: the spec-kit line lists the full strict step order.
- **FR-005**: No runtime file, charter, agent, skill, template, docs site page or test
  changes; those are the implementation issue's (plan.md "Deferred").

## Success Criteria

- **SC-001**: The plan's phrase check fails on a `git archive main` export and passes on the
  worktree.
- **SC-002**: Each `[spec]` default and the interview question appear exactly once in the
  design spec.
- **SC-003**: `git status --short` lists only the four paths in User Story 4.
- **SC-004**: The amendment stays short: design spec net growth under 120 lines (a dry run
  of plan.md's text measured 111, most of it the three step tables).

## Assumptions

- Section number: the issue asks for "new section 5.9", but 5.9 is Cockpit, signals and
  briefings; the new section is 5.10. The issue's "one line in 4.5 hooks" goes in the 4.1
  hook table (4.5 is matching and bypass resistance), and its "configuration appendix" line
  goes in 3.3 (the design spec has no appendix; 5.10 states its keys like 5.8.1 does).
- Only the design spec, the constitution and `AGENTS.md` change here. `AGENTS.md` is not in
  the issue's list, but it is the agent entry point and lists four spec-kit steps; left
  alone it would contradict the amended constitution on the next feature.
- One engine per workspace. Per-repository engines are deferred until a workspace needs
  two; doctor still checks presence per repository.
- Tier values are lowercase (`light`, `standard`, `full`), as `repos.gates.floor`, the lead
  JSON and `dispatch.TIERS` already spell them; the issue's `["LIGHT"]` is `["light"]`.
- "The lead's tier decides" reads `items.<item>.tier` (optional, set by `wuwei plan
  approve` from the lead JSON). An item with no lead tier needs a spec. At the move to the
  gates a tier skip is re-checked against the diff's `computed` tier from `dispatch.tier`,
  before the repository floor and the lead tier: with the default floor `standard` the
  effective tier is never `light`, so comparing the effective tier would void `skip_tiers`.
- `plan set` is an owner action refused from agent tools (added to `protect_state`'s owner
  table), like `config set` and `decision outcome`: a seat must not lower its own spec
  requirement. `--reason` is required for `skipped` and optional for `required`. The value
  and reason live in `items.<item>.spec`, written only by `plan set`.
- Item to artifact: by the item id lowercased, the same rule `wuwei worktree add` uses for
  the branch. spec-kit: the one directory under `specs/` named `<item>` or ending in
  `-<item>` (the brief tells the builder to run `create-new-feature.sh --short-name
  <item>`); OpenSpec: the change id is the item; superpowers: the item is the topic and
  feature name in the dated file names.
- spec-kit's `analyze` writes no file, so the builder saves its report as `analysis.md` in
  the feature directory. Blocking under strict: a finding of severity CRITICAL or HIGH
  (spec-kit itself only asks CRITICAL to be resolved before implement; strict is the
  owner's word). `clarify` is done when `spec.md` has a `## Clarifications` section; the
  seat answers its questions with its recommendation (5.2 mandate, 5.3 assume and record),
  and one-way doors become decision records as before.
- `checklist` "where the engine offers it": only spec-kit offers it. `specify` already
  writes `checklists/requirements.md`, so the step is done when every checklist item in
  `checklists/` is checked.
- The issue's OpenSpec list has no analyze equivalent; `openspec validate <item> --strict`
  is that step (the owner's "validate"), saved as `validation.json` with `--json`. `archive`
  runs in the item's branch before the gates, so the gates review the specs as they will
  merge; afterwards the change is found under `openspec/changes/archive/`.
- superpowers has no pre-implementation analysis; its plan's checkboxes are the gate check,
  and `verification-before-completion` is satisfied by the fast checks and the gates, which
  every engine ends with.
- Order: a step is done when its artifact is present and reads as stated, and the next step
  is the first not done. Artifact times are not compared, because re-running `plan` after
  `tasks` is normal iteration; "out of order" therefore shows as an earlier step not done.
- The move to the gates is enforced in the build loop (`complete_checks`, implement to gate
  and fix to delta), with the gap fed back to the same builder as a failing check named
  `spec`. Refusing only in `dispatch next`, as the issue words it, would strand the item at
  `gate` (gate cannot return to implement); `dispatch next` keeps the refusal as the
  backstop for an item that reached `gate` another way.
- The PreToolUse check applies to every session in an item worktree (the worktree belongs
  to the item), and only to Write, Edit, MultiEdit and NotebookEdit (the file matcher the
  other file guards use; the issue names the first three). A Bash write to a source file is
  not parsed for this (cooperative mistake prevention, 9.1); the build loop's check at the
  gates catches the result.
- The spec checks are not a 9.1 posture area; `spec.mode` is their only setting, and the
  `observe` posture runs `strict` as `advisory`, keeping observe's promise that nothing
  outside records and owner-only actions blocks.
- Defaults follow the owner: `speckit` and `strict`. A workspace upgraded without a `[spec]`
  table therefore runs them; doctor fails the engine row until the engine is installed or
  `spec.engine` is set. Setup asks the interview question with the detected default (spec-kit
  when none is found), so a first day meets the choice at setup, not at the first refused
  edit.
- Superpowers presence is read from Claude Code's installed plugins file, the path
  `scanner.mcp.plugins_file` already configures; no new config key.
- The design names no install command; the lines the doctor row prints are in plan.md
  "Deferred" for the implementation issue.
- The design spec never lists the #280 tier names; they live in `dispatch.TIERS`
  (`light`, `standard`, `full`). 5.10 cites #280 and the default `["light"]`; the
  implementation issue documents the names on the configuration page with `[spec]`.
