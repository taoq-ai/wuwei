# Feature Specification: the same doctor answer from either install

**Feature Branch**: `645-doctor-either-install`

**Created**: 2026-10-10

**Status**: Draft

**Input**: GitHub issue #645, "fix(doctor): the same answer from either install: doctor and the
hooks read the workspace's executable pointer, not the copy that happens to run, and the brief
tells seats which doctor to trust". Companion to #601 (two installs named by doctor).

## Root cause (reproduced)

Reproduced read-only on 2026-10-10 with two copies of release 0.24.1 on one machine (the
marketplace directory and the plugin cache, the cache registered in Claude Code) and a scratch
workspace created by the cache copy, so `.wuwei/executable` names the cache launcher. `doctor
--json` ran from each copy and the Install and Workspace rows were compared:

| Row | From the cache copy | From the marketplace copy |
|-----|---------------------|---------------------------|
| `hooks` | ok, registered in Claude Code | fail, not listed in installed_plugins.json |
| `executable` | ok | fail, "<cache> is not <marketplace>", fix `<marketplace>/bin/wuwei init --upgrade` |
| `template` | ok, current | warn, 1 change, fix `init --upgrade` |
| `plugin`, `launcher` | the cache path | the marketplace path |
| every `fix:` | names the cache launcher | names the marketplace launcher |

That is the owner's report: a builder read "hooks not in installed_plugins.json, executable
pointer stale" and told the owner to run `init --upgrade`. Run from the marketplace copy, that
rewrites the pointer to the marketplace copy, so it flips again.

The cause is one constant. Every doctor row is computed from `integrity.PLUGIN`
(`cli/wuwei/integrity.py` line 12, `Path(__file__).resolve().parents[2]`), the copy that
happens to run:

- `cli/wuwei/commands/doctor.py` `_install` (lines 92 to 135): the plugin, integrity, in_use and
  launcher rows read `integrity.PLUGIN`.
- `doctor.py` `_hooks` (line 151): registration is matched against `integrity.PLUGIN`.
- `doctor.py` `_workspace` (lines 259 to 271): the executable row compares the pointer with
  `integrity.PLUGIN / 'bin/wuwei'`, and its fix is `init --upgrade`, which writes the running
  copy (`cli/wuwei/commands/init.py` line 381, `executable = plugin / 'bin/wuwei'`).
- `doctor.py` `_row` (lines 47 to 49): every fix is rewritten to name
  `integrity.PLUGIN / 'bin/wuwei'`.

#601 (committed and reviewed, not yet on main) fixes three of these at their shared spots:
`_hooks` finds the registration from either launcher (`integrity.registered`), the executable
row and `init` compare with and write the registered launcher (`integrity.launcher`), and a new
`installs` row names every copy in play. It does not make the answer independent of the copy:
the `plugin`, `launcher` and `installs` rows and every fix line still come from
`integrity.PLUGIN`, and the integrity rows (`integrity.fresh`, `integrity.restart`) walk the
running copy's files and markers. Threading a second plugin path through `integrity` would touch
nearly every function in it. The one place all of this routes through is the process: the
doctor that runs is the copy that was invoked.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One doctor answer whichever copy is invoked (Priority: P1)

The owner or a seat runs `doctor` with whatever launcher is at hand: the marketplace directory,
the plugin cache, a release extraction. When the workspace's `.wuwei/executable` names another
runnable install, doctor runs from that install instead, so the rows and every fix are the ones
that install computes. The report adds one row naming the copy that was invoked, the copy that
reported, and the copy that last measured the workspace from a hook.

**Why this priority**: a doctor whose findings depend on the launcher sends seats and the owner
down the wrong fix (`init --upgrade` from the wrong copy flips the pointer).

**Independent Test**: two plugin directories, the workspace pointer names the first, doctor run
in-process as the second: it hands over to the first with the same options. The first, told
which copy invoked it, returns the rows it returns when invoked directly plus the one row.

**Acceptance Scenarios**:

1. **Given** two installs and a workspace pointer to one, **When** `doctor` runs from either
   copy, **Then** it prints the same findings, plus one line naming the invoked copy when it
   differs from the pointer (issue acceptance 1).
