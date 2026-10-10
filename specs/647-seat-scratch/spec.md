# Feature Specification: a scratch directory per seat, named after its item

**Feature Branch**: `647-seat-scratch`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #647 (owner, 2026-10-10): two builder seats shared one scratchpad,
and one overwrote the other's test script (`scratchpad/mutate.sh`) partway through its
testing. It cost a rerun and could mix one item's evidence into another's. Deliver: the
brief names a per-seat scratch directory (`<scratchpad>/<item>/<role>`, or
`.wuwei/scratch/<item>/` when the host offers none), created at seat launch and removed
after a confirmed merge; the brief tells the seat to write every temporary file there; the
PreToolUse guard warns on a Write to another item's scratch directory and never blocks
below strict.

## Root cause

Reproduced in-process on `main` (a temporary workspace with items `A` and `B`, the
`tests/test_brief.py` fakes): `brief.write('builder', 'A', ...)` and
`brief.write('builder', 'B', ...)` produce headers with no scratch line at all, and
`protect_state.check_file` returns `(0, '')`, silently, for a builder's Write to
`.wuwei/scratch/B/builder/mutate.sh`.

- `cli/wuwei/brief.py:367-464`: `write` builds the header (Charter, Written, Item, Seat
  policy, Worktree, Depth, Checks, Gate row, ...) and names no place for temporary files.
  Every Claude seat in a session inherits the same host scratchpad, so two seats that both
  pick `mutate.sh` write the same file.
- `cli/wuwei/guards/protect_state.py:425-435`: `check_file` only refuses protected
  `.wuwei` records; nothing reads which item a target directory belongs to, and nothing
  maps a subagent's tool call to its seat on PreToolUse (only `guards/traces.py:104-112`
  derives the subagent transcript, on PostToolUse).
- Nothing creates or removes a per-item directory: WUWEI never removes worktrees, and the
  confirmed-merge observation (`cli/wuwei/pr_actions.py:223-226`, the move to `merged`)
  touches state only.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which directory does the brief name? A: Both forms in one line: the host scratchpad
  subdirectory `<your scratchpad>/<item>/<role>/` first (a Claude seat always has one and
  writes there without a prompt), else the workspace directory
  `<workspace>/.wuwei/scratch/<item>/<role>/` (Codex and any host without a scratchpad).
  The role level is kept in both, so a sentinel's mutation copy and the builder's files on
  the same item never meet either.
- Q: Who creates it? A: `bin/wuwei brief` creates `.wuwei/scratch/<item>/<role>/` when it
  writes the brief. Every seat launch, Claude or Codex, starts from exactly one brief, so
  this is the one shared spot. WUWEI cannot know the host scratchpad's path; the brief tells
  the seat to create its subdirectory if missing.
- Q: When is it removed? A: When `pr state` (or the watch) observes the item's PR merged
  and moves the item to `merged`, `.wuwei/scratch/<item>/` is removed. WUWEI never removes
  worktrees, so the confirmed merge is the trigger.
- Q: How does the guard know the writer's item? A: From the subagent's transcript, the way
  a SubagentStop binds its seat: the call's `agent_id` gives the subagent transcript, its
  `WUWEI brief:` reference gives the seat, the seat gives item and role. A call with no
  `agent_id` (the planner, the owner) is never checked.
- Q: What counts as another item's scratch directory? A: A target under
  `<...>/scratchpad/<X>/...` or `<...>/.wuwei/scratch/<X>/...` where `X` is an item in
  today's state and not the writer's item. Any other subdirectory of the scratchpad is not
  an item's and is not checked.
- Q: Which posture area? A: `seats` (warn under observe and guarded, block under strict,
  overridable by `security.areas.seats`). The check prints `warning: <reason>` to stderr
  and exits 0 at `warn`, returns the refusal at `block` (the hook adds the
  `posture: seats = block` line), and is silent at `off`.

## User Scenarios and Testing

### User Story 1 - Each seat's brief names its own scratch directory (Priority: P1)

**Acceptance Scenarios**:

1. **Given** two seats on different items `X` and `Y`, **When** their briefs are written,
   **Then** their `Scratch:` lines name different directories (`.../X/builder/` and
   `.../Y/builder/`), and each line tells the seat to write every temporary file there.
2. **Given** a brief written for `builder` on `X`, **Then** `.wuwei/scratch/X/builder/`
   exists in the workspace.

