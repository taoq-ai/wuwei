# Feature Specification: a seat starts from an empty scratch directory and checks only a clean copy

**Feature Branch**: `734-fresh-scratch`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #734 (owner, 2026-10-10, item 62): a reused scratch directory held
files from an earlier session, and the quality gate got false lint failures from them before
the run was discarded. Deliver: the per-seat scratch directory (#647) is created empty at
launch (an existing one is moved aside with a timestamp, never reused); the gate charters
say to extract the copy into a fresh directory and to compare its file list with
`git ls-tree -r --name-only HEAD` before any check, reporting extras; `dispatch receive`
warns when a verdict's evidence names a scratch path that predates the seat.

Governing: `charters/_common.md#Evidence and gates` (rule 2, gate step zero) and
`docs/specs/2026-09-24-wuwei-design.md#5.3 Rules` (the mutation step row).

## Root cause

Reproduced in-process on `main` (the `tests/test_brief.py` `day` fixture in a temporary
workspace; no dry-run workspace exists for this issue): with
`.wuwei/scratch/X/builder/leftover.py` already on disk, `bin/wuwei brief builder X sx2 ...`
exits 0 and `.wuwei/scratch/X/builder/` still holds `leftover.py`. The new seat is told to
write there and inherits the earlier seat's files.

- `cli/wuwei/brief.py:586`: `write` ends with `scratch.mkdir(parents=True, exist_ok=True)`.
  `exist_ok=True` turns an earlier seat's directory into the new seat's directory, files
  included. The directory lives until the item merges (`cli/wuwei/pr_actions.py:232-234`), so
  every later seat of the same item and role (a fresh fix-round builder, a next-day gate, a
  gate relaunched after a lost seat) starts from what the last one left.
- `cli/wuwei/brief.py:423-426`: the `Scratch:` line tells a Claude seat to use
  `<your scratchpad>/<item>/<role>/` and to "create it if missing"; a host scratchpad that
  outlives a session (a resumed planner session) keeps the same subdirectory, and nothing
  says that existing files are not the seat's.
- `charters/_common.md:18` (rule 2, gate step zero): "Mutate only a whole-tree detached copy
  at that sha in scratch" names no fresh directory and no check that the copy holds exactly
  the tree. A copy extracted over stale files carries the stale files into lint, tests and
  mutation, which is the false failure the owner saw.
- `cli/wuwei/dispatch.py:618-722`: `receive` lints and records a verdict and never looks at
  the scratch paths its evidence names, so a verdict built on a stale copy is recorded
  without a word.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where is "launch" for the workspace directory? A: `brief.write`, where #647 already
  creates it. Every new seat, Claude or Codex, gets exactly one fresh brief, and a continued
  seat (a delta round, a #614 builder continue) reuses its brief, so it keeps its own files.
  `guards/agent_launch.py` runs only for Claude seats and also runs on continues; it is not
  changed.
- Q: Which existing directory is moved aside? A: One that holds any entry. An empty one is
  indistinguishable from a new one, so it is kept (no empty timestamped litter, for example
  when a second-opinion brief follows its Claude gate brief on the same item and role).
- Q: What name does the moved directory get? A: `<role>.<YYYYmmddTHHMMSS.ffffff>` next to it,
  from `workspace.now()`. It stays under `.wuwei/scratch/<item>/`, so the #647 merge cleanup
  removes it with the item.
- Q: What about the host scratchpad, which WUWEI cannot see? A: The `Scratch:` line tells the
  seat to move its directory aside with a timestamp suffix when it holds files the seat did
  not write. The charter rule below is what stops a stale copy from being checked.
- Q: Where does the copy rule live? A: In `charters/_common.md` rule 2 (Evidence and gates),
  next to the existing detached-copy sentence: every sentinel reads it, one home (test
  `test_charter_sentences_have_one_home`). It covers every copy a gate checks, not only step
  zero, since the incident was a quality lint run.
- Q: Which command does the charter name for making the copy? A: None. `git archive` is not
  in `shell._GIT_READS`, so the deploy guard calls it an unknown git subcommand (a warning
  below strict, a refusal under strict); naming it would steer seats into that. The charter
  names the comparison, `git ls-tree -r --name-only <sha>`, a known read.
- Q: How does `receive` date a path? A: Against the seat's brief `Written:` time (stable
  across a continued seat, and earlier than the fresh `mkdir`), using the path's `st_ctime`:
  `git archive | tar -x` sets each file's mtime to the commit time, so mtime predates every
  seat; ctime is when the file was written into the directory.
- Q: Warn how? A: `print('warning: ...', file=sys.stderr)` after the verdict is recorded, the
  form `grants.py` and `outward.py` use. Never a refusal, no state field, no event.

## User Scenarios and Testing

### User Story 1 - A new seat starts with an empty scratch directory (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `.wuwei/scratch/X/builder/` holding `stale.py`, **When** a brief is written for
   `builder` on `X`, **Then** `.wuwei/scratch/X/builder/` exists and is empty, and
   `.wuwei/scratch/X/builder.<timestamp>/stale.py` holds the earlier file.
2. **Given** `.wuwei/scratch/X/builder/` that exists and is empty, **When** a brief is written,
   **Then** it is kept and no timestamped sibling appears.
3. **Given** any brief, **Then** its `Scratch:` line tells the seat to move its directory aside
   with a timestamp suffix when it holds files it did not write.

### User Story 2 - A gate checks only a clean copy (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the generated sentinel agents, **Then** each carries the rule: every copy of the
   tree a gate checks is made in a new, empty directory under its `Scratch:` directory, and
   before any check its file list is compared with `git ls-tree -r --name-only <sha>` and each
   extra file is listed in the verdict.
2. **Given** an extracted copy with an extra file, **Then** the charter's comparison step lists
   it before the checks run (charter text; tests assert the rule, never model prose).

### User Story 3 - receive warns on stale scratch evidence (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a verdict whose `Probe:` row names a scratch path (`.wuwei/scratch/...` or
   `.../scratchpad/...`, relative or absolute, with or without a `:<line>` suffix) that existed
   before the seat's brief was written, **When** `dispatch receive` records it, **Then** stderr
   carries one `warning:` line naming the path and the seat, and the verdict is recorded as
   before.
