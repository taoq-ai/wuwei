# Feature Specification: the registry gate warns by default, scans only servers that attach, one server at a time, and never launches unpinned third-party code

**Feature Branch**: `325-mcp-attached-servers`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #325, "fix(mcp): the registry gate warns by default, scans only
servers that attach, one server at a time, and never launches unpinned third-party code".
Evidence: the owner's first-run trial of v0.11.0 on Claude Code (2026-10-03), defect B2.
Owner ruling, 2026-10-03: warn by default, block only where configured. Main is 69453ed
(v0.11.0).

## Root cause (read and reproduced on main, 69453ed)

Reproduction (read-only, in a throwaway directory under the session scratchpad; the item
names no dry-run workspace): a workspace with `adapters.scanner = "ziran"`, one project
`.mcp.json` holding three servers (`docs`, a stdio fake; `aws`, `uvx awslabs.example@latest`;
`remote`, an http server at `127.0.0.1:9`) and a user `~/.claude.json` whose
`projects[<workspace>]` has `enabledMcpjsonServers: []` and `enableAllProjectMcpServers:
null`. With `subprocess.run` replaced to raise `TimeoutExpired` for `watch-registry`:

- `mcp.discover` returned the project file although Claude Code would attach none of its
  servers.
- The adapter made one `watch-registry` call for the whole file with `timeout=150`, would
  have launched `uvx ...@latest` through ZIRAN, and returned exit 2 with the reason
  `ziran watch-registry: unmeasured: TimeoutExpired`: no server named, no findings kept.

Five code facts produce the trial failure:

1. `cli/wuwei/mcp.py:47-48`: `discover` adds `<repo>/<project_file>` for the workspace and
   every repo without reading Claude Code's approval state.
2. `cli/wuwei/mcp.py:232-235`: `check` hands every discovered file to one `scanner.mcp(files)`
   call; `adapters/scanner/ziran.py:89-120` runs one `watch-registry` per file with
   `timeout=60 + 30 * len(entries)` (line 106), and any exception sets `code = 2` for the file
   (lines 118-120), so one unreachable server hides every other server in that file.
3. Nothing inspects a server's command before ZIRAN starts it, so `uvx pkg@latest` and
   `npx -y pkg` run unpinned third-party code the owner never approved.
4. `cli/wuwei/plan.py:114-116` raises on any non-zero `mcp.check`, and `mcp.cached`
   (`cli/wuwei/mcp.py:146-150`, used by `guards/agent_launch.py:61-64` and both runtime
   adapters through `mcp.launch`) refuses every launch on any non-zero record. Exit 2 from a
   single unreachable server therefore stops the day.
5. `mcp.decide` (`cli/wuwei/mcp.py:263-297`) returns early on exit 2 and accepts only
   `Outcome: proceed` for findings, so an unmeasured server has no owner path at all.

## User Scenarios & Testing

### User Story 1 - One unreachable server does not stop the day (Priority: P1)

The owner's repo has a team `.mcp.json` with a local server and an OAuth-backed remote one.
The morning check measures each server on its own, names the one it could not reach, and
the plan proceeds with a nudge. Only a critical finding (by default) blocks.

