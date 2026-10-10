# Feature Specification: a CI-fix item's briefs list every step of the failing job, and its gate verdicts cite each

**Feature Branch**: `733-ci-fix-every-step`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #733 (owner, 2026-10-10, item 61): the builder and the first two gates
checked only the one failing step of a two-step CI job; the step behind it was also failing.
Deliver: when an item's scope is a CI fix (the item or finding names a workflow job), the
builder brief and the gate briefs list every step of that job with the command to run each
locally (read from the workflow file), and the verdict must cite the result of each; the goal
sentinel treats a missing step as a blocking gap.

## Root cause

Reproduced read-only, in process, with the repository's own parser and lint (no workspace
needed; the orchestrator named no dry-run workspace). A two-step job (`ruff check .`, then a
`run: |` block running `mypy`) and a PASS verdict that cites only the first step:

```text
calibrate._workflow(...)['jobs'] ->
  [{'id': 'lint', ..., 'runs': [('ruff check .', 9), ('|', 11)]}]
verdict.lint('Verdict: PASS\nHead: 3f1c2ab\nProbe: CI step 1 ruff check . exit 0\n...') ->
  (0, 'OK: PASS')
```

- GitHub stops a job at its first failing step, so the later steps of that job never ran in
  CI. The red check names only the job, and its log shows only the first failure. Fixing that
  step and rerunning only it leaves every later step unmeasured until the next CI run.
- `cli/wuwei/pr_actions.py:370` to `373` (`_fix`): the fix-round feedback is one line per red
  check, `<check name>: <conclusion> <url>`. It names the job, never its steps.
- `cli/wuwei/commands/build.py:225` (`open_fix`): that feedback reaches the builder once, in
  the launch prompt (or the body of a new fix brief). Nothing records on the item that it is a
  CI fix, so no later brief knows.
- `cli/wuwei/dispatch.py:13` and `:538`: every initial gate brief is written with the fixed
  body `GATE_BODY` ("Review {item} at its HEAD against its spec and acceptance criteria."). A
  gate brief can never name the job, let alone its steps. `dispatch.py:567` and `:790`: a
  delta round resumes the same gate seat with `_delta_feedback`, which names only the head
  range.
- `cli/wuwei/brief.py:376` to `587` (`write`): no brief reads a workflow file; the header,
  the body and the spec-mode block are all a brief carries.
- `cli/wuwei/verdict.py:140` (`lint`) and `:279` (`lint_file`): nothing ties a gate verdict to
  the steps of a job, so a verdict citing one of two steps is `OK: PASS`.
- `cli/wuwei/calibrate.py:201` (`_workflow`, the one workflow reader in the code base) records
  single-line `run:` commands only, with no step boundary or name, and records the block
  indicator `|` as a command (`calibrate.py:267`: the class `[^|>]` matches the space before
  `|`).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: How does WUWEI know an item is a CI fix? A: A text names a job of a workflow file in the
  item's worktree (`.github/workflows/*.yml|yaml`). A text names a job when it carries the
  fix-round check line `<job name>[ (<matrix>)]: <red conclusion>` (the form
  `pr_actions._fix` writes), or the words `job <name>` or `<name> job`, where `<name>` is the
  job's id or its `name:`. The texts read are the brief body and the item title (in
  `brief.write`) and the fix feedback (in `build.open_fix`).
- Q: Gate briefs have a fixed body; how do they learn the job? A: The jobs found are recorded
  on the item as `items.<item>.ci_jobs` (a sorted list of `<workflow path>#<job id>`), by
  `wuwei brief` and by the fix-round opener, each inside the state write it already makes.
  Every later builder or gate brief of the item lists the steps of every recorded job.
- Q: Which steps are listed? A: Every step of the job that has a `run:` command, in file
  order, numbered from 1 across the item's jobs, each with its job, its `name:` (or
  `unnamed`), its `file:line` and its full command (a block scalar keeps every line). A step
  with only `uses:` has no local command and is not listed.
- Q: What does a verdict write, and what does the lint refuse? A: One row per listed step,
  `CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>`. The lint refuses a verdict
  that has no row, or more than one row, for a listed step, and a `Verdict: PASS` carrying a
  `FAIL` row. `NOT RUN` is accepted (the seat could not run the step locally and says why);
  the goal sentinel judges it.
