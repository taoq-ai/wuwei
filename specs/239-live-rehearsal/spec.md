# Feature Specification: The delivery journey is the release criterion

**Feature Branch**: `239-live-rehearsal`

**Created**: 2026-09-30

**Status**: Draft

**Input**: GitHub issue #239, "test(e2e): the delivery journey is the release criterion: no
compensating actions in the fixture, and a bounded live rehearsal". Design spec sections
5.8, 9.1 and 10; follows #179 (headless runner), #212, and #225 (landed as #241).
Evidence: the whole-system review of 2026-09-30, point 3.

## Evidence (current main, `e9e7fd9`)

Reproduced read-only in a scratch copy of the worktree with the pipeline interpreter.

1. The two compensating actions the review named (`day.transition('raised')` and
   `day.transition('merged')`, formerly lines 43 and 81 of `tests/test_e2e_day.py`) were
   removed by #241: `state.record_pr` and `pr_actions.observe` now move those phases. One
   compensating action remains: `day.transition('fix')` at `tests/test_e2e_day.py:34`.
   Deleting that line makes `test_scripted_day` fail at line 36:
   `dispatch next A` returns `{'action': 'fix', 'roles': ['quality']}` where
   `{'action': 'gates', 'roles': ['quality']}` is expected. The fix builder ran, its checks
   passed, and the item never left `gate`.
   Root cause: nothing in the product moves `gate` to `fix`.
   - `dispatch.receive` (`cli/wuwei/dispatch.py`, the `update` closure at lines 180 to 187)
     records the third initial verdict, one of them FIX, and leaves the phase in `gate`.
   - `dispatch.next_step` (`cli/wuwei/dispatch.py:101-103`) computes `action: fix` from
     `gate` but does not move it.
   - `build.next_action` (`cli/wuwei/commands/build.py:148-149`) moves only `planned` to
     `implement` at launch, and the build-done joint (`cli/wuwei/commands/build.py:366`)
     maps only `implement` and `fix`, so a fix build started in `gate` finishes in `gate`.
   The gap is documented as intended: `docs/site/reference.md:95` says "`gate` to `fix`
   stays a planner transition", and `skills/wuwei-plan/SKILL.md:48` tells the planner to
   "transition the item to `fix`" (decided in `specs/208-loop-joints/spec.md:145`). That is
   the operator bookkeeping the review asks the product to own.
   A prototype of FR-001 in the scratch copy made the scripted day pass without the line;
   the only other failures in the full suite were six `tests/test_dispatch.py` tests that
   perform the same manual `state.transition('A', 'fix', root)` after the last initial
   receipt (they then fail with "fix -> fix").
2. The fixture also reconstructs a job handle: `Day.gate` in `tests/fakes/day.py` passes
   `json.dumps({'id': name})` to `runtime continue` for the delta instead of the handle
   `runtime dispatch` printed for that seat.
3. `scripts/headless_e2e.py` is the only real-Claude runner. It forbids commits, pushes and
   PRs, parks the item, and treats a missing `ANTHROPIC_API_KEY` as exit 0 with "skipping"
   (`scripts/headless_e2e.py:259-261`), so a skip is indistinguishable from a pass by exit
   code. It has no code host, no fix round, no owner decision and no merge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The scripted day passes with no compensating action (Priority: P1)

The scripted day in `tests/test_e2e_day.py` runs every step through the product. Where it
used to move a phase itself it now asserts that the product moved it.

**Why this priority**: the default PR suite is the cheap journey; while it repairs state
itself it certifies work the product does not do.

**Independent Test**: `python -m pytest -q tests/test_e2e_day.py tests/test_dispatch.py`.

**Acceptance Scenarios**:

1. **Given** the fixture without compensating actions and current main, **When** the
   scripted day runs, **Then** it passes, and after the last initial gate verdict (quality
   FIX) the item is already in `fix` with no `state transition` call.
2. **Given** an item in `gate` with arch PASS and security PASS recorded, **When**
   `dispatch receive` records quality FIX, **Then** the same write moves the item to `fix`
   and the `gate.received` event carries `phase_changes: {item: 'fix'}`.
3. **Given** three initial PASS verdicts, **When** the last is received, **Then** the item
   stays in `gate` and `dispatch next` returns `raise`.
4. **Given** an initial FIX next to an initial PARK or ESCALATE, **When** the last verdict is
   received, **Then** the item stays in `gate` and `dispatch next` returns `escalate`.
5. **Given** the verdicts are incomplete (a FIX received, another role missing), **When**
   `dispatch next` runs, **Then** it still returns `gates` for the missing role and the item
   stays in `gate`.
6. **Given** the delta round in the scripted day, **When** the planner continues the
   sentinel, **Then** it passes the job handle `runtime dispatch` printed for that seat, not
   one the fixture builds.

---

### User Story 2 - Bounded live rehearsal before a release (Priority: P1)

