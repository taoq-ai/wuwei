# Feature Specification: wuwei doctor finds every problem in the install, host, workspace, gates, day and guards, and fixes the deterministic ones in one confirmed batch

**Feature Branch**: `339-doctor`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #339, "feat(cli): wuwei doctor: find every problem in the install,
host, workspace, gates, day and guards, and fix the deterministic ones in one confirmed
batch". Owner request after the v0.11.0 first-run trial (2026-10-03): "perhaps we can also
have like wuwei doctor? To find out problems?". Relayed owner instruction for this run:
find and fix, not only find. Depends on #324, #325, #326 (exact fix lines); builds after
#327 (setup calls doctor), #328 and #329 in the same chain.

## Root cause (read and reproduced on main, 4a384c5)

The trial needed four to six owner round trips per problem because no command says what
is wrong and how to fix it. Each check that exists covers one area and stops there:

- `cli/wuwei/__main__.py:42-52` registers one subcommand per module in
  `cli/wuwei/commands/`; there is no `doctor` module. Reproduced read-only in the trial
  workspace: `bin/wuwei doctor` exits 2 with `invalid choice: 'doctor'`.
- `cli/wuwei/heartbeat.py:116-142` (`measure`) runs ten liveness probes for the watch tick.
  It has no install, host, repository, MCP or branch protection rows and prints no fix.
  It must stay cheap (#287), so it is not the place to grow.
- `cli/wuwei/commands/config.py:26-30` returns at the first `ConfigError`; nothing after it
  (credentials, protection, seat tokens) is shown, and nothing else in the workspace is
  examined.
- `cli/wuwei/commands/integrity.py:12-16` prints one verdict line. On the trial that line
  was `page: plugin integrity: .in_use/15760`; nothing said the markers are Claude Code's
  own or which command clears them. The same defect (#324: `cli/wuwei/integrity.py:39`
  and `:213` prune only `.git` and `__pycache__`) was live in this spec session: the
  installed v0.11.0 plugin refused a `Read` with `page: plugin integrity: .in_use/15760;
  .in_use/16824`.
- `cli/wuwei/commands/mcp.py:16-26` prints the gate reason only; per-server state lives in
  `.wuwei/ziran/status.json` (`cli/wuwei/mcp.py:166-187`) and no command lists it.
- `cli/wuwei/commands/status.py:31-187` (`scan`) knows the watch, the listener, the
  heartbeat, pages and pending decisions, but only feeds the status line and the board.

So the fix is composition: one owner-run command that calls these existing checks, adds
the install and host rows nothing measures today, and attaches the fix to every row.

## User Scenarios & Testing

### User Story 1 - One command names every problem and its fix (Priority: P1)

The owner runs `bin/wuwei doctor` in the workspace. It prints six sections (Install, Host,
Workspace, Gates and adapters, Day and sessions, Guards). Every row is `ok`, `warn`,
`fail` or `unmeasured` with the measured value; every row that is not `ok` carries the
exact command or edit that fixes it and a docs link. It writes nothing.

**Why this priority**: it is the trial's whole complaint; every later story builds on the
rows.

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k "trial or healthy"`.

**Acceptance Scenarios**:

1. **Given** a fixture workspace with the trial's five failures (a pre-#324 `.in_use`
   integrity finding, `repos = []` next to a `[[repos]]` table, an approved MCP server the
   registry could not measure, an empty `fast_checks`, a classic branch protection 404 with
   no rules), **When** `doctor` runs, **Then** it exits 1 and reports the integrity row with
   `wuwei integrity reconfirm` and the config row with the #326 hint and
   `wuwei init --upgrade`; the rows that need a loading config say so as `unmeasured`.
   **When** the config fix is applied and `doctor` runs again, **Then** it exits 1 and
   reports the MCP row with `wuwei mcp decide proceed-unmeasured <server>`, the
   `fast_checks` row with `wuwei config promote`, and the `config check` row carrying the
   `classic protection: none visible ...` and `required reviews: missing (...)` lines.
   **When** every printed fix is applied, **Then** `doctor` exits 0.
2. **Given** a healthy workspace, **When** `doctor` runs, **Then** every row is `ok` (a row
   that does not apply, such as the listener with `adapters.inbound = "none"`, is `ok` with
   the reason) and the exit is 0.
3. **Given** a workspace whose MCP record notes a server that is not attached (unapproved),
   **When** `doctor` runs, **Then** that server is an `ok` row reading
   `not attached (unapproved)`.

### User Story 2 - `--fix` applies the deterministic fixes after one confirmation (Priority: P1)

The owner runs `bin/wuwei doctor --fix` in a host terminal. Doctor diagnoses, collects the
rows whose fix is on its allow list, shows each fix's exact preview as one batch, asks for
one typed digest on `/dev/tty`, applies the batch, records one `doctor.fixed` event per
applied fix, then diagnoses again and prints the result. Fixes that are decisions stay
printed commands with their reason.

**Why this priority**: the relayed owner instruction is "find and fix"; without it the
owner still types every command.

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k fix`.

**Acceptance Scenarios**:

1. **Given** a development checkout whose integrity verdict asks for reconfirmation,
   **When** `doctor --fix` runs and the owner types the batch digest, **Then** the batch
   shows `wuwei integrity reconfirm` with the installation fingerprint, the confirmation is
   recorded, a `doctor.fixed` event `{"fix": "integrity-reconfirm", "exit": 0}` is
   appended, and the second diagnosis has an `ok` integrity row.
2. **Given** rows whose fix is a decision (`mcp decide`, `guards.mode`, `state recover`) or
   an id not on the allow list, **When** `doctor --fix` runs, **Then** none of them is
   applied; each is printed under `Not applied` with its reason.
3. **Given** the owner types a wrong digest, **When** `doctor --fix` runs, **Then** nothing
   is applied, no event is written and the exit is 1.
4. **Given** no terminal (`/dev/tty` cannot be opened, as in a seat), **When**
   `doctor --fix` runs, **Then** nothing is applied and it exits 2 with
   `this is an owner action: run it in a host terminal`.
5. **Given** the value a fix previewed changed before it ran (a different fingerprint,
   digest or dry-run plan), **When** the batch applies, **Then** that fix is not applied,
   it is reported as changed since the preview, and the other fixes still run.

### User Story 3 - Doctor works before there is a workspace (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k no_workspace`.

**Acceptance Scenarios**:

1. **Given** a directory with no `.wuwei/` above it, **When** `doctor` runs, **Then** the
   Install and Host sections still run, the Workspace section has one `fail` row saying
   where to run `wuwei setup --shadow`, the Guards section runs only the
   outside-workspace probe, and the exit is 1.

### User Story 4 - Machine-readable output and entry points (Priority: P3)

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k json tests/test_docs.py`.

**Acceptance Scenarios**:

1. **Given** any workspace, **When** `doctor --json` runs, **Then** stdout is one JSON
   object `{"exit": <0|1|2>, "rows": [...]}` with one object per row, and the process
   exit equals `exit`.
2. **Given** `doctor --fix --json`, **Then** it exits 2 with a usage message and changes
   nothing (the confirmation needs a terminal).
3. **Given** the docs, **Then** `reference.md` lists `bin/wuwei doctor` in Commands and has
   a Doctor section with the fix allow list; `recovery.md` and `daily.md` point to doctor
   first.
4. **Given** `wuwei setup` from #327 on main, **Then** its last step prints the doctor
   report.

### Edge Cases

- `config.toml` does not load: Install, Host, the config row and the template drift row
  still run; the repository, calibration, Gates and Day rows collapse to one `unmeasured`
  row per section reading `config.toml does not load`.
- Today's state is unreadable: the state row is `fail` with `wuwei state recover` (an
  owner action, printed only); the rest of the Day section is one `unmeasured` row.
- Two repositories with an empty `fast_checks`: two rows, one `config promote` in the
  batch (fixes are de-duplicated by id).
- A development checkout with a dirty tree: the integrity row fails with the existing
  "restore a clean commit" reason; `--fix` previews it as not appliable instead of
  reconfirming.
- A heartbeat probe times out: that row is `unmeasured` with `timeout`.
- Doctor itself raises: exit 2 through the CLI's three-state wrapper.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei doctor [--fix | --json]` is an owner-run CLI command. Without `--fix`
  it writes no workspace file and appends no event (the heartbeat probe's `state.lock` and
  today's directory are the only side effects, as for `wuwei heartbeat`).
- **FR-002**: Rows are grouped in this order: Install, Host, Workspace, Gates and adapters,
  Day and sessions, Guards. Each row has `section`, `name`, `status`
  (`ok|warn|fail|unmeasured`) and `value`; every non-ok row has a `fix` and a `docs` link;
  a row whose fix is on the allow list also has `apply` (the fix id).
- **FR-003**: Exit 1 when any row is `warn` or `fail`; else 2 when any row is
  `unmeasured`; else 0. A row that does not apply to this configuration is `ok` with the
  reason, never `unmeasured`.
- **FR-004**: Doctor composes existing checks and re-implements none: `heartbeat.measure`
  (once), `integrity.measure` (no workspace only), `workspace.load_config`, `init.upgrade`
  with `dry_run=True`, `commands.config.run`, the MCP registry record and `mcp.cached`,
  `status.scan`, `interview.load`, `profiles.load`, and the VCS, code host and host
  adapters.
- **FR-005**: Install rows: plugin path and version; signed release or development
  checkout; integrity verdict; `.in_use` markers counted as expected, never a finding;
  `hooks/hooks.json` valid and the plugin listed in Claude Code's installed plugins;
  `bin/wuwei` executable; Python 3.11 or newer.
- **FR-006**: Host rows: `gh` on PATH and authenticated; git identity; ZIRAN on PATH when
  `adapters.scanner = "ziran"`; the Claude Code CLI on PATH when an inbound source is
  configured; Codex on PATH when selected; free memory against `host.free_memory_mb`;
  launchd or systemd present.
- **FR-007**: Workspace rows: where `.wuwei/` is; `config.toml` loads (the error with the
  #326 hint on failure); template drift from `init --upgrade --dry-run`; per repository:
  path exists, is a git repository, default branch exists locally, identity set,
  `fast_checks` filled; calibration applied and when; calibration drift flagged today;
  interview answers today; guard profile and calibration profile in effect; shadow days
  left.
- **FR-008**: Gates and adapters rows: one row for `config check` (its exit, with its
  printed lines as detail; they carry credentials by name, the control plane and branch
  protection per repository); the MCP gate from `mcp.cached`; one row per server the
  record names (unmeasured, decided by the owner, not attached).
- **FR-009**: Day and sessions rows: day state readable, planner live, watch and listener
  health and whether their units are installed, the last heartbeat health, one row per
  open page, and the count of open nudges.
- **FR-010**: Guards rows: the heartbeat hook probes `refused`, `allowed`, `state_write`
  and `status_line`, plus one probe that runs `bin/wuwei hook PreToolUse` from a directory
  outside any workspace with a heredoc Bash command mentioning `gh`, which must exit 0
  (#323).
- **FR-011**: `--fix` applies only fixes on the allow list: `integrity-reconfirm` (only
  for a development checkout), `init-upgrade` (template drift and the #326 `repos = []`
  repair), `config-promote` (an empty `fast_checks`), `calibrate` (calibration drift
  flagged today), `watch-install`, `listen-install`, and `config-set` (a repository
  identity, or a default branch, that discovery resolved, through #327's `config set`).
  The table is a constant with a test pinning its keys.
- **FR-012**: `--fix` previews every fix first (the command's own dry run, or a declined
  confirmation that reveals its digest), shows them as one batch, and applies them only
  after the owner types the batch digest at `integrity._host_confirm`. Each fix's own
  confirmation is bound to the value its preview showed, so a change between preview and
  apply refuses that fix.
- **FR-013**: Every applied fix appends one `doctor.fixed` event `{fix, exit}`; the kind is
  listed in `EVENT_PRODUCERS`, so `wuwei event` refuses it.
- **FR-014**: After applying, `--fix` diagnoses again and prints that report; its exit is
  the command's exit, so a fix that did not take is named.
- **FR-015**: `--json` prints `{"exit", "rows"}`; `--fix` with `--json` exits 2.
- **FR-016**: Doctor is never imported on a hook path.
- **FR-017**: Docs: a `reference.md` Commands row and a Doctor section (rows, exit, the fix
  allow list); `recovery.md` and `daily.md` name `bin/wuwei doctor` first.

### Key Entities

- **Row**: `{section, name, status, value, fix, apply, docs, detail}`; `detail` is a list
  of lines (the `config check` output) and is omitted when empty; `fix`, `apply` and
  `docs` are omitted on `ok` rows.
- **Fix**: an allow-list entry: id, the command text shown to the owner, a preview that
  returns the text to show and the value to bind, and an apply that runs the existing
  command bound to that value.

## Success Criteria

- **SC-001**: On the trial's five failures the owner reaches a clean `doctor` with at most
  two `doctor --fix` runs plus the printed decisions, instead of four to six round trips
  per problem.
- **SC-002**: A healthy workspace exits 0 with every row `ok`.
- **SC-003**: No fix outside the allow list is ever applied, and nothing is applied
  without the typed digest.

## Assumptions

- Dependencies land first, as the issue orders: #324 (`.in_use` pruned, so a real marker
  is no longer a finding), #325 (on main: per-server record, `mcp decide
  proceed-unmeasured`), #326 (the hint `repos is assigned on line N; delete that line
  before using [[repos]] tables` from `load_config`, and `init --upgrade` removing the
  line), #328 (`config promote` fills a one-line `fast_checks = []`), #329 (the
  `classic protection: none visible (404: unprotected or no admin)` row) and #327
  (`wuwei setup`, `wuwei config set`). Doctor matches their printed text and re-implements
  none of them. If #327's `config set` is absent at build time, the `config-set` fix stays
  a printed command and goes under Deferred.
- The acceptance fixture's "`.in_use` marker before #324" is simulated by faking the
  integrity probe with the reason the trial printed, because after #324 a real marker is
  clean; a separate test places a real `.in_use/12345` and expects an `ok` markers row.
- The acceptance fixture's "unapproved MCP server" is read as the trial's B2 failure in
  its post-#325 form: an approved server the registry could not measure (fix:
  `wuwei mcp decide proceed-unmeasured <server>`, a decision, so printed only). A server
  that is truly unapproved is `ok`, `not attached (unapproved)`.
- "Every line is ok or an explained unmeasured and the exit is 0" is met by printing
  not-applicable rows as `ok` with the reason. A row that tried to measure and could not
  stays `unmeasured` and exits 2, per constitution principle II.
- Doctor reads the MCP record (`.wuwei/ziran/status.json`) and does not run `mcp check`:
  the check launches servers and writes the record, which is not read-only. With no record
  for today and servers to check, the row is `unmeasured` with `wuwei mcp check`.
- Doctor runs `config check` in process because the issue asks for its lines; that makes
  the same `gh` reads `config check` makes. Doctor makes no other network call.
- The `gh` account login is not shown: `auth_status` deliberately keeps `gh` output out of
  WUWEI, so the row says `authenticated`. The ZIRAN version is not re-measured: the row
  checks ZIRAN is on PATH, and every ZIRAN call already refuses a version below 0.39.0
  with a reason that reaches the MCP row.
- "Posture profile in effect" is `config.profile` (the guard profile) plus today's
  imported calibration profile name, if any. There is no "observe" mode on main; only
  shadow days are reported.
- Interview answers are informational (`ok`): answers are promoted into `config.toml`, so
  none today is not a problem.
- Open nudges are a count (`ok`); open pages are `fail` rows, since a page asks the owner
  to act now.
- `doctor --fix` is not added to the owner-action table in `guards/protect_state.py`
  (#222): the table matches a group and a verb and drops flags, so a flag-shaped entry
  reopens the parser the constitution warns about. Every effect of `--fix` passes through
  `integrity._host_confirm`, the same `/dev/tty` digest each underlying owner action uses,
  and the digest binds the exact previews. A seat has no terminal and gets exit 2.
- `--json` is the contract for the board and the DM; wiring either to it is a later item.
- Docs links are repository paths with anchors (`docs/site/<page>.md#<anchor>`), the form
  the docs tests already use.

### Found at build time (main at e5e2070)

- On main: #324, #326, #328, #329 and #323's read-only shell forms (the outside-workspace
  probe exits 0 through the real launcher; one smoke test keeps it). Not on main: #327
  (`wuwei setup`, `wuwei config set`). So `config-set` is not in `FIXES`, a repository
  identity row prints the `config.toml` edit instead of `wuwei config set`, setup does not
  call doctor (T027, T028), and the no-workspace row names `wuwei init --shadow`, the
  command that exists, instead of `wuwei setup --shadow`.
- `doctor.fixed` is classified silent in `cli/wuwei/signal.py`: it records an owner action,
  not something that needs attention (the emitted-kinds test requires a tier).
- A guard probe that failed because of plugin integrity prints `fix the integrity row
  first` instead of the reinstall fix.
- Right after `--fix` installs the watch, the re-diagnosis reads the watch as dead until
  the service writes its first clock line; the test simulates the service starting.
