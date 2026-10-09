# Feature Specification: next passes --repo to worktree add on a multi-repository workspace, and approves the day's proposed goals

**Feature Branch**: `603-dispatch-repo-goals`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #603: fix(dispatch): next passes --repo to worktree add on a
multi-repository workspace, and asks for the day's goals before plan approve.

Binding principles: #530 (autonomous by default: under observe and guarded a guard is a
warning or a card, never a refusal, except the records floor; under strict refusals stay;
no new refusal below strict) and #551 (the CLI owns the path: what the planner does next is
a command `wuwei next` returns, never a paragraph a model interprets).

Real-day finding (owner, 2026-10-09, 0.23.0, autonomous, observe, a fresh workspace with two
configured repositories): two commands `wuwei next` returned on the way from the plan to the
first dispatch could not succeed.

## Root cause

Both defects were reproduced in a tmp fixture workspace with `bin/wuwei` from this worktree.

### Defect 1: dispatch emits `worktree add` without `--repo`

- `cli/wuwei/dispatch.py:408` (`_start`, lines 399-409) returns `wuwei worktree add {name}`
  for every planned item whose worktree is missing. `_start` never reads the config, and
  nothing it reads knows the item's repository: the lead's candidate (validated in
  `cli/wuwei/plan.py:74-103`, `_proposal`) has `paths` but no repository field.
- `cli/wuwei/commands/worktree.py:44-45` (`add`) raises `several repositories configured;
  pass --repo <name>` when more than one repository is configured and `--repo` is absent;
  the command exits 2. Reproduced: two `[[repos]]`, a planned item `A`, `dispatch._start`
  returned `['wuwei worktree add A', 'wuwei brief builder A ...']` and `bin/wuwei worktree add
  A` exited 2 with that line.
- The lead is never asked for the repository: `LEAD_BODY` (`cli/wuwei/commands/next.py:70-76`)
  and `charters/lead.md` step 4 name `paths` and `owner_actions`, not a repository.
- Sibling texts name `bin/wuwei worktree add <item>` or `{item}` without `--repo` and so
  exit 2 in the same workspace: `dispatch.py:119` and `:543`, `docs.py:51`,
  `workspace.py:845`, `commands/build.py:132`, `brief.py:350`, `pr_actions.py:268`,
  `fast_checks.py:66`. `pr_actions.py` already passes `--repo` for its own adopt command.

### Defect 2: `plan approve` needs goals that `next` records only afterwards

- `plan.propose` (`cli/wuwei/plan.py:163-168`, `:249-250`) validates the lead's proposed goal
  blocks and writes them to `.wuwei/days/<date>/goals.md`; `memory/goals.md` stays untouched
  (by design: `tests/test_plan.py:248`).
- `plan.gate_widget` (`plan.py:264-265`, `:283-291`) shows those draft goals on the card and
  returns the record command `wuwei plan approve --items ... --goals-confirmed`.
- `plan.approve` (`plan.py:307-309`) validates the proposal against `memory/goals.md` only;
  `goals.parse` raises `goals line 1: no goals` (`cli/wuwei/goals.py:58-59`) because memory
  has no goal heading. Reproduced in a fixture with the empty goals template.
- `next.step` (`cli/wuwei/commands/next.py:195-201`) returns the `goals` row (`wuwei goals edit
  --file <day>/goals.md`) only after `gate_approved`, so the path `next` returns runs approve
  first. `tests/test_plan.py:280` (`test_approve_needs_recorded_goals`) pins the defect.

## Design decision for defect 2

The item allows two fixes; neither holds up, and a third is shorter:

- Return the goals edit before the gate: before the gate card is asked, `protect_state`
  refuses the planner's `goals edit` (the allowance needs the answered `Goals` gate question,
  `cli/wuwei/guards/protect_state.py:268-271`), and it would record goals the owner has not
  confirmed (design 5.7: the gate shows them, then the planner records them). Returning it
  between the card and approve would ask the owner the card again: a new prompt.
- Let `plan approve` write `memory/goals.md`: `plan approve` is not an owner action, so the
  planner would write owner memory under strict, where `goals edit` stays the owner's
  (`protect_state.py:72`, `:286`). That weakens strict.
