# Feature Specification: the terminal and other local tools are a local class, never outward

**Feature Branch**: `727-local-class`

**Created**: 2026-10-10

**Status**: Draft

**Input**: GitHub issue #727, "feat(outward): the terminal and other local tools are a local
class, never outward: a visible terminal tab on the owner's machine runs without a draft".
Owner, 2026-10-10 (item 53): the outward guard refused running a long job in a visible terminal
tab as an "unknown connector"; registering the terminal as an outbound channel would turn every
terminal command into a draft. A terminal on the owner's own machine is not outward.

## Current behaviour (reproduced on main, d3b7066, read-only)

The orchestrator notes for this issue name no dry-run workspace, so a scratch workspace in a
temp directory (`[owner] name = "Pat Example"`, default posture) ran
`wuwei.guards.outward.check_tier` and `check_lint` in process with
`tool_input = {"command": "sleep 600"}`:

| Tool | `tool_kind` | `resolve` | `check_tier` and `check_lint` |
| --- | --- | --- | --- |
| `mcp__terminal__run_in_terminal` | write | `set()` | `(2, 'outward: connector terminal is not known for write tool ...; write it as a draft for the owner to send, and the planner runs bin/wuwei outbound learn --tool ...')` |
| `mcp__terminal__open_terminal_tab` | write | `set()` | same refusal |
| `mcp__computer-use__open_application` | write | `set()` | same refusal |
| `mcp__terminal__stop_terminal_tab` | unknown | `set()` | `(0, '')` under guarded; refused under strict (outward area `block`) |
| `mcp__Claude_Code_iOS_Simulator__control` | unknown | `set()` | as above |
| `mcp__terminal__read_terminal` | read | `set()` | `(0, '')` |

Root cause:

1. **Local tools are sorted as connectors.** `cli/wuwei/guards/outward.py:36-44` (`tool_kind`)
   reads the name words only; `run` (`:25`) and `open` (`:23`) are in `WRITES`, so
   `run_in_terminal` and `open_terminal_tab` are writes. `resolve` (`:63-84`) knows only the
   outward channels (`slack`, `tracker`, `code_host`, `docs`, `mail`, `other`), so a terminal
   tool resolves to nothing and `_check` (`:164-165`) hands it to `_unmatched` (`:189`), whose
   write branch (`:201-203`) refuses it in every posture as an unknown connector.
2. **No class means "acts only here".** The only way out today is `outbound learn`, whose
   `--as` choices (`cli/wuwei/commands/outbound.py:127`, from
   `workspace.SCHEMA['outward']['servers']`, `cli/wuwei/workspace.py:240`) are all outward
   channels: learning the terminal as `other` puts every command through the tier table and
   the lint as a message, which is the owner's objection.
3. **The terminal's command escapes the command guards.** The Bash guards (`commit_push`,
   `deploy`, `pr`, `protect_state`) are selected by tool name `Bash`
   (`cli/wuwei/guards/__init__.py:18-34`, `cli/wuwei/commands/hook.py:63-80`). A command typed
   through `mcp__terminal__run_in_terminal` (`tool_input.command`, optional `tool_input.cwd`)
   is never judged by them, so passing the terminal as local without more would open a way
   around the push, deploy, PR and records guards.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A visible terminal tab runs without a draft (Priority: P1)

A seat starts a long job in a visible terminal tab on the owner's machine. The outward guard
passes it as local, with no draft and no learn card; what the command does is still judged by
the same guards that judge a Bash command.

**Why this priority**: this is the owner's report; today the call is refused in every posture.

**Independent Test**: PreToolUse hook calls with `mcp__terminal__run_in_terminal` inside a
workspace, one plain command and one guarded command.

**Acceptance Scenarios**:

1. **Given** a terminal tool call (`mcp__terminal__run_in_terminal`, `open_terminal_tab`,
   `stop_terminal_tab`), **When** the outward guard runs (`check_tier`, `check_lint`), **Then**
   it passes it as local (`(0, '')`) in every posture, with no draft row and no
   `outward.unknown_tool` event.
2. **Given** `mcp__terminal__run_in_terminal` with `command = "sleep 600"` through the PreToolUse
   hook, **When** the hook runs, **Then** it exits 0.