The owner runs `python3 scripts/headless_e2e.py --rehearsal` before cutting a release. It
builds the signed plugin, installs it for a real Claude Code planner, clones a designated
test repository on the code host with real local Git, and takes one item through plan, a
failing fast check with continuation, a gate FIX and delta, PR raise, one owner decision
answered on the host terminal, merge under the merge policy and a verified close. It
prints owner interventions, elapsed time, model cost and every unexpected refusal next to
the verdict.

**Why this priority**: the review found that a large passing suite did not show that the
owner can finish ordinary work; this is the release criterion.

**Independent Test**: offline tests in `tests/test_headless_e2e.py` drive the rehearsal
with stubbed process runs and recorded evidence; the live run is the owner's.

**Acceptance Scenarios**:

1. **Given** credentials, a host terminal and a test repository, **When** the rehearsal
   runs, **Then** it completes and prints a verdict line followed by one JSON line with
   `verdict`, `interventions`, `elapsed_seconds`, `cost_usd`, `refusals`, `findings` and
   `pr`.
2. **Given** no `ANTHROPIC_API_KEY` (and no `--local-login`), or no `WUWEI_REHEARSAL_REPO`,
   or no `GH_TOKEN`, or no host terminal, **When** the rehearsal runs, **Then** it makes no
   external call, prints `rehearsal unmeasured: <reason>` and the JSON line with
   `"verdict": "unmeasured"`, and exits 2; pass is exit 0 and fail is exit 1.
3. **Given** recorded evidence of the whole journey, **When** it is validated, **Then** there
   are no findings; **Given** the same evidence with any one step missing (no `continue`
   build action, no initial FIX, no delta PASS, no raised PR, no owner decision, no
   accepted merge, item not `merged`, close not requested, a seat still running), **Then**
   that step is a finding and the verdict is fail.
4. **Given** the planner or operator called `state transition`, `state set` or
   `state recover` during the run, **When** the result is measured, **Then** each call is
   listed under `interventions` and is a finding (a manual repair is not a pass). The
   planned owner answer to the decision is listed under `interventions` too, marked
   planned, and is not a finding.
5. **Given** `hook.refusal` events or CLI calls that exited 2 during the run, **When** the
   result is measured, **Then** each is listed under `refusals` with its reason or command,
   whether or not the verdict is pass.
6. **Given** the Claude results report `total_cost_usd`, **When** the result is measured,
   **Then** `cost_usd` is their sum; when any session does not report it, `cost_usd` is
   `null` and the verdict line says cost unmeasured.

---

### User Story 3 - Skips are unmeasured in the existing headless day too (Priority: P2)

`python3 scripts/headless_e2e.py` without credentials exits 2 with `unmeasured` in its
line, never 0.

**Why this priority**: the issue states skips are never reported as pass; the same script
must not keep a second meaning for exit 0.

**Independent Test**: `test_no_key_skips_before_any_external_call` in
`tests/test_headless_e2e.py`.

**Acceptance Scenarios**:

1. **Given** no `ANTHROPIC_API_KEY` and no `--local-login`, **When** the default mode runs,
   **Then** it makes no external call, prints `headless e2e unmeasured: ANTHROPIC_API_KEY is
   not set`, and exits 2.

---

### User Story 4 - The owner runs the rehearsal from one page (Priority: P2)

`docs/site/rehearsal.md`, linked from the site index, tells an operator everything needed:
prerequisites, how to prepare the test repository, the environment variables, the
command, what the terminal prompt asks, the bounds, how to read the output and exit codes,
what is left on the test repository, and that it runs before a release while the scripted
day runs on every PR.

**Independent Test**: `tests/test_docs.py` checks the page exists with the site front
matter, is linked from `index.md`, and names the command, the variables and the three
verdicts.

**Acceptance Scenarios**:

1. **Given** the docs, **When** an operator follows `docs/site/rehearsal.md` alone, **Then**
   they can run the rehearsal and interpret its result.

### Edge Cases

- A `claude -p` session that ends with an error subtype, exhausted turns or budget, or an
  expired login is unmeasured (exit 2), as the existing `check_result` already decides.
- The merge policy refuses (for example the test repository requires approvals): the
  rehearsal records the refusal reason as a finding and fails; it never merges by any
  other route.
- The owner declines the digest prompt: `decision outcome` exits 1; the rehearsal does not
  start the second session and reports fail with that finding.
- The builder satisfies the fast check on its first try, so no `continue` action is seen:
  that is a finding ("no failing check with continuation"), not a pass.
- A `hook.refusal` from a guard doing its job (the model improvised) is listed, not
  hidden; it does not by itself fail the run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `dispatch.receive` MUST move an item from `gate` to `fix` in the same state
  write that records the last initial verdict when all three initial verdicts are
  recorded, at least one is FIX and none is PARK or ESCALATE.
- **FR-002**: Every other phase rule MUST stay as it is: `next_step` results, the
  `gate`/`delta` receive checks, `build` transitions, `record_pr` and `observe`.