- Q: Where does the lint get the steps? A: From the item record and the worktree at lint
  time, the way `lint_file` already reads the docs value (#667): gate file name, seat, item,
  `ci_jobs`, the item's worktree, the workflow file. A delta seat resumed on an old brief is
  held to the same steps, and its continue prompt carries the same step block.
- Q: Does the light depth skip the rows? A: No. The rows are the point of a CI-fix item at
  any depth; the light shape stays Verdict, Head and findings plus these rows.
- Q: Does the builder's handoff get linted? A: No. The issue asks for the verdict to cite each
  step; the builder brief lists the steps and the builder charter asks for the same rows in
  the handoff, and the goal sentinel treats a step the handoff does not show passing as a
  blocking gap.

## User Scenarios and Testing

### User Story 1 - the briefs list every step of the named job (Priority: P1)

The owner adds an item titled "fix the lint job". Its worktree's `.github/workflows/ci.yml`
has a job `lint` with two run steps. The builder brief, and later each gate brief (whose body
is the fixed `GATE_BODY`), lists both steps with their commands.

**Why this priority**: the failure in item 61 is a step nobody was told to run.

**Independent Test**: `wuwei brief builder X ...` and `wuwei brief quality X ... --gate` in
the `tests/test_brief.py` fixture with a worktree holding a two-step workflow; read the brief
files and `items.X.ci_jobs`.

**Acceptance Scenarios**:

1. **Given** an item that names a job with two steps, **When** the builder brief and the gate
   briefs are written, **Then** each brief lists `CI step 1` and `CI step 2` with the job,
   step name, `file:line` and command of each.
2. **Given** the job was named only in the fix-round feedback (`lint: failure <url>`),
   **When** the fix round opens, **Then** `items.X.ci_jobs` records the job, the builder's
   prompt lists both steps, and the next gate brief and the delta continue prompt list them.
3. **Given** an item whose texts name no workflow job (or that has no worktree), **When** its
   briefs are written, **Then** they are byte-for-byte what they are today and no `ci_jobs`
   is recorded.

### User Story 2 - a verdict citing one step is refused (Priority: P1)

A gate on that item writes a verdict with a row for step 1 only. The verdict lint refuses it,
naming step 2 and the row to write.

**Independent Test**: `verdict.lint` with the two steps passed in; `verdict.lint_file` on a
gate file whose seat's item records `ci_jobs` and whose worktree holds the workflow.

**Acceptance Scenarios**:

1. **Given** an item that names a job with two steps, **When** a gate verdict cites only
   `CI step 1`, **Then** the lint exits 1 naming `CI step 2` and the form
   `CI step <n>: PASS|FAIL|NOT RUN <what ran and what it showed>`.
2. **Given** rows for both steps, **When** the verdict is otherwise valid, **Then** the lint
   accepts it.
3. **Given** `Verdict: PASS` with `CI step 2: FAIL ...`, **Then** the lint exits 1.
4. **Given** two rows for the same step, **Then** the lint exits 1.
5. **Given** an item with no `ci_jobs`, or a gate file whose seat or item cannot be resolved,
   **Then** the lint behaves exactly as today.
6. **Given** a recorded job's workflow file cannot be read at lint time (a symlink, over
   1 MiB, an OS read error), **Then** the lint exits 2 naming the file, never clean when
   unmeasured. A workflow file that is simply gone is the edge case below.

### User Story 3 - the charters say it (Priority: P2)

The builder charter tells the builder to run every listed step and report one row per step;
the goal sentinel charter makes a listed step with no passing result a blocking gap; every
sentinel agent's Verdict format section carries the `CI step` row.

**Independent Test**: `bin/wuwei agents build` regenerates `agents/`; `tests/test_agents.py`
golden test and the I44 invariant (every sentinel example lints) stay green.

**Acceptance Scenarios**:

1. **Given** the regenerated agents, **Then** `agents/builder.md` and
   `agents/sentinel-goal.md` carry the new charter lines and every `agents/sentinel-*.md`
   Verdict format section lists the `CI step` row.

### Edge Cases

- A job named in a text that is not in any workflow of the worktree: nothing is recorded.
- A recorded job no longer in the workflow at a later head (the fix renamed or removed it, or
  removed the file): the brief block says `CI job <ref>: not in the workflow file at this
  head`, and the lint requires rows only for steps it can read.
- A job with matrix values: steps are listed once, commands verbatim (`${{ matrix.x }}` left
  for the seat to substitute).
- The same job named twice, or by id and by `name:`: recorded once.
- A second-opinion brief copies the first brief's body, which already holds the step block:
  the block is not appended twice.
