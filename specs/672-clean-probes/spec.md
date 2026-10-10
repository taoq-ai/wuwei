# Feature Specification: gate probes leave no files in the builder's worktree

**Feature Branch**: `672-clean-probes`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #672 (owner, 2026-10-10, item 37): a reviewer's probe left
`__pycache__` in the builder's worktree. Deliver: the brief sets `PYTHONDONTWRITEBYTECODE=1`
and `PYTHONPYCACHEPREFIX=<seat scratch>` (#647) for every gate seat and tells it to probe
from a copy under its scratch directory; `dispatch receive` warns when the worktree has
untracked files after a gate round and names them; the sentinel charters carry the rule.

## Root cause

Reproduced read-only on `main` (no dry-run workspace is named for this issue; see
Assumptions). A temporary tree with `pkg/mod.py` and `python3 -c "import pkg.mod"` run in it
leaves `pkg/__pycache__`; the same import with `PYTHONDONTWRITEBYTECODE=1`, with
`PYTHONPYCACHEPREFIX=<scratch>/pycache`, or with both leaves nothing in the tree (the prefix
alone writes the bytecode under the prefix; with both, nothing is written at all). Python
writes bytecode next to the source by default, so any gate probe that imports the item's
code or runs its tests inside the worktree leaves files there.

- `charters/_common.md:18` (Evidence and gates, rule 2) keeps only mutation out of the
  worktree ("Mutate only a whole-tree detached copy at that sha in scratch, never the
  builder's worktree"). A probe, a baseline test run or a reproduction may still run in the
  builder's worktree, and `charters/_common.md:10` (Write boundary, rule 1) does not say a
  sentinel's commands must leave the worktree untouched.
- `cli/wuwei/brief.py:422-426` (`write`): every brief gets the #647 `Scratch:` line, but no
  gate brief names an environment that keeps bytecode out of the worktree, and no line tells
  a gate seat to probe from a copy. `gate` is already known at `brief.py:383`.
- `cli/wuwei/dispatch.py:664-673` (`receive`): the brief's `Worktree:` is read only to
  compare HEAD; the worktree's status is never read, so a file a probe left is not reported
  when the verdict is received. It surfaces only later: the next gate brief refuses with
  `gate brief on a dirty tree` (`brief.py:453`, `brief.py:553`), or never, when the
  repository ignores `__pycache__` (git status omits ignored files).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: How does a brief "set" an environment variable? A: It cannot set the seat's process
  environment; a Claude seat is a subagent of the planner and a Codex seat runs through its
  companion. The brief names the exact prefix in a `Probe env:` header line and tells the
  seat to put it on every command that runs code. The brief is the one spot every gate seat
  launch reads, Claude or Codex, first opinion or second.
- Q: Which scratch path goes in `PYTHONPYCACHEPREFIX`? A: The concrete workspace one from
  #647, `<workspace>/.wuwei/scratch/<item>/<role>/pycache`, shell-quoted. WUWEI does not
  know the host scratchpad's path, and `brief.write` already creates
  `.wuwei/scratch/<item>/<role>/`.
- Q: Which seats get the line? A: Gate seats only (`gate` true in `brief.write`: every
  `sentinel-*` role and a second opinion). The builder owns its worktree and runs its tests
  there.
- Q: What does `receive` report, untracked files only? A: Every path the VCS status of the
  brief's worktree lists at receive time, untracked or modified. A gate brief is refused on a
  dirty tree and the builder stands down during gates, so any path there at receive time
  appeared during the round; a mutant left in a tracked file is the worse case of the same
  leak and costs no extra code to report.
- Q: Does the warning block the verdict? A: No. `receive` records the verdict as today,
  exits 0, and prints one `warning:` line to stderr naming the paths. A status read that
  fails is exit 2 before anything is recorded, like the HEAD read beside it.
- Q: Where does the charter rule live? A: Once, in `_common.md` Write boundary rule 1,
  which already speaks to sentinels; every sentinel agent file is built from `_common.md`
  plus its role charter (`bin/wuwei agents build`), so all four sentinel agents carry it
  without four copies.

## User Scenarios and Testing

### User Story 1 - A gate brief keeps bytecode out of the worktree (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a gate brief (`arch`, `quality`, `security` or `goal`) for item `X`, **When**
   it is written, **Then** its header has exactly one line
   `Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<workspace>/.wuwei/scratch/X/sentinel-<role>/pycache; ...`
   that tells the seat to set it on every command that runs code and to run every probe,
   test and mutant in a copy of the worktree under its scratch directory, never in the
   worktree itself.
2. **Given** a probe that imports a module and runs with the `Probe env:` prefix in the
   worktree, **Then** no `__pycache__` appears in the worktree.
3. **Given** a builder, lead, steward or shepherd brief, **Then** it has no `Probe env:`
   line.

### User Story 2 - `dispatch receive` names what a round left (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a stopped sentinel whose brief names a worktree, and that worktree's status
   lists untracked files after the round, **When** `bin/wuwei dispatch receive` runs,
   **Then** it records the verdict as today, exits 0, prints the JSON on stdout, and prints
   one stderr line starting `warning:` that names the worktree and each path.
2. **Given** a clean worktree, **Then** `receive` prints nothing on stderr.
3. **Given** the status read fails, **Then** `receive` exits 2 with the reason and records
   nothing.

### User Story 3 - The sentinel charters carry the rule (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the charters, **Then** `_common.md` says once that a sentinel never writes in
   the builder's worktree and runs every probe, test and mutant in a copy under its
   `Scratch:` directory with the brief's `Probe env:` set, and each generated
   `agents/sentinel-*.md` contains that sentence.

### Edge Cases

- A workspace path with spaces: the `PYTHONPYCACHEPREFIX` value is shell-quoted so the line
  pastes as one assignment.
- A gate brief with no worktree cannot be written (`gate requires a worktree`), so every
  `Probe env:` line names an existing item scratch directory.
- A brief whose `Worktree:` is `none` skips the status read, as it skips the HEAD read
  today.
- A gitignored `__pycache__` is not in VCS status and is not reported by `receive`; the
  `Probe env:` line is what prevents it.

## Requirements

- **FR-001**: `brief.write` appends, for a gate brief only and right after the `Scratch:`
  line, `Probe env: PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<quoted scratch>/pycache;
  set it on every command that runs code, and run every probe, test and mutant in a copy of
  the worktree under your scratch directory, never in the worktree itself`.
- **FR-002**: `dispatch.receive` reads the VCS status of the brief's worktree with the
  existing `brief.status` helper, next to the HEAD read, and after the verdict is recorded
  prints `warning: <worktree> has files the gate round left: <paths>; ...` to stderr when
  the list is not empty. Return value, state, events and exit code are unchanged.
- **FR-003**: `charters/_common.md` Write boundary rule 1 gains the sentence of User Story 3;
  its version goes from 1.9.0 to 1.10.0; `bin/wuwei agents build` regenerates `agents/*.md`.
- **FR-004**: Docs: a `Gate probes` row in the "Seat briefs and the build loop" table of
  `docs/site/reference.md` naming the `Probe env:` line and the `receive` warning.

## Success Criteria

- **SC-001**: A gate seat that follows its brief leaves no `__pycache__` in the builder's
  worktree.
- **SC-002**: A file a gate round leaves in the worktree is named on the `receive` that
  ends that round, not discovered at the next gate brief's dirty-tree refusal.

## Assumptions

- No orchestrator notes file exists for #672 (`notes/672-full.md` is missing) and no
  dry-run workspace is named; the issue text is the input and the root cause was reproduced
  in a temporary directory and by reading the cited lines.
- Gate seats only get `Probe env:`. The issue says "every gate seat"; the builder runs its
  own tests in its own worktree and its leftovers are its to commit or ignore.
- `receive` reports every status path, not only untracked ones (see Clarifications); the
  issue's untracked case is a subset. Ignored files are not reported: listing them needs a
  new allowlisted git form (`--ignored`) in the VCS adapter, and the prevention line covers
  the bytecode case. Upgrade: add the ignored form if seats keep leaving ignored files.
- The warning is advisory: it does not refuse, park or raise a card, and it is not a guard,
  so no posture area, design 9.2 invariant or `tests/test_invariants.py` row is added.
- `.pytest_cache` and other tool caches are covered by the copy rule, not by a flag: a seat
  that probes in its copy leaves nothing in the worktree whatever the tool writes.
- The brief cannot enforce the environment; a seat that ignores the line is caught by the
  `receive` warning (for files git sees). A PreToolUse rewrite of the seat's command is not
  built.
- The rule has one home in `_common.md` (the charter tests pin one home per rule); the four
  `sentinel-*.md` role charters are not edited.
- The seat's own commands pass the guards: `protect_state.check_bash` returns `(0, '')` for
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<workspace>/.wuwei/scratch/A/sentinel-quality/pycache python3 -m pytest -q`
  and for `cp -R <tree> <workspace>/.wuwei/scratch/A/sentinel-quality/copy` (checked
  in-process; the #647 scratch exemption covers both).