- Chosen: `plan approve` validates against the day's `goals.md` while `memory/goals.md` has
  no goal heading. Those are the exact blocks the gate card showed and the owner confirmed
  (`--goals-confirmed`). Memory stays written only by `goals edit`, which `next` already
  returns right after approve. About three lines, no prompt, no refusal, strict unchanged.

## User Scenarios and Testing

### User Story 1: The first dispatch on a multi-repository workspace starts (Priority: P1)

The planner follows `wuwei next` on a workspace with two configured repositories; the
dispatch set's start commands create each item's worktree in its own repository.

**Independent Test**: `dispatch.launch_set` and `wuwei worktree add` in a two-repository
fixture with the VCS port faked; the walking day of `tests/test_path_day.py` with a second
repository.

**Acceptance Scenarios**:

1. **Given** two configured repositories and a proposal whose candidates carry `repo`,
   **When** `wuwei next` and `wuwei dispatch next --all` return the launch set, **Then** every
   `wuwei worktree add` command names `--repo <that name>` and runs to exit 0 in the fixture.
2. **Given** one configured repository, **When** the launch set is returned, **Then** the
   command is unchanged: `wuwei worktree add <item>` with no `--repo`.
3. **Given** two configured repositories and a candidate without `repo` whose `paths` exist
   in exactly one repository's checkout, **When** the plan is proposed, **Then**
   `proposal.json` records that repository as the candidate's `repo` and the start command
   names it.
4. **Given** two configured repositories and a candidate without `repo` whose `paths` exist
   in none or several repositories, **When** the plan is proposed, **Then** `wuwei plan
   propose` exits 0 and the plan names the missing field under that candidate with the
   configured names to choose from; **When** that item is due to start without a worktree,
   **Then** the start entry is `wuwei plan park <item> --reason <why>`, which exits 0, never
   a `worktree add` that exits 2.
5. **Given** two configured repositories and an item whose worktree already exists,
   **When** the launch set is returned, **Then** the start entry is the builder brief only,
   as today, whatever the item's repository.
6. **Given** two configured repositories and today's proposal naming `repo` for item X,
   **When** `wuwei worktree add X` runs without `--repo` (a remediation line names it so),
   **Then** it uses that repository and exits 0; with no repository known it exits 2 as
   today, naming the configured repositories.

### User Story 2: A fresh day's proposed goals reach an approved plan (Priority: P1)

On a fresh workspace with no goals in memory, the lead proposes goal blocks; the planner
follows `wuwei next` and the owner's Approve on the gate card approves the plan.

**Independent Test**: `plan.approve` over the empty goals template with a proposed draft;
the walking day with the empty template.

**Acceptance Scenarios**:

1. **Given** a fresh day with a lead proposal carrying goal blocks and no goals in memory,
   **When** the planner follows the commands `wuwei next` returns, in order, **Then** it
   reaches an approved plan without a `no goals` error, and the next row after approval is
   `wuwei goals edit --file .wuwei/days/<date>/goals.md`, which records them in memory.
2. **Given** the same day, **When** `wuwei plan approve --items A --goals-confirmed` runs,
   **Then** it approves against the day's `goals.md`, records the goal ids in state, and
   leaves `memory/goals.md` unchanged.
3. **Given** goals in memory, **When** approve runs, **Then** it validates against memory as
   today (the day's `goals.md` exists only for provisional goals and is not read).
4. **Given** no goals in memory and no day `goals.md`, **When** approve runs, **Then** it
   fails as today with `no goals`.

### Edge Cases

- A candidate's `repo` that names no configured repository is treated as missing: derived
  from `paths`, else named by the plan lint.
- `paths` is optional; a candidate without `paths` and without `repo` is unresolved.
- Under strict, approve passes on the gate-confirmed draft; the `goals` row then shows the
  owner the host-terminal command as today (`THEN['goals']`).
- An item imported from yesterday or admitted with `plan add` has no row in today's proposal;
  with its worktree present it starts as today; without one in a multi-repository workspace
  it is parked with the reason (see Deferred).

## Requirements

### Functional Requirements

- **FR-001**: When more than one repository is configured, `dispatch._start` MUST emit
  `wuwei worktree add <item> --repo <name>` with the candidate's `repo` from today's
  `proposal.json`.
- **FR-002**: When one repository is configured, `_start` output MUST be unchanged.
- **FR-003**: `plan.propose` MUST, when more than one repository is configured, keep a
  candidate's `repo` that names a configured repository, else derive it as the one configured
  repository whose checkout contains at least one of the candidate's `paths` (existence only,
  never read), and write the result into the candidate in `proposal.json`.