2. **Given** the pointer names the invoked copy, **When** `doctor` runs, **Then** nothing is
   handed over and no extra row is printed (today's behaviour).
3. **Given** the pointer is missing, empty or not executable, or there is no workspace, **When**
   `doctor` runs, **Then** it reports from the invoked copy as today; the executable row already
   names the broken pointer and its fix.
4. **Given** `doctor --json`, `--fix`, `--fix --widget`, `--fix --apply <ids>` or `--section
   pr-flow` from the other copy, **When** it hands over, **Then** the install named by the
   pointer runs with the same options, and `--json` output stays one JSON document with the
   extra row in `rows`.
5. **Given** the hand-over itself fails (the pointer names an executable that cannot be run),
   **When** `doctor` runs, **Then** it reports from the invoked copy and adds a warn row naming
   the pointer, the error class and that this report comes from the invoked copy.

---

### User Story 2 - The seat brief names the doctor to trust and who owns install findings (Priority: P2)

A seat reads doctor output and turns an install finding into a `Next:` step. Every seat brief
carries one line: run doctor through the launcher `.wuwei/executable` names, and an install
finding (the Install section and the workspace executable row) is the owner's, reported in the
handoff, never a `Next:` step for a seat and never a fix the seat runs.

**Why this priority**: the hand-over makes the answer consistent; the brief line stops a seat
from acting on an install finding at all.

**Independent Test**: write a builder brief and a sentinel brief; both headers contain the line.

**Acceptance Scenarios**:

1. **Given** a seat brief of any role, **Then** its header names the doctor command and the
   install rule (issue acceptance 2).

### Edge Cases

- The pointer names the invoked copy through a different spelling (symlinked directory, `..`):
  compared after `resolve()`, so no hand-over.
- The handed-over doctor sees the invoked-copy marker and never hands over again (no loop).
- The install named by the pointer is an older release without this change: it prints its own
  findings without the extra row. Both copies still print the same findings, because both run
  that install's doctor.
- The integrity verdict is missing, unreadable or has no `plugin`: the row says the hooks' copy
  is unknown.
- In-process callers (`setup` through `doctor.diagnose`, tests through `doctor.run` with a
  `confirm` callback) never hand over.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `doctor.run` MUST hand over when all hold: no `confirm` callback was passed, the
  invoked-copy marker is not set, a workspace is found, and its `.wuwei/executable` names an
  executable file that is not the running launcher after `resolve()`. Hand-over replaces the
  process with that launcher running `doctor` with the same options and sets the invoked-copy
  marker to the running launcher's path.
- **FR-002**: When the invoked-copy marker is set and names a launcher other than the running
  one, doctor MUST add one `ok` row (section `install`, name `invoked`) naming the invoked copy,
  the reporting copy (the one `.wuwei/executable` names), and the copy that last measured plugin
  integrity for the workspace (the `plugin` field of `.wuwei/integrity/verdict.json`, which the
  SessionStart hook writes), or "unknown" when the verdict has none. The row MUST NOT change the
  exit code.
- **FR-003**: When the hand-over fails with `OSError`, doctor MUST report from the invoked copy
  and add one `warn` row (section `install`, name `invoked`) naming the pointer and the error
  class, with the fix to run the launcher in `.wuwei/executable` with `doctor` directly.
- **FR-004**: Every seat brief header MUST carry one `Doctor:` line naming the doctor command
  (the launcher in `.wuwei/executable` with `doctor`) and the rule that Install section findings
  and the workspace executable row are the owner's: reported in the handoff, never a `Next:`
  step for a seat, never a fix the seat runs.
- **FR-005**: `docs/site/reference.md` (Doctor) MUST state the hand-over and the extra row in
  one or two sentences.

### Key Entities

- **Invoked-copy marker**: the environment variable `WUWEI_DOCTOR_FROM`, set only on the
  handed-over process, holding the launcher path that was invoked. Informational: nothing
  trusts it beyond the extra row and the no-second-hand-over rule.
- **Hooks' copy**: the `plugin` field of `.wuwei/integrity/verdict.json`, written by
  `integrity.check` (the SessionStart hook, `integrity check`, `init`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For two installs and one pointer, the doctor rows from either copy are identical
  except for the one `invoked` row (asserted in a test).
- **SC-002**: Every seat brief, whatever its role, contains the `Doctor:` line (asserted for a
  builder and a sentinel brief).
- **SC-003**: The full suite passes; no existing doctor test changes its expectations.

## Assumptions

- #601 lands on main before this is built and provides `integrity.recorded(root)`. If it has
  not, the builder adds `integrity.recorded` exactly as #601 defines it (five lines) so the merge
  is trivial, and notes it under Deferred. Why: the issue calls this a companion to #601, which
  is committed and reviewed. What would overturn it: #601 dropped; then `recorded` stays here.
- Hand-over replaces the process (`os.execve`) instead of computing every row for another
  install in-process. Why: `integrity.PLUGIN` is read by nearly every `integrity` function, and
  only running the named install's own code gives the same answer by construction, also across
  versions. `os.execve` is not `subprocess`, so the core rule (no `subprocess` import under
  `cli/`) holds. What would overturn it: a host where the launcher cannot be executed; FR-003
  covers that case.
- Executing the path in `.wuwei/executable` adds no trust: the git hooks
  (`commands/git_hook.py`) and the SwiftBar plugin already execute it, `init` refuses a
  symlinked pointer, and `guards/protect_state.py` refuses seat writes to it.
- "Which one the hooks run" is read from the hooks' own evidence, the integrity verdict the
  SessionStart hook writes, not from `installed_plugins.json`. The owner's report of 2026-10-10
  (problem 70) shows a hook running from the marketplace directory while
  `installed_plugins.json` names the cache, so the registration is not proof of which copy runs.
  The verdict is also rewritten by `integrity check` and `init`, so the row says "last
  measured", not "runs".
- The `installs` row of #601 and its fix text are not changed here. Adding the hooks' copy to
  that row, and choosing the canonical install for a directory marketplace, belong to problem 70
  and its own issue.
- The traces guard (`cli/wuwei/guards/traces.py`) is not changed: #601 already names the
  executable mismatch in its failure reason. Hooks keep running from the copy Claude Code
  starts; handing a hook over to another copy would cost a second interpreter start on every
  tool call against the hook latency budget.
- The brief line is a constant (no file read at brief time): with the hand-over, any copy's
  doctor gives the pointer's answer, so the line is guidance, not a correctness need.
- `setup` and other in-process callers of `doctor.diagnose` keep reporting from the running
  copy; the issue names the `doctor` command.