- A job id such as `test` and prose "the test job" in a non-CI item: the job is recorded and
  its steps listed. The cost is rows for a job the item did not break, never a missed step.

## Requirements

### Functional Requirements

- **FR-001**: The workflow reader (`calibrate._workflow`) records each job's steps in order,
  each with its `name:` (or none), first line number and full `run:` command (block scalars
  joined by newlines, dedented), and never records a block indicator as a command.
- **FR-002**: One shared function finds the jobs a text names in a worktree, one lists the
  run steps of recorded jobs, and one renders the brief block; all live in `cli/wuwei/brief.py`
  and read workflows only through `calibrate._workflows`.
- **FR-003**: `brief.write` for a builder or gate brief with a worktree records the jobs its
  body and the item title name into `items.<item>.ci_jobs` (union with what is recorded) and
  appends the step block for every recorded job after the body.
- **FR-004**: `build.open_fix` records the jobs the feedback names into
  `items.<item>.ci_jobs` in its existing state write and appends the step block to the
  builder prompt.
- **FR-005**: The delta continue prompts (`dispatch._seats` and `dispatch.opinion`) carry the
  step block of the item's recorded jobs.
- **FR-006**: `verdict.lint` takes the listed steps and refuses a missing or duplicate
  `CI step <n>:` row and a PASS verdict with a FAIL row; `verdict.lint_file` resolves the
  steps from the seat's item and worktree. With no steps nothing changes.
- **FR-007**: `verdict.FORMAT` gains the `CI step` row, so every sentinel agent's Verdict
  format section lists it after `bin/wuwei agents build`.
- **FR-008**: `charters/builder.md` and `charters/sentinel-goal.md` carry the rule; `agents/`
  is regenerated.
- **FR-009**: `items.<item>.ci_jobs` is producer-owned (the reserved-key message names
  `wuwei brief` and the fix round).
- **FR-010**: Design spec 9.2 gains the invariant row and `tests/test_invariants.py` its
  check and mutation; `docs/site/reference.md` lists the lint rule.

### Key Entities

- **`items.<item>.ci_jobs`**: sorted list of `<workflow path relative to the worktree>#<job
  id>` strings; written only by `wuwei brief` and the fix-round opener; read by every later
  brief, delta prompt and the verdict lint.
- **CI step row**: `CI step <n>: PASS|FAIL|NOT RUN <evidence>` in a gate verdict.

## Success Criteria

- **SC-001**: For an item naming a two-step job, the builder brief and every gate brief list
  both steps with their commands.
- **SC-002**: A gate verdict citing one of the two steps is refused by the lint, naming the
  missing step.
- **SC-003**: Items that name no job get the same briefs and lint results as before (the full
  suite passes unchanged apart from regenerated agents).

## Assumptions

- The orchestrator notes file named for this issue (`notes/733-full.md`) does not exist and no
  dry-run workspace was named; the failure was reproduced in process with the repository's
  parser and lint, and the mechanism traced in the code paths cited above.
- #648 (one broken main is one fix item) is not on `main`; this feature does not depend on it
  and names no `main_broken` record. When #648 lands, its fix item's feedback names the check
  and is detected the same way.
- Only `run:` steps are listed. A step that is only `uses:` (checkout, setup, an action that
  lints) has no local command. Would overturn it: a CI-fix item whose failing step is an
  action; then list `uses:` steps with "no local command" and accept `NOT RUN` for them.
- Step and job `working-directory`, `env` and `shell` are not rendered; the `file:line` lets
  the seat read them. Would overturn it: a seat running a listed command from the wrong
  directory; then prefix `cd <dir> &&`.
- The detection words are `job <name>`, `<name> job` and the fix-feedback check line. A plain
  mention of a job id elsewhere is not a CI fix (a job named `test` would otherwise match
  every brief).
- The tracker ticket's title is not read (no network read in `brief.write`); the item title
  is read when the item has one (`plan add` items, claimed PRs).
- `NOT RUN` is accepted by the lint. A step that cannot run locally (a service, a secret)
  should not force a false PASS or FAIL; the goal sentinel treats a step not shown passing as
  a blocking gap.
- The builder's handoff is not linted (no builder report lint exists, and the issue asks for
  the verdict to cite each step); the builder charter asks for the same rows.
- The new invariant takes id I60, the id the orchestrator reserved for this item.
- `guards/pr.py` and `obligations.py` keep calling `verdict.lint` without steps: every gate
  verdict they read was already received through `lint_file`.
