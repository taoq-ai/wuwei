# Feature Specification: Specification mode, `[spec]` engine and mode, hooks that enforce the engine's steps per item, trivial tiers skipped, setup and doctor detect the engine

**Feature Branch**: `412-spec-mode`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #412, feat(spec). Implements design 5.10 (amended by #411, on `main` at
ed77b30). Owner request 2026-10-03: a configured spec engine, spec-kit by default, every
step (analyze and validate included) enforced strictly by the hooks by default, superpowers
and OpenSpec as alternatives, trivial changes may skip the spec. References: #280 tiers,
#240 event-to-module imports, #346 latency, #302 mandate block in briefs, #358 orientation,
#343 setup, #342 doctor, #279 interview, `scripts/headless_e2e.py`.

## Root cause (read on main, ed77b30)

A feature gap, not a runtime failure; the orchestrator notes name no dry-run workspace, so
nothing is reproduced. Design 5.10 (`docs/specs/2026-09-24-wuwei-design.md:772-879`) and
the 4.1 hook rows (lines 165-185) state the behaviour; no code implements it:

- `cli/wuwei/workspace.py:45-172` (`SCHEMA`): no `spec` table, so `engine`, `mode` and
  `skip_tiers` cannot be configured or checked by `config check`.
- `cli/wuwei/guards/__init__.py:18-31` (`MODULES`) and `:37-42` (`AREAS`): no guard reads
  a spec artifact on PreToolUse, PostToolUse or SubagentStop. A Write or Edit of a source
  file in an item worktree passes with no spec.
- `cli/wuwei/commands/build.py:321-366` (`complete_checks`): lines 363-365 move an item
  from implement to gate (fix to delta) on green fast checks alone.
- `cli/wuwei/dispatch.py:148-180` (`next_step`): dispatches the gates of an item at `gate`
  without reading any artifact.
- `cli/wuwei/brief.py:188-277` (`write`): the builder and gate briefs carry no step table and
  no artifact paths.
- `cli/wuwei/commands/plan.py:11-32`: no `plan set`, so the owner cannot skip or require
  the spec for one item; `cli/wuwei/state.py:264-277` (`_producer_error`) names no producer
  for `items.<item>.spec`; `cli/wuwei/guards/protect_state.py:45-68` (`_OWNER_ACTIONS`) has
  no `('plan', 'set')`.
- `cli/wuwei/commands/doctor.py:261-298` (per-repository rows),
  `cli/wuwei/commands/setup.py:287-289` (interview call) and `cli/wuwei/interview.py:80`
  (`QUESTIONS`): no engine detection, no doctor row, no interview question.
