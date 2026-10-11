# Feature Specification: owner commands work from any configured repository

**Feature Branch**: `735-workspace-from-repo`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #735 (owner, 2026-10-10, item 63): the owner commands WUWEI prints
(`decide`, `drafts approve`) only work when the shell is already in the workspace. ziran is a
repository of the ziran-paper workspace, but from its checkout the CLI did not find the
workspace. Deliver: `find_workspace` also resolves from a checkout that a workspace's `repos`
table names, through a per-user index written by WUWEI (one workspace resolves, two is a
refusal naming both); every owner command WUWEI prints carries `--workspace <root>` (the
existing leading flag, read before the lookup); the status line and cards print the same
form.

## Root cause

Reproduced read-only on `main` (d3b7066) against the owner's real layout: the workspace root
`ziran-paper/` holds `.wuwei/`, and its `config.toml` configures `[[repos]] path = "."` and
`[[repos]] path = "../ziran"`, a sibling checkout.

1. **The lookup only walks up.** `cli/wuwei/workspace.py:311` `find_workspace` honours
   `WUWEI_WORKSPACE` (lines 313-322), then walks the start directory and its parents for a
   `.wuwei/` directory (lines 323-328) and otherwise raises `FileNotFoundError` (line 329).
   A sibling checkout has no `.wuwei/` above it, so `find_workspace(<github>/ziran)` raises
   `No .wuwei/ found from .../ziran`, while `find_workspace(<github>/ziran-paper)` returns
   the root. Nothing in WUWEI maps a configured checkout back to its workspace: the `repos`
   table is read only once a root is already known (`workspace.py:370`, inside `scope`).
2. **So every command fails there.** `cli/wuwei/__main__.py:66-73` calls `find_workspace()`
   for every command but `hook` and `init`; the command then calls it again and exits 2 with
   that message. `bin/wuwei status`, `bin/wuwei decide D-n <option>` and
   `bin/wuwei drafts approve <id>` all fail from `ziran/`.
3. **The guards miss it too.** `workspace.scope` (`workspace.py:353`) starts from the same
   lookup (line 362) and returns `None` for `ziran/` (reproduced:
   `scope(<github>/ziran) -> None`), although design spec 9.1 says a guard acts inside a
   workspace, "one of its configured repos", or a WUWEI worktree.