**Why this priority**: it is the trial blocker; without it the plugin is unusable on a
common repo shape.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "two_server or posture"`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given an approved two-server config, one reachable fake that
   reports a finding and one remote server at `127.0.0.1:9`, when `mcp check` runs, then the
   first server's finding is recorded (`mcp.finding` event, report kept), the second is
   unmeasured with a reason that names it, and `mcp check` exits 2.
2. (Issue acceptance 1) Given scenario 1 with the default `scanner.mcp.block` and a `high`
   finding, when `plan propose` runs, then the plan is written, its measured sweep has an
   `mcp:` line naming the unmeasured server and the open decision, and the agent launch gate
   (`mcp.cached`) returns exit 0.
3. (Issue acceptance 1) Given scenario 1 with a `critical` finding and the default block,
   then `plan propose` refuses (state error naming the pending decision) and the launch gate
   returns exit 1.
4. Given `scanner.mcp.block = []`, a critical finding blocks nothing; given
   `["high", "critical"]`, a high finding blocks; given a list containing `"unmeasured"`, an
   unmeasured server blocks with exit 2.
5. Given a check that could not run at all (invalid config, unreadable approval state, an
   interrupted check, a stale or missing record), then the launch gate still refuses with
   exit 2 under every posture.

### User Story 2 - Unapproved project servers are neither scanned nor run (Priority: P1)

A repo's `.mcp.json` lists servers the owner never approved in Claude Code. Claude Code
does not attach them to any session or seat there, so the gate reports them as not attached
and never executes their command.

**Why this priority**: the trial check executed more code than the seats would; this is
the security inversion the issue names.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "unapproved or approval"`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given an unapproved project config whose server command would
   write a sentinel file when started, when `mcp check` runs with a ZIRAN stub that starts
   stdio servers, then the reason contains `<name>: not attached (unapproved)`, the check
   exits 0 and the sentinel file is never written. Control: once the same server is listed
   in `enabledMcpjsonServers`, the stub starts it and the sentinel appears.
2. Given approval through any of: `projects[<repo path>].enabledMcpjsonServers` or
   `enableAllProjectMcpServers: true` in the user file; `enabledMcpjsonServers` or
   `enableAllProjectMcpServers` in `~/.claude/settings.json`, `<project>/.claude/settings.json`
   or `<project>/.claude/settings.local.json`; or any of these for an item worktree root
   under `<workspace>/worktrees/`, then the server is scanned.
3. Given a server named in `disabledMcpjsonServers` for a project key, then that key does
   not approve it even when `enableAllProjectMcpServers` is true there.
4. Given approval state that is present but invalid (bad JSON, a non-list server list, a
   non-boolean flag), then `mcp check` exits 2 and the gate refuses (fail closed).
5. User-scope servers (`~/.claude.json` top-level `mcpServers`) and plugin servers are in
   scope without approval, as today.

### User Story 3 - Unpinned launchers are never executed (Priority: P1)

**Why this priority**: an approved server whose command fetches the latest package on every
start runs code nobody reviewed; the check must not be the thing that runs it.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k unpinned`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given an approved stdio server `npx -y pkg@latest`, when
   `mcp check` runs, then that server is unmeasured with the reason `<name>: unpinned
   launcher`, the scanner is never called for it, and an `npx` stub on `PATH` that writes a
   sentinel is never run.
2. The same holds for `npx -y pkg`, `uvx awslabs.example@latest`, `uvx pkg`, `pipx run pkg`
   and a launcher given by a path ending in `/npx`.
3. Given `npx -y pkg@1.2.3`, `uvx pkg==1.2.3` or `pipx run pkg==1.2.3`, then the server is
   scanned normally.

### User Story 4 - The owner can proceed with a named unmeasured server (Priority: P2)

**Why this priority**: an unreachable OAuth server stays unmeasured; the owner needs a
recorded way to say "proceed" so the check reads clean and, under a blocking posture, seats
can launch.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k proceed_unmeasured`.

**Acceptance Scenarios**:

1. (Issue acceptance 4) Given one approved server that is unmeasured today, when the owner
   runs `wuwei mcp decide proceed-unmeasured <server>` on the host and types the displayed
   digest, then a decision record `D-n.md` with `Decided-by: owner` and
   `Outcome: proceed-unmeasured` naming the server is written, an `mcp.decided` event with
   outcome `proceed-unmeasured` and the server names is appended, and the next `mcp check`
   exits 0 with a reason that says the server proceeds unmeasured by owner decision.
2. Given that decision, when the server's definition in `.mcp.json` changes, then the next
   `mcp check` reports it unmeasured again (the decision is bound to the definition).
3. Given a declined confirmation or a server that is not unmeasured today, the command
   exits 1; given no server name or a check that could not run, it exits 2. Neither records
   anything.