2. **Given** the same verdict when the path is newer than the brief, or does not exist, or the
   brief has no `Written:` line, **Then** no warning is printed.

### Edge Cases

- A continued seat (delta round) keeps its directory: no new brief is written.
- `scratch` replaced by a symlink: `rename` moves the link itself, never its target.
- Two moves of the same directory with the same timestamp (only with a fixed `WUWEI_NOW`): the
  second `rename` onto a non-empty directory raises `OSError`, and `wuwei brief` exits 2 with
  the reason. Marked with a `ponytail:` comment.
- A `Written:` value that does not parse is damage to a brief WUWEI wrote: `receive` exits 2
  with the reason (fail closed), as for any other unreadable record.

## Requirements

- **FR-001**: `brief.write` moves an existing, non-empty `<root>/.wuwei/scratch/<item>/<role>/`
  to `<role>.<YYYYmmddTHHMMSS.ffffff>` in the same parent before creating the directory
  (replacing the plain `mkdir` at `cli/wuwei/brief.py:586`).
- **FR-002**: The `Scratch:` header line says "create it if missing, or move it aside with a
  timestamp suffix when it holds files you did not write" in place of "create it if missing";
  the rest of the line is unchanged.
- **FR-003**: `charters/_common.md` rule 2 carries the copy rule of User Story 2; the
  frontmatter version is bumped and `agents/*.md` are regenerated with `bin/wuwei agents
  build`.
- **FR-004**: `dispatch.receive` prints one `warning:` line per scratch path in the verdict
  text whose `st_ctime` is earlier than the seat brief's `Written:` time, after the state write.
- **FR-005**: Docs: the `Scratch directory` row of `docs/site/reference.md` names the move
  aside and the receive warning.

## Success Criteria

- **SC-001**: No new seat is told to write into a directory holding an earlier seat's files.
- **SC-002**: A gate verdict built on files older than its seat is flagged to the planner when
  it is received.

## Assumptions

- No orchestrator notes file exists for #734 (`notes/734-full.md` is missing); the issue text
  is the input, and the root cause was reproduced in a temporary workspace.
- "At launch" means at brief write (see Clarifications); a seat continued on the same brief
  keeps its directory, since its files are its own. Overturned if a continue must also start
  empty.
- The only concurrent pair on one item and role is a Claude gate and its second opinion. The
  Claude seat writes in its host scratchpad, and an empty workspace directory is not moved, so
  the second-opinion brief never moves a running seat's files. If a Claude seat without a host
  scratchpad wrote into the workspace directory, its files would be moved (kept, not deleted).
- The charter names `<sha>` (the brief's `HEAD:`) where the issue wrote `HEAD`: the copy is at
  the pinned sha, and the gate brief already requires the worktree HEAD to equal it.
- Only extra files are reported, as the issue asks; files missing from the copy are not.
- `receive` reads paths from the whole verdict text, not only `Probe:` rows; a path it cannot
  stat is not dated and not warned (a seat may have removed its copy).
- No design spec 9.2 invariant: no guard or decision rule changes; the receive line is a
  warning, never a refusal.
- #672 (sibling, not on `main`) will add its own receive warning and probe environment; this
  item does not depend on it.