4. **The printed commands carry no workspace.** The owner-facing texts are fixed strings
   with no root: `cli/wuwei/decision.py:214` `RECORD = 'wuwei decide {id} "<label>"'`
   (decision cards), `cli/wuwei/drafts.py:194-215` (the draft card's record and options), `cli/wuwei/commands/decision.py:203,206,274,277`,
   `cli/wuwei/commands/status.py:220` and `cli/wuwei/commands/dashboard.py:106`. The leading
   `--workspace <path>` flag that would make them work from any folder already exists
   (`__main__.py:52-54`, #354) and the guards already read it (`protect_state._positional`,
   `commands.read_only`), but nothing prints it.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: The issue names `~/.wuwei/workspaces.json` for the index. Is that location safe? A: No.
  `find_workspace` treats any directory holding `.wuwei/` as a workspace root, so a
  `~/.wuwei/` directory would make the home folder the workspace of every path below it:
  every command and every guard under the home folder would load a workspace with no
  `config.toml` and fail closed. The index lives at `~/.config/wuwei/workspaces.json`
  instead (a folder named `wuwei`, not `.wuwei`).
- Q: Who writes the index? A: The two places that settle a workspace's repositories:
  `config.offer`, the one owner digest path every config write goes through (`config set`,
  `config add-repo`, `config promote`, `setup`, `outbound learn`, `grants revoke`, the draft
  tier rows), right where it already syncs the derived register (`graph.sync`); and
  `init --upgrade`, so an existing workspace (ziran-paper) is indexed by the next upgrade
  without a config edit. A fresh `init` has no repositories (the template's `repos` table is
  empty), so it writes no entry.
- Q: What does a checkout configured by two workspaces do? A: The lookup refuses: the error
  names both roots and says to pass `--workspace <path>` (or set `WUWEI_WORKSPACE`). It is a
  `FileNotFoundError` like the existing "no workspace" error, so every caller already
  handles it: a command exits 2 with the reason; a guard treats the path as outside any
  workspace, as it does today.
- Q: Which printed commands get `--workspace`? A: The owner commands the owner named,
  `decide` and `drafts approve` / `drafts drop`, at every place WUWEI prints one with a
  concrete id for the owner on a local surface: decision cards, the draft card, the `decide` refusals and undo replies, the phone-answer nudge,
  and the dashboard's approve command. See Assumptions for what stays as it is.
- Q: Does the status line change? A: The status line prints no command (it shows
  `decision D-n waiting`), so its text has nothing to carry. With the index, the status line
  command (`<executable> status --line`) finds the workspace when Claude Code runs it in a
  configured checkout. The `statusLine` setting `init` writes is not changed: pinning
  `--workspace` there would pin every project once the owner copies it into the user-wide
  settings. The status nudge that names a `decide` command (the phone answer) carries the
  flag.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - the CLI finds the workspace from a configured checkout (Priority: P1)

The owner works in a repository checkout that a workspace configures but that is not inside
the workspace folder (`ziran/` beside `ziran-paper/`). Every WUWEI command run there uses that
workspace, as if run in the workspace root.

**Why this priority**: it is the owner's failure; it fixes every command at once, printed or
typed.

**Independent Test**: a workspace `ws/` whose config names `../repo`, indexed through
`config add-repo` (or `init --upgrade`); from `repo/`, `find_workspace()` returns `ws/` and
`bin/wuwei status` exits 0.

**Acceptance Scenarios**:

1. **Given** a shell in a configured repository's checkout outside the workspace folder,
   **When** the owner runs `bin/wuwei status`, **Then** it reads that workspace and exits 0;
   and `bin/wuwei decide D-n <option>` as printed works from there.
2. **Given** two workspaces whose configs both name the same checkout, **When** a command
   runs in that checkout, **Then** it exits 2 and the reason names both workspace roots and
   the `--workspace` flag.
3. **Given** a workspace `ws/`, **When** `config add-repo` adds `../repo` (or
   `init --upgrade` runs on a workspace that already configures it), **Then** the per-user
   index maps `ws/` to the resolved `repo/` path.

---

### User Story 2 - every owner command WUWEI prints carries --workspace (Priority: P1)

Wherever WUWEI prints a `decide`, `drafts approve` or `drafts drop` command
with a concrete id for the owner to run, the command reads
`bin/wuwei --workspace <root> <command>`, so it works when pasted into a terminal in any
folder.

**Why this priority**: the owner copies these commands; they must work wherever the terminal
is.

**Independent Test**: build a decision card, a draft card and the `decide` refusal for a
workspace at `tmp_path`; each command text starts with `bin/wuwei --workspace <tmp_path>`.

**Acceptance Scenarios**:

1. **Given** a printed owner command (decision card record, draft card record and
   options, the `decide` host-terminal refusals, the undo replies, the
   phone-answer nudge, the dashboard approve command), **Then** it contains
   `--workspace <root>` right after `bin/wuwei`.
2. **Given** that command, **When** it is run from a folder outside any workspace, **Then**
   it acts on that workspace (the existing leading flag, #354).

---

### User Story 3 - the guards cover a configured checkout (Priority: P2)

A guard acting on a path inside a configured sibling checkout uses that checkout's workspace,
as design spec 9.1 already states.

**Independent Test**: with the index written, `workspace.scope(<repo>)` returns the
workspace root and config.

**Acceptance Scenarios**:

1. **Given** an indexed workspace that configures `../repo`, **When** `scope(<repo>/x)` runs,
   **Then** it returns that workspace; for a checkout configured by two workspaces it
   returns `None` (outside, as today).

### Edge Cases

- No index file, an unreadable one, invalid JSON, or entries of the wrong shape: the lookup
  ignores the index and raises today's "No .wuwei/ found" error. A damaged per-user file
  must never fail every hook on the machine.
- An indexed root whose `.wuwei/` is gone or is a symlink: that entry is skipped.
- The start path is inside the workspace folder: the parent walk finds it first; the index
  is read only after the walk fails, so it never overrides a containing workspace.
- `WUWEI_WORKSPACE` or `--workspace` set: it wins as today; the index is not read.
- A repository path that resolves to the workspace root itself (`path = "."`), to the home
  folder or to one of its parents (`path = "~"`): not indexed. The root is found by the walk,
  and indexing the home folder would put every path under it in that workspace.
- A repository removed from the config: its entry goes on the next config write or upgrade
  (the writer replaces the root's whole entry). Until then a stale entry can resolve the
  CLI to that workspace; `scope` still checks the live `repos` table before a guard acts.
- Two `init --upgrade` runs or config writes for different workspaces at the same moment:
  the last atomic write wins and the other entry returns on that workspace's next write
  (`ponytail:` ceiling, no lock).
- A workspace root with a space in its path: the printed `--workspace` value is shell-quoted.
- `config.offer` or `init --upgrade` cannot write the index (read-only home): a warning,
  never a failed config write or upgrade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `workspace.find_workspace`, after the `.wuwei/` parent walk finds nothing,
  reads the per-user index `~/.config/wuwei/workspaces.json` and collects the workspace
  roots whose indexed checkouts contain the start path and whose `.wuwei/` is a real
  directory (not a symlink). One root: it is returned. Two or more: `FileNotFoundError`
  naming every root and `--workspace <path>`. None: today's error, unchanged.
- **FR-002**: `WUWEI_WORKSPACE` (and the leading `--workspace` flag that sets it) and the
  parent walk keep their precedence over the index.
- **FR-003**: A missing, unreadable or malformed index is treated as empty; reading it never
  raises.
- **FR-004**: `workspace.index(root, config)` writes the root's entry: the sorted, resolved
  paths of its configured repositories, without the root itself and without the home folder
  or its parents; an empty list removes the root's entry. Other roots' entries are kept. The
  write is atomic (`workspace.atomic_write`).
- **FR-005**: `config.offer` calls `workspace.index` after a changed config is written;
  `init --upgrade` calls it outside `--dry-run`. A failure to write the index prints a
  warning and changes neither exit code.
- **FR-006**: `workspace.owner_cli(root)` returns `bin/wuwei --workspace <shell-quoted
  root>`; it is the one place that prefix is built, and every FR-007 site uses it.
- **FR-007**: These texts carry the FR-006 form: the decision card record
  (`decision.RECORD`) through `decision.record_widget`;
  the draft card's record and its `drafts approve --file`, `drafts approve --always` and
  `drafts drop` option texts (`drafts.widget`); the `decide` host-terminal refusals and the
  undo replies in `commands/decision.py`; the phone-answer nudge in `commands/status.py`;
  the dashboard's `approve_command`.
- **FR-008**: `workspace.scope` resolves a configured sibling checkout through the same
  lookup (no code of its own), so guards act there as design spec 9.1 states.

### Key Entities

- **Workspace index**: `~/.config/wuwei/workspaces.json`, a JSON object mapping each
  workspace root (absolute, resolved) to the sorted list of its configured checkout paths
  (absolute, resolved). Written only by `workspace.index`; read only by `find_workspace`. It
  is a lookup aid, not a trust anchor: `scope` re-checks the live `repos` table, and an
  entry can only resolve to a root that holds a real `.wuwei/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a configured checkout outside the workspace folder, `bin/wuwei status`
  exits 0 and `bin/wuwei decide` reaches the workspace (test, US1).
- **SC-002**: A checkout configured by two workspaces makes a command exit 2 with both roots
  and `--workspace` in the reason (test, US1).
- **SC-003**: Every FR-007 text contains `--workspace <root>` (tests, US2).
- **SC-004**: No existing workspace-lookup test changes its expectation (env override,
  nearest workspace, missing workspace), and the full suite passes.

## Assumptions

- The orchestrator notes for this issue (`735-full.md`) did not exist when this spec was
  written; the scope comes from the issue and the owner's item 63. The reproduction used a
  read-only `find_workspace` / `scope` call against the owner's real workspace, no CLI run.
- The index location deviates from the issue (`~/.config/wuwei/` instead of `~/.wuwei/`)
  for the reason in Clarifications. `XDG_CONFIG_HOME` is not honoured: the test suite
  isolates only `HOME` (`tests/conftest.py`), so honouring it could write a developer's real
  config from a test.
- The index is written by `config.offer` and `init --upgrade`, not by a fresh `init`
  (Clarifications). The owner's ziran-paper workspace is indexed by its next
  `bin/wuwei init --upgrade` or config edit.
- The printed form keeps the `bin/wuwei` program word every other owner text uses; how the
  owner runs `bin/wuwei` (alias, PATH, the `.wuwei/executable` path) is unchanged.
- Outside the FR-007 set, unchanged: the daily report's `reverse: bin/wuwei decide` line and
  the docs close line (`docs.findings`), because the report can be published outward and an
  absolute local path must not go with it; the guard reason templates in
  `protect_state._OWNER_ACTIONS` (they use `<id>` placeholders and have no root at hand) and
  its "Run it in a host terminal" echo of the planner's own command; the strict-only ticket
  texts in `tracker.check` and `tracker._held`; the `mcp decide` texts (`mcp.RECORD`,
  `mcp.command` and the launch gate's waiting line, used by status, doctor, setup and the
  dashboard), a family of its own the owner did not name; and every other owner command
  group. All of
  them work from any configured checkout through the index (US1), and from anywhere else the
  "No .wuwei/ found" error already names `--workspace <path>`.
- The `--workspace` flag itself is unchanged: leading position only, consumed before the
  lookup (#354). No trailing or per-command form is added.
- FR-008 adds no guard rule and changes no decision rule: it makes the guard scope match
  what design spec 9.1 already says, so no new 9.2 invariant row is added.