- `cli/wuwei/commands/next.py:117-145` (`orientation`): no engine or mode line.
- Reused, not re-implemented: the lead tier `items.<item>.tier` and the diff tier
  `dispatch.tier(...)['computed']` (#280, `cli/wuwei/dispatch.py:40-104`); the recorded
  `items.<item>.worktree` (`cli/wuwei/brief.py:322-325`); the seat resolver
  `guards.agent_launch.stopping_seat` (`cli/wuwei/guards/agent_launch.py:197-223`); the
  build loop's failing-check feedback, signature and stuck rule (`build.py:343-361`); the
  owner-action table; `scanner.mcp.plugins_file`; the posture resolver `workspace.posture`.

## Clarifications

### Session 2026-10-03

- No question was put to the owner (AGENTS.md). Each open point was answered with the
  recommendation and recorded under Assumptions: helper module name, where advisory
  warnings show, how the fixture days carry the two items, how existing tests meet the new
  strict default, the analyze and validate artifact formats, and whether `plan set` asks a
  yes or no confirmation.

## User Scenarios & Testing

### User Story 1 - Strict spec-kit keeps a non-trivial item's steps in order (Priority: P1)

A builder seat in an item worktree tries to edit source before the spec exists. The hook
refuses and names the next step and its command. As the seat writes each artifact, the
hook records one event per step. Once every step before implementation is done, edits
pass; the build loop moves the item to the gates only when implementation is done too.

**Independent Test**: `tests/test_spec_mode.py` with a temporary workspace, a recorded item
worktree and hook payloads through `wuwei.commands.hook.run`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given `engine = "speckit"`, `mode = "strict"` and a STANDARD item
   (no lead tier, or `standard`) whose worktree has no `specs/<n>-<item>/spec.md`, when an
   Edit of a source file in that worktree runs, then PreToolUse refuses with a reason
   containing `specify first: /speckit.specify`.
2. Given the same item, when `spec.md` (with `## Clarifications`), `plan.md`, `tasks.md`,
   `analysis.md` with no CRITICAL or HIGH row and `checklists/requirements.md` all checked
   are written through Write calls, then each write produced exactly one `spec.step`
   event (item, engine, step, path) and the next source Edit passes.
3. Given `plan.md` is missing while `tasks.md` exists, when a source Edit runs, then it is
   refused with `plan first: /speckit.plan` (the next step is the first one not done).
4. Given `analysis.md` has a table row with severity HIGH, then a source Edit is refused
   with `analyze first` and the reason names `analysis.md`.
5. Given an Edit under `specs/` or `.specify/` in the worktree, then it always passes.
6. Given every step before implementation is done but `tasks.md` has an unchecked task,
   when `wuwei build check` finds green fast checks, then the item stays at `implement`
   and the builder gets a failing check named `spec` naming `implement`; repeated, the
   stuck rule parks it like any repeated failure.
7. Given an item at `gate` reached by `wuwei state transition` with a gap, when `wuwei
   dispatch next <item>` runs, then it exits 1 naming the step.
8. Given a builder seat whose last message does not name its feature directory, when
   SubagentStop runs, then it is refused naming the directory; with `stop_hook_active`
   it passes.
9. Given `.specify/` absent from the repository, then the PreToolUse reason also carries
   the spec-kit install line.

### User Story 2 - Trivial items skip, the owner overrides (Priority: P1)

**Independent Test**: same file; `plan set` through `wuwei.__main__.main`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given an item whose lead tier is `light` and `skip_tiers =
   ["light"]`, when source Edits run in its worktree, then they pass, no step is checked
   and exactly one `spec.skipped` event (item, reason `lead tier light`) is recorded for
   the day, however many calls follow.
2. Given `wuwei plan set <item> spec=required` on that item, then the checks run for it.
3. Given `wuwei plan set <item> spec=skipped --reason "typo fix"`, then a STANDARD item is
   skipped with reason `owner: typo fix`; `items.<item>.spec` holds the value and the
   reason; one `spec.override` event is recorded.
4. Given `plan set <item> spec=skipped` with no `--reason`, then it exits 2 and writes
   nothing; given an item not in today's plan, it exits 1.
5. Given `wuwei plan set` run from an agent tool, then protect_state refuses it as an
   owner action; `wuwei state set items.A.spec ...` and `wuwei event spec.override ...`
   are refused as reserved, naming `wuwei plan set` as the producer.
6. Given a `light` lead tier whose diff computes `standard` (#280 `computed`, before the
   floor and the lead tier), when the build loop moves the item to the gates, then the
   spec is required after all and the gap goes back to the builder.

### User Story 3 - Advisory and off (Priority: P1)

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given `mode = "advisory"`, then the situations of User Story 1
   never refuse (PreToolUse, build loop, dispatch next, SubagentStop) and the first gap per
   item and day records one `spec.warned` event (item, engine, step, where).
2. Given `security.posture = "observe"` and `mode = "strict"`, then the checks behave as
   advisory.
3. Given `mode = "off"` or `engine = "none"`, then nothing is checked and no `spec.*`
   event is written.
4. Given the day report with `spec.warned` events, then it lists them under
   `## Spec warnings`.

### User Story 4 - The other engines (Priority: P2)

**Acceptance Scenarios**:

1. (Issue acceptance 4) Given `engine = "superpowers"`, then `brainstorming`
   (`docs/superpowers/specs/<date>-<item>-design.md`), `writing-plans`
   (`docs/superpowers/plans/<date>-<item>.md`) and `executing-plans` (every step in that
   plan checked) are enforced, and edits under `docs/superpowers/` always pass.
2. Given `engine = "openspec"`, then `proposal`, `specs` (at least one
   `specs/<capability>/spec.md`), `tasks`, `validate` (`validation.json`, every item
   valid), `apply` (every task checked) and `archive` (the change found under
   `openspec/changes/archive/` ending in `-<item>`) are enforced, and edits under
   `openspec/` always pass.
3. One fixture per engine (`tests/fixtures/spec/<engine>/`) holds a complete artifact set;
   removing any one artifact makes its step the next one.

### User Story 5 - Setup, doctor, interview, orientation, briefs (Priority: P2)

**Acceptance Scenarios**:

1. (Issue acceptance 5) Given a repository without `.specify/` and `engine = "speckit"`,
   then `wuwei doctor` has a `<repo> spec` row with status fail whose fix is the spec-kit
   install line; with `.specify/` present the row is ok; `engine = "none"` is ok.
2. Given setup on repositories where `openspec/` is found and `.specify/` is not, then the
   interview question "Which spec engine do your repositories use?" lists OpenSpec first;
   with nothing found, spec-kit first.
3. Given `config check` on `[spec] engine = "kiro"` or `skip_tiers = ["tiny"]`, then it
   reports the key as invalid.
4. Given a SessionStart in a workspace, then the orientation block carries one line
   `Spec: speckit strict` (engine and effective mode).
5. Given a builder brief for a STANDARD item, then it has one `Spec:` header line naming
   the engine, the effective mode, the item's artifact location and each step with its
   command; for a skipped item, `Spec: skipped (<reason>)`; a gate brief's `Spec:` line
   names the artifact paths.

### User Story 6 - Latency and the fixture days (Priority: P1)

**Acceptance Scenarios**:

1. (Issue acceptance 6) Given the hooks outside an item worktree (the bash PreToolUse
   fixture, a Write in the workspace root, a PostToolUse Bash), then `wuwei.specmode` is
   not in `sys.modules` and the existing #346 import tests pass unchanged.
2. (Issue acceptance 7) Given the scripted fixture day (`tests/fakes/day.py`), then item A,
   STANDARD under spec-kit strict, completes plan to merge with its artifacts written
   through the hooks (one refused source Write before the spec, one `spec.step` event per
   artifact), and a LIGHT item records `spec.skipped` and is never checked.
3. Given `scripts/headless_e2e.py`, then its verification-only item A carries `tier:
   light` and the validator requires one `spec.skipped` event for A.

### Edge Cases

- Two directories match the item (`specs/001-a`, `specs/002-a`): the step is not done and
  the reason names both.
- An unreadable artifact (bad UTF-8, `validation.json` not JSON or not the expected shape)
  is not done; the reason names the file.
- Item id case: `ENG-7` is found as `specs/eng-7` or `specs/*-eng-7`, the branch rule of
  `wuwei worktree add`.
- No item records a worktree containing the path (the workspace root, another repository,
  an unbriefed item): the guard returns clean before importing `wuwei.specmode`.
- Today's `state.json` unreadable: the PreToolUse check exits 2 with the state reason (fail
  closed); PostToolUse reports exit 2 but cannot undo the call.
