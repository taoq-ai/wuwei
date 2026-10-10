# Feature Specification: the raise action is a ready-to-run shepherd launch that opens the PR with wuwei pr raise --item

**Feature Branch**: `783-raise-is-a-launch`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #783 (owner, 2026-10-10, items 72 and 74). After all gates passed,
`dispatch next` returned `"action": "raise"` with no command or prompt. The owner copied an
earlier shepherd brief from a transcript and launched the shepherd by hand. A PR a seat opens
with `gh pr create` is not linked to its item, and linking it later depends on the host API.

## Root cause

Reproduced read-only on `main` with the existing in-process tests. No dry-run workspace was
named (A9).

- `cli/wuwei/dispatch.py:379` (gate phase, every initial verdict PASS) and
  `cli/wuwei/dispatch.py:397` (delta phase, no blocking finding) return
  `{'action': 'raise', 'notes': [...]}` and nothing else.
  `tests/test_dispatch.py::test_fix_pass_then_only_quality_delta` pins that exact dict
  (line 107) and passes. The gate action carries `seats` and `commands` (#551, `_seats` at
  `dispatch.py:518`). Raise carries neither.
- `cli/wuwei/commands/build.py:48` to `55` (#666) prints whatever `dispatch.next_step`
  returns once the build is done, so `build next` has the same empty raise.
- The brief command and the launch already exist, but only in `wuwei next`:
  `cli/wuwei/commands/next.py:401` to `417`, `_shepherd`, builds
  `wuwei brief shepherd <item> shepherd-<item> --worktree ... --body ...`, then
  `brief.seat_action('shepherd', ...)`, with the body `SHEPHERD_BODY` (`next.py:84`). The
  planner that asks `dispatch next` or `build next` never sees it. The body does not say how
  to open the PR.
- `charters/shepherd.md:9` says "Raise the PR through the configured adapter". It does not
  name `wuwei pr raise --item`, so a seat can open the PR with `gh pr create`.
- `cli/wuwei/guards/pr.py:247` to `249`, `create_check`: when the gate set passed,
  `gh pr create` returns `(0, '')` with no word about the item.
  `tests/test_pr_guards.py::test_create_from_the_workspace_root_names_a_recorded_branch`
  pins `(0, '')` for a recorded item `DIV-1` and passes. Only `shepherd.raise_pr`
  (`cli/wuwei/shepherd.py:357`, `state.record_pr`) links a PR to its item and ranks its
  reviewers.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where are the shepherd brief command and launch built? A: In `dispatch`, once, as
  `dispatch.raise_action`. `next_step` returns it at both raise points, and `wuwei next`
  renders it instead of building its own. `build next` agrees through #666 with no change.
- Q: What shape does raise take? A: The gate shape (#551). `seats` is always present (a
  list, empty or one launch); `commands` is present only when a step is due. Before the
  shepherd brief exists, `commands` holds its brief command. Once the brief exists and no
  seat has started, `seats` holds `brief.seat_action('shepherd', ...)`. With a seat already
  recorded, both are empty and `reason` names the seat and its status.
- Q: Does the guard refuse or warn? A: Below `strict` it warns on stderr and lets the call
  run, as the issue asks. Under `strict` it refuses, as #647 and #659 do for "a warning below
  strict". The refusal starts with `pr raise: `, so the hook levels it under `publish`.
- Q: What counts as "an item with a brief" for the guard? A: An item whose recorded
  worktree is the command's worktree (or whose branch `--head` names, #534) and that links
  no PR yet. `wuwei pr raise --item` has the same preconditions (A3).

## User Scenarios and Testing

### User Story 1 - raise hands the planner a ready launch (Priority: P1)

All gates pass. The planner runs `dispatch next A` (or `build next A`) and gets the exact
command that writes the shepherd brief. After it runs that command, the next call returns
the shepherd launch with its prompt, ready for Agent.

**Why this priority**: it is the owner's item 72; today the planner improvises the brief.

**Independent Test**: `main(['dispatch', 'next', 'A'])` and `main(['build', 'next', 'A', ...])`
in the `tests/test_dispatch.py` `root` fixture after three PASS verdicts.

**Acceptance Scenarios**:

1. **Given** all gates PASS and no shepherd brief, **When** `dispatch next A` runs, **Then**
   it exits 0 and prints `action: raise` with `notes`, `seats: []` and `commands` holding
   one `wuwei brief shepherd A shepherd-A --worktree <worktree> --body <body>`. The body
   names `bin/wuwei pr raise` with `--item A` and says never `gh pr create`. `build next A`
   prints the same JSON.
2. **Given** the brief `briefs/shepherd-A.md` exists and no seat `shepherd-A` is recorded,
   **When** `dispatch next A` runs, **Then** `seats` is
   `[brief.seat_action('shepherd', <brief>, <worktree>, root)]` (action `launch`,
   agent_type `wuwei:shepherd`, a prompt naming the brief) and there is no `commands`.
   `build next A` prints the same JSON.
3. **Given** a seat `shepherd-A` is recorded (running or stopped), **When** `dispatch next A`
   runs, **Then** `seats` is empty, there is no `commands`, and `reason` names `shepherd-A`,
   its status and `bin/wuwei why A`.
4. **Given** the delta round ends with only non-blocking findings, **When** `dispatch next A`
   runs, **Then** the brief command's body carries one `Review note: <note>` line per note.

### User Story 2 - the shepherd opens the PR with wuwei pr raise --item (Priority: P1)

The shepherd charter and its brief say the PR is opened with
`bin/wuwei pr raise <repo> --base <branch> --title <title> --body-file <file> --item <item>`,
which links it and ranks reviewers, and never with `gh pr create`. `pr claim` stays for a
PR that already exists.

**Acceptance Scenarios**:

1. **Given** `charters/shepherd.md`, **Then** its PR raise step names `wuwei pr raise`,
   `--item`, `gh pr create` as the way not to raise, and `wuwei pr claim` for a PR that
   already exists. `agents/shepherd.md` is regenerated from it.

### User Story 3 - gh pr create for a briefed item names wuwei pr raise (Priority: P2)

A seat runs `gh pr create` in a recorded item's worktree, or with `-R <repo> --head <item
branch>`, or after `cd <worktree> &&`.

**Acceptance Scenarios**:

1. **Given** posture `guarded` (default), a recorded item `DIV-1` that links no PR and whose
   gates passed, **When** a seat runs `gh pr create -r alice` there, **Then** the guard
   returns `(0, '')` and stderr carries
   `warning: DIV-1 is a WUWEI item: raise its PR with bin/wuwei pr raise example/project`
   with `--item DIV-1`.
2. **Given** posture `strict` and the same call, **Then** the guard returns exit 1 with a
   reason that starts `pr raise: DIV-1 is a WUWEI item` and names `--item DIV-1`.
3. **Given** the item already links a PR, or the directory is not a recorded item
   worktree, **Then** the result is today's, with no warning.

### Edge Cases

- The planner runs `wuwei next` instead: it shows the same brief command, then the same
  launch, then the existing card for a seat that stopped without a PR. The existing tests
  `test_verdict_rows_return_the_gate_action` and `test_shepherd_launch_then_card` pass
  unchanged.
- `dispatch next --all`: a raise entry with one launch in `seats` counts one launch against
  the free seats (`launch_set` already counts `len(seats)`); a raise with only `commands`
  counts none.
- An item without a recorded worktree (a test or a legacy row): the brief command names
  the workspace root, as `next._shepherd` does today.
- `gh pr create` from a subdirectory of the worktree: no warning (A4).
- Gates not passed: the guard's existing refusal stands; below strict the warning prints
  first.

## Requirements

### Functional Requirements

- **FR-001**: `dispatch.next_step` MUST return the raise action from one helper,
  `dispatch.raise_action(root, data, item, notes)`, at both raise points (`dispatch.py:379`
  and `:397`).
- **FR-002**: The raise action MUST carry `action`, `notes` and `seats` (a list). It also
  carries `commands` with the shepherd brief command while the brief
  `briefs/shepherd-<item>.md` does not exist. `seats` holds one shepherd launch from
  `brief.seat_action` while the brief exists and no seat of that name is recorded. While
  that seat is recorded, `reason` names it.
- **FR-003**: The shepherd brief body MUST name
  `bin/wuwei pr raise <owner/repo> --base <branch> --title <title> --body-file <file> --item <item>`,
  say that it links the PR to the item and requests the ranked reviewers, and say never
  `gh pr create`. It keeps one `Review note:` line per note.
- **FR-004**: `build next` MUST print the same raise action as `dispatch next`. This already
  holds through #666 once FR-001 does; a test pins it.
- **FR-005**: `wuwei next` MUST render its raise row from `dispatch.raise_action`.
  `next._shepherd` stops building its own command, and `SHEPHERD_BODY` moves to
  `dispatch.py`.
- **FR-006**: `charters/shepherd.md` MUST say the PR is opened with `wuwei pr raise ...
  --item <item>`, never `gh pr create`, and that `wuwei pr claim <ref> --item <item>` links
  a PR that already exists. Its version goes up and `agents/shepherd.md` is regenerated
  with `bin/wuwei agents build`.
- **FR-007**: `guards/pr.create_check` MUST act on an item it resolves (from `--head` per
  #534, else the recorded item whose worktree is the command's directory) that links no
  PR. Below `strict` it prints `warning: <reason>` to stderr. Under `strict` it returns exit
  1 with that reason. The reason names `bin/wuwei pr raise <repo> ... --item <item>`.
- **FR-008**: The gate check, the reviewer check and every other `create_check` result MUST
  NOT change. In particular `gate_check` keeps receiving the `item` it receives today.
- **FR-009**: The design spec (the 4.1 row for `gh pr create`, the 5.3 build-loop paragraph)
  and the site docs (`docs/site/daily.md` steps 5 and 6, the posture paragraph in
  `docs/site/reference.md`) MUST describe the raise shape and the warning.

### Key Entities

- Raise action: `{'action': 'raise', 'notes': [...], 'seats': [...], 'commands'?: [...],
  'reason'?: str}`.
- Shepherd brief: `days/<date>/briefs/shepherd-<item>.md`, written by
  `wuwei brief shepherd <item> shepherd-<item> --worktree <worktree> --body <body>`.

## Success Criteria

- **SC-001**: After all gates pass, the planner launches the shepherd from `dispatch next`
  output alone: one brief command, then one launch, with no copying from a transcript.
- **SC-002**: A shepherd that follows its charter or brief never opens a PR that WUWEI does
  not link. A `gh pr create` for a recorded item says so on the spot.
- **SC-003**: The changed test files pass; the full suite runs in CI.

## Assumptions

- **A1**: The brief name stays `shepherd-<item>`, as `next._shepherd` uses today. A shepherd
  that stopped without raising keeps the existing `wuwei next` card (`wuwei why <item>`),
  and `dispatch next` names it in `reason`. A new brief name per retry is not added
  (ponytail; add it when a stopped shepherd needs an automatic relaunch).
- **A2**: The brief body names `<owner/repo>` and `<branch>` as placeholders. The shepherd
  reads the repository and base from its brief header (`Worktree:`, `Merge-base: <sha>
  (<remote>/<branch>)`). Resolving the repository in `dispatch` would add a VCS call to every
  raise for text the brief header already carries.
- **A3**: "An item with a brief" is read as an item whose worktree is recorded and that
  links no PR. A brief records the worktree (`brief.write`), and every item that reaches
  its gates has a builder brief; `worktree adopt` and `worktree add --branch` record one
  too. These are the preconditions `shepherd.raise_pr` checks itself, so the warning never
  names a command that would refuse for a missing worktree. For the same reason the
  warning says "is a WUWEI item", not "has a brief".
- **A4**: The worktree match is exact (the existing `_recorded(path=...)`, #534). A
  `gh pr create` from a subdirectory of the worktree gets no warning. Ponytail: walk the
  parents when that case shows up.
- **A5**: The warning applies to every session the hook sees (planner or seat), not only
  subagents. `pr raise` is the one linked path for all of them, and the owner's own
  terminal runs no hook.
- **A6**: The warning follows the existing convention for a warning below strict
  (`protect_state.check_scratch`, #647): `warning: <reason>` on stderr and exit 0. It
  records no event, so it adds no nudge (owner item 76 is about nudge growth).
- **A7**: Under `strict` the hook levels the refusal as `publish`. Its reason starts with
  `pr raise: ` because `guards/pr.action` prefixes every `create_check` refusal. That
  matches design 9.1, "Under `strict`, refusals stay".
- **A8**: Existing tests that compare the whole raise dict (`tests/test_dispatch.py` lines
  107, 698, 777, 813 and 1223, `tests/test_parallel_dispatch.py` line 127) are updated to
  compare `action` and `notes`. The behaviour they pin does not change.
- **A9**: The orchestrator notes file for this issue does not exist, so no dry-run
  workspace was named. The root cause was reproduced from the existing tests that pin the
  empty raise dict and the silent guard (Root cause, above).
- **A10**: `gh pr create` is not refused below strict. The issue asks for a warning, and a
  refusal below strict would be a new wall against design invariant I1.

## Deferred

- None.