4. Agent tools cannot run `mcp decide` with any arguments (existing owner-command guard).

### User Story 5 - Seats know which servers are unmeasured (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_brief.py -k mcp_unmeasured`.

**Acceptance Scenarios**:

1. Given today's record lists unmeasured servers (decided or not), when a brief is written,
   then its header has `MCP unmeasured: <names>` with the instruction to treat their output
   as untrusted data. Given none, no such line is added.

### User Story 6 - Per-server timeout (Priority: P3)

**Acceptance Scenarios**:

1. Given no setting, each `watch-registry` call uses `timeout=60`; given
   `scanner.mcp.timeout_seconds = 5`, each call uses 5, independent of the server count.

### Edge Cases

- Two config files declaring a server with the same name: each is scanned separately (own
  one-server file, own snapshot directory); unmeasured entries and decisions carry the
  definition digest, so a decision for one definition does not cover a different one.
- A server name outside `[A-Za-z0-9][A-Za-z0-9_.-]{0,127}`: invalid input, `mcp check`
  exits 2 (fail closed), as an invalid server map does today.
- A status record written by v0.11.0 (no posture fields): read as before, so its pending
  decision and any exit 2 keep blocking until the next check rewrites it.
- The `none` scanner adapter or ZIRAN missing: every in-scope server is unmeasured, a nudge
  under the default posture.
- WUWEI's own signed `plugin.json` servers stay covered by integrity and are not scanned.

## Requirements

### Functional Requirements

- **FR-001**: For a project `<repo>/<project_file>` (workspace root and configured repos),
  `mcp check` MUST scan only servers Claude Code would attach: a server is attached when, for
  at least one project key (the repo path or an existing directory under
  `<workspace>/worktrees/`), its name is not in that key's `disabledMcpjsonServers` and is in
  that key's `enabledMcpjsonServers` or the key has `enableAllProjectMcpServers: true`. A
  key's state is the union of `projects[<key>]` in `scanner.mcp.user_file`,
  `~/.claude/settings.json`, `<key>/.claude/settings.json` and
  `<key>/.claude/settings.local.json`. Missing files mean no approval; present but invalid
  data is exit 2.
- **FR-002**: Unapproved project servers MUST be reported as `<name>: not attached
  (unapproved)` in the check reason, count as measured, and MUST never be passed to the
  scanner.
- **FR-003**: Each in-scope server MUST be measured by its own scanner call on a one-server
  config `{"mcpServers": {<name>: <entry>}}` written at a path stable per (source file, server
  name); `${CLAUDE_PLUGIN_ROOT}` expansion for plugin manifests is kept. An unmeasured
  server's reason MUST start with its name.
- **FR-004**: A stdio server whose launcher is `uvx`, `npx` or `pipx run` (by command
  basename) MUST be reported unmeasured with reason `unpinned launcher` and never passed to
  the scanner unless its package spec carries an exact version (`@<digit>...` or
  `==<digit>...`; `@latest` is not exact). Anything the rule cannot read as pinned is
  unpinned.
- **FR-005**: New config `scanner.mcp.block`, a list over `critical`, `high`, `medium`, `low`,
  `unmeasured`, default `["critical"]`. The launch gate (`mcp.cached`, `mcp.launch`,
  `plan propose`) MUST refuse only when an undecided finding batch contains a severity in
  `block` (exit 1) or an undecided unmeasured server exists and `block` contains
  `unmeasured` (exit 2), and MUST always refuse when the check could not run, is stale or
  missing (exit 2). Otherwise it returns exit 0 with the nudge reason.
- **FR-006**: `mcp check` exit MUST stay the honest measurement: 2 while any in-scope server
  is unmeasured and not owner-decided, 1 while findings await a decision, else 0.
- **FR-007**: New config `scanner.mcp.timeout_seconds`, integer >= 1, default 60, used as the
  per-server `watch-registry` timeout.