### User Story 2 - A Write to another item's scratch directory warns (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a builder seat on item `A` and a Write to `.wuwei/scratch/B/builder/mutate.sh`
   (or `<scratchpad>/B/mutate.sh`), **When** the PreToolUse hook runs under `observe` and
   under `guarded`, **Then** it prints a warning naming the seat's own directory
   (`.wuwei/scratch/A/builder/`, or `<scratchpad>/A/builder/`) and exits 0.
2. **Given** the same Write under `strict`, **Then** the hook refuses it with the same
   reason and the line `posture: seats = block (set security.areas.seats)`.
3. **Given** a Write to the seat's own item directory, a Write from the main session (no
   `agent_id`), or a Write to a scratchpad subdirectory that names no item of today, **Then**
   the hook prints nothing and exits 0.

### User Story 3 - The scratch directory goes with the merge (Priority: P2)

**Acceptance Scenarios**:

1. **Given** item `A` with `.wuwei/scratch/A/builder/x` and item `B` with
   `.wuwei/scratch/B/builder/y`, **When** `pr state` observes `A`'s PR merged, **Then**
   `.wuwei/scratch/A/` is gone and `.wuwei/scratch/B/` is kept.

### Edge Cases

- A seat whose subagent transcript cannot be found is not bound: no warning (the seat is
  unknown, not another item's).
- A malformed `agent_id` or an unreadable state or config is exit 2, levelled by the
  `seats` area like any guard result (a warning below strict).
- `.wuwei/scratch/<item>` replaced by a symlink is not followed on removal (`shutil.rmtree`
  refuses a symlink; the error is ignored).
- An item carried to tomorrow keeps its directory: the path has no date.

## Requirements

- **FR-001**: `workspace.SCRATCH = '.wuwei/scratch'`, the one name for the workspace scratch
  base, read by the brief, the guard and the merge cleanup.
- **FR-002**: `brief.write` adds a header line after `Seat policy:`:
  `Scratch: <your scratchpad>/<item>/<role>/, or <root>/.wuwei/scratch/<item>/<role>/ when
  your host names no scratchpad; create it if missing and write every temporary file there,
  never at the scratchpad root or in another item's directory`, and creates
  `<root>/.wuwei/scratch/<item>/<role>/` once the brief is written.
- **FR-003**: `brief.subagent_transcript(payload)` returns the subagent transcript path of a
  hook call with `agent_id` (the derivation `traces.check` uses today, which then calls it),
  else None; `brief.seat_of(payload, data)` returns that transcript's seat record (matched by
  its `WUWEI brief:` reference), else None.
- **FR-004**: `protect_state.check_scratch`, a second PreToolUse guard on
  `Write|Edit|MultiEdit|NotebookEdit`, implements User Story 2; `guards.AREAS` maps
  `protect_state.check_scratch` to `seats`.
- **FR-005**: `pr_actions.observe` removes `<root>/.wuwei/scratch/<item>/` for each item it
  moves to `merged`, after the state write.
- **FR-006**: Docs: a `Scratch directory` row in `docs/site/reference.md` (Seat briefs and
  the build loop) and `scratch directories (protect_state.check_scratch)` in the `seats` row
  of `docs/site/security.md`.

## Success Criteria

- **SC-001**: No two seats on different items are told the same scratch directory.
- **SC-002**: A seat writing into another item's directory is told which directory is its
  own, without being blocked below strict.

## Assumptions

- No orchestrator notes file exists for #647 (`notes/647-full.md` is missing); the issue
  text is the input, and the root cause was reproduced in a temporary workspace instead of
  a named dry-run workspace.
- The workspace fallback keeps the role level (`.wuwei/scratch/<item>/<role>/`, the issue
  wrote `.wuwei/scratch/<item>/`): two gate seats on one item mutate whole-tree copies at
  the same time. The guard and the cleanup key on the item level only, so the issue's form
  is a subset.
- The warning goes to stderr, as `guards.profile_result` does today; a PreToolUse exit 0
  stderr line reaches the transcript, not necessarily the model. The brief line is the
  prevention; the warning is the trace. If seats keep writing into other items'
  directories, the upgrade is `hookSpecificOutput.additionalContext` on stdout.
- No `guard.would_refuse` or `hook.warning` event: both nudge the owner, and a seat's scratch
  path is the seat's to fix.
- The host scratchpad's subdirectories are not removed: WUWEI does not know the path, and
  the host clears its session scratchpad.
- The incident wrote at the scratchpad root (`scratchpad/mutate.sh`), which no item owns; the
  guard cannot attribute such a write and does not try. The brief line forbids the root.
- Charters are unchanged: the brief line is what each seat reads for its paths, as it is
  for `Worktree:` and `Verdict file:`.