3. **Given** `mcp__terminal__run_in_terminal` whose command the Bash guards refuse (a write to
   the day's `state.json` that `protect_state` refuses through `Bash`), **When** the hook runs,
   **Then** it refuses with the same exit and reason as the same command through `Bash`.
4. **Given** `tool_input.cwd` on the terminal call, **When** the Bash guards judge the command,
   **Then** they judge it in that directory (relative to the session cwd, `~` expanded), as a
   Bash call there would be.

---

### User Story 2 - Other local tools pass the same way (Priority: P2)

The simulator, file preview and computer-use on the owner's own apps act only on the owner's
machine and pass the outward guard as local.

**Independent Test**: `check_tier` and `check_lint` on one tool of each shape under strict.

**Acceptance Scenarios**:

1. **Given** `mcp__Claude_Code_iOS_Simulator__control`, `mcp__Claude_Preview__preview_start`,
   `mcp__Claude_Browser__preview_start` or `mcp__computer-use__open_application`, **When** the
   outward guard runs under `strict`, **Then** it returns `(0, '')`.
2. **Given** a local tool whose input carries the workspace canary or honeytoken, **When**
   `check_tier` runs, **Then** it refuses with the `security.` reason as for any other call (the
   records floor is not lowered).
3. **Given** a tool of another server whose name merely contains a local word
   (`mcp__plugin_x_terminal__run_job`, `mcp__Claude_Browser__navigate`), **When** the outward
   guard runs, **Then** nothing changes from today (it is not local).
4. **Given** the owner aliased a server as `local` in `outward.servers`, **When** a write tool of
   that server runs, **Then** it passes as local; an owner alias of a built-in local server to
   an outward channel wins over the built-in shape.

---

### User Story 3 - The learn card offers local, and the tier table lists it (Priority: P3)

**Acceptance Scenarios**:

1. **Given** an unknown connector whose identity call says it is local (the planner passes
   `bin/wuwei outbound learn --tool <tool> --as local`), **When** learn runs, **Then** the card
   proposes `local` ("Connector <server> is local, ..."), offers Approve and Defer and no mode
   options, and approving records `outward.servers.<server> = "local"`.
2. **Given** a tool that matches the local shapes, **When** learn runs without `--as`, **Then**
   the card proposes `local`.
3. **Given** `outbound.learn = "auto"` in any posture, **When** learn runs for `local`, **Then**
   it still writes a card and records nothing until the owner answers (local is never learned
   without the owner).
4. **Given** a connector that already resolves to an outward channel, **When** the planner runs
   learn `--as local`, **Then** it is refused as today (`--as` never lowers a channel).
5. **Given** any workspace, **When** the owner runs `bin/wuwei outbound tiers`, **Then** its last
   line names the local class: the built-in local servers and the owner's `local` aliases pass
   without a draft, and the command guards judge what runs.

### Edge Cases

- `mcp__terminal__run_in_terminal` with a non-string `command` or `cwd` is refused by the hook
  as a malformed payload (exit 2), never passed.
- Outside a WUWEI workspace nothing changes: the hook returns before any guard (design 9.1), as
  it does for Bash.
- `mcp__terminal__read_terminal` and `list_terminal_tabs` are reads and pass, as today.
- A `local` server in `outward.modes` has no effect: local is never drafted or blocked by the
  outward rules, and the learn card does not offer modes for it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `outward.servers` accepts the class `local` (schema choice, so also `--as local`
  on `outbound learn`).
- **FR-002**: `guards.outward.resolve` returns `{'local'}` for a write or unknown tool of a
  server aliased `local`, and for a tool matching the built-in local shapes (exact servers
  `terminal`, `Claude_Preview`, `Claude_Code_iOS_Simulator`, `computer-use`, and the
  `preview_*` tools of `Claude_Browser`), after the owner alias and the tool rules, before the
  vocabulary.
- **FR-003**: The outward guard passes a call that resolves to `{'local'}`: `check_lint`
  returns `(0, '')`; `check_tier` returns `security.outbound(tool_input, root)` (the canary and
  honeytoken floor only). No draft, no tier row, no lint, no unknown-tool event.
- **FR-004**: The PreToolUse hook judges a `mcp__terminal__run_in_terminal` call as the Bash
  call it types: every PreToolUse guard sees `tool_name = "Bash"`, `tool_input = {"command":
  <command>}` and the tab's cwd. Other events are unchanged.
- **FR-005**: `outbound learn` proposes `local` from `--as local` or a local-shaped tool, always
  on a card (never auto-applied), without mode options; the card text says local calls are
  never drafted and the command guards still judge what runs.
- **FR-006**: `outbound tiers` prints one line naming the local class and its servers.
- **FR-007**: The guard rule is added to the design spec 9.2 table and to
  `tests/test_invariants.py` (constitution, Workflow; #530).
- **FR-008**: The docs that list the `outward.servers` choices name `local`
  (`docs/site/configuration.md`, `docs/site/security.md`, `templates/workspace/config.toml`).

### Key Entities

- **local class**: a value of `outward.servers` and of `resolve`; a connector that acts only on
  the owner's machine. Not an audience class (`AUDIENCES` is unchanged).

## Success Criteria *(mandatory)*

- **SC-001**: A run_in_terminal call with a plain command passes the hook in every posture.
- **SC-002**: A command the Bash guards refuse through `Bash` is refused the same way through
  `mcp__terminal__run_in_terminal`.
- **SC-003**: The full suite passes, the invariant walk included.

## Assumptions

- The local shapes are exact server names as Claude Code reports them in this environment
  (`mcp__terminal__*`, `mcp__Claude_Code_iOS_Simulator__*`, `mcp__computer-use__*`) plus file
  preview as `mcp__Claude_Preview__*` and `mcp__Claude_Browser__preview_*`. The rest of
  `Claude_Browser` (navigate, form input, clicks on any site) can reach other people and stays
  outward. The remote-device variants (`mcp__remote-devices__*`) are left out because they act
  on a linked machine; the owner can alias them `local`.
- Computer-use is local as the issue says: it acts on the owner's own apps, each granted by the
  owner in that tool's own access flow. A seat typing into a chat app through it is not judged
  by the outward rules; this is the owner's stated choice, recorded here as the known residual.
  The canary and honeytoken floor still applies to its inputs.
- "Whose identity call says it is local" means the planner reads the connector's identity or
  description and passes `--as local`. WUWEI cannot verify that claim, so `local` is always a
  card the owner answers, even under `learn = "auto"`.
- Judging the terminal command as Bash is done once, at the hook, by presenting the call to the
  guards as the Bash call it types. Refusal records of that PreToolUse call name `Bash`; the
  PostToolUse trace still names the real tool.
- Only `run_in_terminal` types a command. `open_terminal_tab` only starts the owner's shell and
  `stop_terminal_tab` only sends Ctrl-C, so they need no command judgement.
- The orchestrator notes file for this issue was not present; this spec follows the issue text.