- Codex builders fire no hooks: the build-loop check in `complete_checks` holds them.
- An unreadable `scanner.mcp.plugins_file` makes the superpowers doctor row unmeasured,
  never ok.

## Requirements

- **FR-001**: `workspace.SCHEMA['spec']` with `engine` (`speckit` default; `superpowers`,
  `openspec`, `none`), `mode` (`strict` default; `advisory`, `off`) and `skip_tiers`
  (default `["light"]`, items in `light`, `standard`, `full`); `CONFIG_CACHE_VERSION`
  bumped; the template has a commented `[spec]` section.
- **FR-002**: One helper module `cli/wuwei/specmode.py` holds the three step tables as
  data, the artifact rules, item location, the next-gap function, the skip rule (override,
  then lead tier, then the diff re-check), the effective mode, the once-per-day event
  writer, engine presence and install lines. Every caller below uses it; none restates a
  rule.
- **FR-003**: One guard module `cli/wuwei/guards/spec.py` with PreToolUse
  `Write|Edit|MultiEdit|NotebookEdit`, PostToolUse `Write|Edit|MultiEdit|NotebookEdit|Bash`
  and SubagentStop checks; registered in `guards.MODULES` and `guards.AREAS['spec'] = None`.
  Its top level imports only `wuwei.guards` and `wuwei.exits`; it imports
  `wuwei.specmode` only after it has matched the path to an item's recorded worktree.
- **FR-004**: `complete_checks` adds a failing check `spec` on a gap (strict) before the
  move to gate or delta; `dispatch.next_step` refuses the gates of an item at `gate` with
  a gap.
- **FR-005**: `wuwei plan set <item> spec=required|skipped [--reason <why>]` writes
  `items.<item>.spec = {"value", "reason"}` and one `spec.override` event; reason required
  for `skipped`; owner action in protect_state; `items.<item>.spec` and the four `spec.*`
  event kinds name their producers.
- **FR-006**: Briefs carry one `Spec:` header line (builder: steps and commands, or the
  skip; gates: artifact paths). Orientation carries `Spec: <engine> <mode>`. The report
  lists `spec.warned`.
- **FR-007**: Doctor adds one `<repo> spec` row per configured repository; setup detects the
  engine and passes it to the interview, whose new `spec` question sets `spec.engine`.