- **FR-003**: `tests/test_e2e_day.py` MUST contain no `state transition` call and no
  fixture step that performs product work; the `Day.transition` helper is removed.
- **FR-004**: The delta continuation in the fixture MUST use the job handle printed by the
  seat's `runtime dispatch`.
- **FR-005**: The planner skill and the operator reference MUST say the product moves
  `gate` to `fix`, and MUST no longer tell the planner to transition it.
- **FR-006**: `scripts/headless_e2e.py --rehearsal` MUST run the journey in User Story 2
  with the signed plugin built by `scripts/build-release.py`, real Claude Code seats, real
  local Git and the test repository named by `WUWEI_REHEARSAL_REPO`.
- **FR-007**: The rehearsal MUST check its preconditions (Claude credential, test
  repository, `GH_TOKEN`, host terminal) before any external call and report a missing one
  as unmeasured, exit 2.
- **FR-008**: The rehearsal MUST be bounded: fixed turn, USD and wall-clock limits per
  Claude session, and no paid retries.
- **FR-009**: The rehearsal MUST print its verdict line and a final one-line JSON result
  with the fields in User Story 2, scenario 1, for every outcome including unmeasured.
- **FR-010**: The owner decision MUST be answered by the operator through the existing
  `decision outcome` host-terminal confirmation; the rehearsal adds no bypass.
- **FR-011**: No workflow change: the rehearsal is not run on pull requests or pushes; the
  scripted day stays in the default suite.
- **FR-012**: The default headless mode MUST report a missing credential as unmeasured,
  exit 2.
- **FR-013**: `docs/site/rehearsal.md` MUST document the rehearsal for the owner and be
  linked from `docs/site/index.md`; `docs/headless-e2e.md` MUST state the new skip exit.

### Key Entities

- **Rehearsal result**: one JSON object on the last stdout line. `verdict` (`pass`,
  `fail`, `unmeasured`), `interventions` (list of strings), `elapsed_seconds` (number),
  `cost_usd` (number or `null`), `refusals` (list of strings), `findings` (list of
  strings), `pr` (PR reference or `null`).

## Success Criteria *(mandatory)*

- **SC-001**: The default suite passes with the scripted day free of compensating actions.
- **SC-002**: `grep -n "transition" tests/test_e2e_day.py` finds only the `phase_changes`
  read.
- **SC-003**: The rehearsal with no credentials exits 2 and prints `unmeasured`, verified
  offline.
- **SC-004**: An owner-run rehearsal against a disposable repository prints all four
  measurements next to the verdict.

## Assumptions

- #225 landed as #241 and already removed the raised and merged repairs; the only remaining
  compensating action is the manual `fix` transition, fixed at the shared producer
  (`dispatch.receive`), not in the fixture.
- The move happens on the receipt that completes the initial round because that is the
  write that makes the fix round a fact; `next_step` stays a read and `build` stays
  unaware of gate verdicts.
- `merge.item_evidence` counts fix and delta phase changes only from `state.*` events. The
  pre-PR fix change now arrives on `gate.received`, so it is not counted there; the delta
  change still comes from the build-done `state.transition` and keeps the budget bound, and
  `dispatch.next_step` already escalates a second pre-PR fix round. `merge.py` is left
  unchanged. Metrics read `phase_changes` from every event and still count one fix round.
- "Signed asset" means the plugin built and signed by `scripts/build-release.py` from the
  checkout with a throwaway key, as the existing runner does; a release asset does not
  exist yet when the rehearsal runs before a release.
- The code host credential is `GH_TOKEN`, which `gh` reads. It is passed into the Claude
  session environment because the CLI's GitHub adapter runs under the planner's Bash; the
  docs tell the owner to use a token scoped to the test repository only. Separating
  publication credentials from seats is point 2 of the review and out of scope.
- The rehearsal is attended: the owner decision needs the host terminal (`/dev/tty`), so it
  cannot run in CI. No terminal is unmeasured.
- The failing check is made deterministic by a fast check that requires a line the builder
  brief does not mention and that the failure output names; the gate FIX is made
  deterministic by a rehearsal rule in the quality sentinel's brief. Both depend on the
  model following its brief; when it does not, the missing step is a finding.
- Turn, budget and time bounds are initial values held as constants in the script; the
  owner tunes them.
- The rehearsal leaves its merged PR and branch on the test repository; the repository is
  disposable by definition.
- `_pipeline/release.sh` is owner tooling outside the repository; the orchestrator updates
  it to require a recorded rehearsal result (the last JSON line). Nothing in the repository
  touches it.
- Superseded on rebase: #238 (PR #249) made `dispatch next` open the fix round through
  `build.open_fix`, which moves `gate` to `fix` and arms the builder in one write. That is
  the single `gate` to `fix` transition; `dispatch receive` only records verdicts, so FR-001
  and scenario 2 hold through `dispatch next` rather than the receipt.
- Clarifying questions were not asked (AGENTS.md); the above are the defaults taken.