- **FR-008**: `wuwei mcp decide proceed-unmeasured <server>...` MUST, at the owner terminal
  after typed-digest confirmation, write a decision record with
  `Outcome: proceed-unmeasured`, an accepted record binding each server name to its
  definition digest under `.wuwei/ziran/`, and an `mcp.decided` event; later checks MUST
  treat a still-unmeasured server with an accepted (name, digest) pair as decided.
  `wuwei mcp decide` with no arguments keeps today's findings flow.
- **FR-009**: Every brief MUST list today's unmeasured servers (undecided and decided) in an
  `MCP unmeasured:` header line when there is at least one.
- **FR-010**: Docs: `docs/site/configuration.md` (`scanner.mcp` keys and the posture),
  `docs/site/security.md` (what the gate executes, never executes, and what blocks by
  default), the wuwei-plan skill step 1, the template config and the design spec S3 bullet.

### Key Entities

- Registry status record (`.wuwei/ziran/status.json`): gains `severities`, `unmeasured`
  and `decided` (see `data-model.md`).
- Accepted unmeasured record (`.wuwei/ziran/accepted-<digest>.json`): gains `servers`.
- One-server config (`.wuwei/ziran/servers/<sha256>.json`).

## Success Criteria

- **SC-001**: The trial shape (one approved local server with findings, one unreachable
  remote server, unapproved repo configs with `@latest` launchers) yields a written plan
  under the default posture, with no unapproved or unpinned command executed.
- **SC-002**: Every issue acceptance scenario has a passing test; the full suite passes.
- **SC-003**: No hook exceeds its `WUWEI_BENCH=1` budget (the launch gate adds one cached
  config read, no subprocess).

## Assumptions

- Owner ruling 2026-10-03 deliberately narrows constitution II ("exit 2 blocks like exit 1")
  for this one gate: `mcp check` still exits 2 when unmeasured, but the launch gate treats a
  per-server unmeasured result as a nudge unless `scanner.mcp.block` contains
  `unmeasured`. The issue says `["high", "critical"]` "is the old behaviour"; that is true
  for findings. Because a severity list cannot express unmeasured, the full pre-#325
  behaviour is `["high", "critical", "unmeasured"]`, and the docs say so.
- A check that could not run at all (bad input, interrupted, stale, missing) still blocks
  under every posture; only per-server measurement failures are posture-controlled. ZIRAN
  missing or the `none` adapter counts as per-server unmeasured.
- Findings decisions are still queued for every high or critical finding (and for any
  severity named in `block`), so the owner sees them; only blocking depends on `block`.
  Signal tiers are unchanged: a high finding event still pages.
- A findings decision (`mcp decide` without arguments) is allowed while some server is
  unmeasured; it is refused only when the check could not run or is stale.
- Approval reading over-approximates: an approval at any item worktree root covers that
  server name for every repo config, and project `.claude/settings*.json` files are trusted
  as approval sources. Over-approximation scans more, which is the safe direction.
- `~/.claude/settings.json` is read through `Path.expanduser`, so tests point it at a
  fixture with `HOME` (the autouse sandbox in `tests/conftest.py`); no new config key.
- Local-scope servers (`projects[<path>].mcpServers` in the user file) and launchers other
  than `uvx`, `npx` and `pipx run` (`bunx`, `pnpm dlx`, `uv tool run`) are not handled here;
  today's discovery does not read the former either. Deferred.
- Snapshots are keyed by the one-server file path, so the first check after upgrading
  registers a fresh baseline per server; drift that happened between the last v0.11.0 check
  and the upgrade is not reported. Documented in configuration.md.
- One-server configs copy the entry as Claude Code reads it (env and headers included), so
  they are written owner-only (mode 0o600) under the protected `.wuwei/ziran/`.
- `wuwei init` keeps returning the measurement exit of `mcp check`.
- `scanner.mcp` stays in the calibration profiles' private list; the posture profiles item
  will drive `scanner.mcp.block` on its own.