- **FR-004**: When the repository stays unresolved, `plan.propose` MUST still write the plan
  and exit 0, and the plan MUST name the missing field under the candidate with the
  configured names (the lint); it MUST NOT refuse.
- **FR-005**: In a multi-repository workspace the plan MUST show each candidate's repository
  (`Repository: <name>`) so the owner sees it at the gate.
- **FR-006**: An unresolved item with no worktree MUST start as `wuwei plan park <item>
  --reason <why>`; no command `next` returns for a planned item exits 2.
- **FR-007**: `wuwei worktree add <item>` without `--repo` in a multi-repository workspace
  MUST use the item's `repo` from today's proposal when there is one; otherwise it exits 2
  as today, naming the configured repositories.
- **FR-008**: `LEAD_BODY` and `charters/lead.md` step 4 MUST ask for `repo` (the configured
  repository name) on each candidate when more than one repository is configured.
- **FR-009**: `plan.approve` MUST validate the proposal against the day's `goals.md` when
  `memory/goals.md` has no goal heading and that file exists; otherwise against memory as
  today. Approve MUST NOT write `memory/goals.md`.
- **FR-010**: The order of `next` rows MUST stay: gate, then goals, then calibrate.
- **FR-011**: Design 9.2 and `tests/test_invariants.py` MUST carry two new rows: every
  command `next` returns to start a planned item exits 0 in a multi-repository fixture; and a
  fresh day's gate-confirmed proposed goals approve the plan while memory has none, approve
  never writing owner memory.

### Key Entities

- **Candidate `repo`**: optional string on a lead candidate and on its `proposal.json` row; a
  configured `[[repos]] name`. Read by `dispatch._start` and `worktree add`.
- **Day `goals.md`**: the provisional goal blocks `plan propose` writes while memory has none;
  now also read by `plan approve`.

## Success Criteria

- **SC-001**: In a two-repository fixture, every command the launch set returns for a planned
  item exits 0 (scenario 1.1, invariant row).
- **SC-002**: In a fresh-day fixture with the empty goals template, the walk from `wuwei
  next` reaches `gate_approved` with no command exiting 2 and then records the goals in
  memory with the next row.
- **SC-003**: One-repository output is identical to today's; existing tests pass unchanged
  except `test_approve_needs_recorded_goals`, which pinned defect 2.

## Assumptions

- Derivation by existence: "paths fall under a repository" means the repository-relative
  path exists in that repository's configured checkout. A new file exists nowhere, so such a
  candidate needs `repo` from the lead; the lint says so.
- The lint is a plan line, as #518 does for owner actions the CLI does not understand: a
  card-free fix the lead makes when the planner proposes again (the gate's Change something
  path), never a refusal before the gate.
- For an item that still has no repository at start, parking it with a reason is the one
  exact command that exits 0 and lets the day close; a refused or waiting entry would hold
  the close. The park is a two-way seat record (`plan.dispose`), no card.
- `plan approve` reading the day's `goals.md` adds no trust: `gate_widget` already reads the
  same file to show the owner the goals, and `goals edit --file` records the same file.
- `.specify/feature.json` written by the feature script is local tooling state.
- The design spec text of 5.7 stays as is (the planner records the approved blocks with
  `goals edit --file`); only 9.2 gains rows.
- New invariant ids are the next free ones at writing (I26, I27); if #599, #600 or #601 land
  rows first, renumber on rebase.

## Deferred

- `plan add` and imported items carry no `repo`; in a multi-repository workspace without a
  worktree they are parked at start. A follow-up issue adds `--repo` to `plan add` (and a
  `repo` copy on import). To be filed; not in this item.
- `plan template` could print `repo` on its candidate in a multi-repository workspace.
