# Feature Specification: the builder loop is not a parking scanner chain

**Feature Branch**: `870-scanner-builder-loop`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #870: "fix(scanner): the normal builder loop (Edit, Bash, Write in its own worktree) is not a critical chain that parks every item"

## Root cause

- `cli/wuwei/scanner.py:81-92` (`_trace_response`): every critical chain ZIRAN reports for a
  seat session is a `scanner.finding` page and parks the seat's items. The chain itself is
  never looked at.
- ZIRAN's `shell_execute -> write_file` pattern (`command_injection_persist`, risk critical)
  matches Claude Code's `Bash` followed by `Write` or `Edit`, which every builder and sentinel
  does: run the test, write the handoff or verdict. Measured with ZIRAN 0.40.0 on a synthetic
  trace: `Bash -> Write`, `Bash -> Edit` and `Edit -> Bash` all come back critical.
- ZIRAN's trace evidence carries tool names and shell commands only (its `_shell_commands`
  keeps the `command` string of shell tools and no other argument), so the finding has no
  file path to tell a write in the worktree from one outside it.
- `cli/wuwei/commands/status.py:94-95` (`attention`): a page-tier event is keyed by its line
  number, so each `scanner.finding` event is its own doctor fail row, all reading
  `scanner.finding`.

## User Scenarios & Testing

### User Story 1 - The builder loop does not park (Priority: P1)

A builder edits, runs its focused tests and writes its handoff; a sentinel reads, runs a
check and writes its verdict. ZIRAN reports `Bash -> Write` for their sessions. The item
keeps running and nobody is paged.

**Independent Test**: a trace sweep with a seat session whose only critical chains use the
local tools leaves the item in its phase and writes no `scanner.finding`.

**Acceptance Scenarios**:

1. **Given** a seat session with chains `Bash -> Write`, `Bash -> Edit`, `Edit -> Bash -> Write`,
   **When** the trace sweep runs, **Then** the item is not parked and no `scanner.finding` is
   appended.

### User Story 2 - A credential read then an outward send still parks (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a seat session with chain `Read -> WebFetch` (or
   `Read -> mcp__slack__slack_send_message`, `Bash -> WebFetch`), **When** the trace sweep
   runs, **Then** the item parks with `scanner chain Read -> WebFetch` and a `scanner.finding`
   page is appended, as today.

### User Story 3 - Doctor lists one row per chain class (Priority: P2)

**Acceptance Scenarios**:

1. **Given** three `scanner.finding` events for `Read -> WebFetch` and two for
   `Bash -> WebFetch`, **When** doctor (through `status.attention`) reads the day, **Then** it
   shows two scanner rows, one per chain, each naming the chain and carrying its count.

### Edge Cases

- A chain mixing a local tool with any other tool (WebFetch, WebSearch, Agent, an MCP tool,
  an unknown tool) parks: only all-local chains are the builder loop.
- Registered non-seat and unknown sessions keep their once-per-day notes (#352) unchanged.
- S4 audit rows and the honeytoken row (a `rule`, no `chain`) group by rule.

## Requirements

### Functional Requirements

- **FR-001**: A critical chain from a seat session whose tools are all local file and shell
  tools (`Read`, `Grep`, `Glob`, `Edit`, `MultiEdit`, `Write`, `NotebookEdit`, `Bash`) neither
  pages nor parks, unless a span of that session in today's `traces.jsonl` names a credential
  location; then it parks with `after a credential read` in its reason.
- **FR-002**: Any other critical chain from a seat session pages and parks exactly as before.
- **FR-003**: The `scanner.finding` event of a parked chain carries `reason`
  (`scanner chain A -> B`).
- **FR-004**: `status.attention` keys `scanner.finding` by chain (or by rule when there is no
  chain), so doctor shows one row per chain class with its count.

### Key Entities

- `scanner.finding` event: `chain`, `risk_level`, `session_id`, now `reason`.

## Success Criteria

- **SC-001**: The 2026-10-12 day's chains (`Edit -> Bash -> Write`, `Edit -> Bash`,
  `Bash -> Write`) park zero items.
- **SC-002**: A `Read -> WebFetch` seat chain still parks its item.
- **SC-003**: N events of one chain give one doctor row.

## Assumptions

- ZIRAN's chain names tools only; its evidence carries the Bash command strings
  (`evidence.sessions[].commands`) but no file paths. WUWEI's own `traces.jsonl` records every
  call's arguments (paths, globs, commands) per session, so the scanner reads those.
- The edges floor does not stop Bash egress: `check_bash` covers git and gh edges,
  `check_deploy` deploy verbs, and `check_send` on Bash only the canary and honeytoken values.
  So a credential read, then `curl` from Bash, then a write reaches ZIRAN as a plain
  `Bash -> Write` (review F1, fix round 1). An all-local chain therefore parks when any span of
  its session in today's `traces.jsonl` names a credential location in `file_path`, `path` or
  Bash `command`; the reason reads `scanner chain A -> B after a credential read`. The session
  matches by its raw id or the sha256 `trace_sweep` gives a redacted one.
- The scanner has its own narrow check, `scanner._credential_path` (review D1, fix round 2);
  redact's broad name check stays for redaction only. Only path-like words count (a `/`, or a
  leading `~` or `.`), and only exact credential locations: a part `.ssh`, `.netrc`, `.npmrc`,
  `.pypirc`, `.git-credentials`, `.gnupg` or `.env`, a part `.env.*` not ending in `example`,
  `sample` or `template`, or a path ending in `.aws/credentials`, `gh/hosts.yml`, `.pem`,
  `.key` or `.wuwei/env`. A Grep `pattern` is a regex, not a path, and is not read. So
  `grep -E "secret|credential"`, `git diff -G "token|secret"`, `.env.example` and
  `tests/test_env_credentials.py` do not park. On the reviewer's real day traces this check
  matches 2 of 59 and 0 of 104 sessions (the 2 are `jq '.key'` filters), against 22 and 15 for
  the broad check.
- A credential read in a trace is a plain `Read` to ZIRAN (it maps to `read_secret_file`
  only from permission-rule specifiers), so a credential read followed by WebFetch, WebSearch,
  an MCP send or Agent parks through the non-local tool in the chain.
- An all-local chain with no credential location is dropped silently: its spans stay in
  `traces.jsonl` and nothing new is recorded. A once-per-day note would need the dedup the
  non-seat branch has, more than one line (review F3).
- `closing.scanner_hold` keeps one owner card per critical finding; fewer findings means
  fewer cards. Grouping those cards by chain is not asked for. Adding `reason` changes the
  hold token for findings appended after the upgrade (one-off).

## Deferred

- A path check of a seat's `Write` and `Edit` spans against its worktree and scratch
  directory, from WUWEI's own `traces.jsonl` arguments. File it as a follow-up if a write
  outside the worktree must park.
- A bare `Read(credentials) -> Bash(curl ...)` with no later write gives ZIRAN no critical
  chain (`read_file -> shell_execute` is not a pattern; only a high `unrestricted_execution`),
  so it parks neither on main nor here. Pre-existing; closing it needs WUWEI's own check of
  the session's spans without a ZIRAN chain (review F2).
- The credential check is a name match on recorded arguments (review D2). It misses globs
  (`cat ~/.aws/cred*`), quote splitting (`cred''entials`), python string building, base64
  decoded paths and `gh auth token | curl`, and what the recorder's redaction hides: heredoc
  bodies, a `curl -d @file` argument, and the tail of a command over 2048 characters. The
  canary, the honeytoken and the edges guards stay the floor; a credential read check at
  PreToolUse, before redaction, is the upgrade.