- **FR-008**: Charters (builder, lead, planner), the plan skill and the generated
  `agents/` carry the steps and the skip rule; docs: configuration.md `[spec]`,
  concepts.md glossary entries "Spec engine" and "Strict mode", daily.md one paragraph,
  agent.md one step-list line and one hook-refusal bullet.
- **FR-009**: The scripted fixture day and the headless e2e fixture cover a STANDARD item
  under strict and a LIGHT item skipped.

## Success Criteria

- **SC-001**: `python -m pytest -q` passes, every new test seen red before its code.
- **SC-002**: The #346 import and latency tests pass unchanged; a new test proves
  `wuwei.specmode` stays unloaded outside item worktrees.
- **SC-003**: Every rule of 5.10 is decided in `specmode.py` only: no step name, artifact
  name or tier rule is restated in build, dispatch, brief, guards, doctor or setup.

## Assumptions

- Module names: the helper is `cli/wuwei/specmode.py` (the issue's name; 411's map said
  `spec.py`), so it does not read as the guard; the guard is `cli/wuwei/guards/spec.py`
  and records as guard `spec`.
- "The guard loads only for item worktrees" (#346): `discover()` imports a module by
  event and tool (#240), so the small guard module loads on Write-family PreToolUse and on
  Write-family or Bash PostToolUse calls in a workspace, like every other guard. It reads
  today's state and returns before importing `wuwei.specmode` unless the path lies in an
  item's recorded worktree. Its top level adds no stdlib import, so the existing deny
  lists hold.
- The item worktree is the recorded `items.<item>.worktree` containing the path (5.10:
  "the item whose recorded worktree contains the path"), not the git anchor, so a
  worktree briefed as the repository itself (both fixture days) is covered. The deepest
  match wins.
- Design 5.10 wins over the issue where they differ: `skip_tiers` is lowercase
  `["light"]`; the override event is `spec.override`, not a decision record; the move to
  the gates is held in the build loop with `dispatch next` as the backstop; advisory warns
  once per item and day.
- `plan set` asks no yes or no confirmation (#354 confirms digests and decisions); the
  owner-action refusal from agent tools is the barrier, as for `plan carry` and `plan
  park`. `--reason` is optional for `required`; reasons are folded to one line.
- `analyze` blocks on a Markdown table row in `analysis.md` with a cell equal to
  `CRITICAL` or `HIGH` (case-insensitive), the spec-kit analyze report format; counts in
  prose ("CRITICAL issues: 0") do not block.
- `validation.json` is `openspec validate <item> --strict --json` output: an object whose
  `items` list is nonempty and every entry has `"valid": true`. Any other shape is
  unreadable, so not done.
- A checkbox step (`checklist`, `implement`, `executing-plans`, `apply`) is done when its
  files have at least one checked box (`- [x]` or `- [X]`) and no `- [ ]`.
- superpowers `verification-before-completion` has no artifact: it is always done in the
  table (the fast checks and the gates are the loop itself). OpenSpec `archive` comes
  after `apply`, so only the build-loop check requires it.
- The orientation block shows engine and effective mode only (no event read on the
  SessionStart path); the report lists the warned items. `wuwei next`'s one-line output is
  unchanged.
- PostToolUse records every done step whose `spec.step` is not yet recorded today, so an
  artifact written by Bash (a spec-kit script) is recorded on that call or the next one in
  the worktree.
- Fixture days: `scripts/headless_e2e.py` is an opt-in paid run whose item reaches the
  gates and parks, never merges; the offline scripted day (`tests/fakes/day.py`, collected
  by default) runs plan to merge, so it carries the STANDARD item under strict. The
  headless fixture's verification-only item becomes the LIGHT item (`tier: light`; its
  zero-line diff computes `light`, so the skip holds, and its gates stay three at the
  `standard` floor). A STANDARD item in the paid run is deferred: it needs the paid seat
  to run every spec-kit step.
- Existing tests that move an item to the gates without artifacts set `[spec] engine =
  "none"` in their workspace config; they test other behaviour, and the default stays
  `speckit` `strict`.
- Install lines (doctor fix and refusal), from 411's map: spec-kit `uvx --from
  git+https://github.com/github/spec-kit.git specify init --here --ai claude`; superpowers
  `/plugin marketplace add obra/superpowers-marketplace`, then `/plugin install
  superpowers@superpowers-marketplace`; OpenSpec `npm install -g @fission-ai/openspec`, then
  `openspec init`.
- Setup prefers spec-kit when several engines are found, then OpenSpec, then superpowers.
- The guard's state read and the event dedupe read are not one transaction; two hooks
  racing can write a duplicate `spec.step`. Harmless (a count, never a decision input);
  marked with a `ponytail:` comment.
