# Feature Specification: the day board as an inline widget in the Claude Code conversation through a plugin MCP server

**Feature Branch**: `281-board-widget`
**Created**: 2026-10-01
**Status**: Ready for implementation
**Input**: Issue #281, feat(cockpit). Owner request 2026-10-01 ("can wuwei show an inline
widget with the queue/board in the conversation, like some MCPs provide"). References:
design 5.9 (cockpit, signals), 7 S3 (MCP audit and drift, `scanner.mcp`), 7.1 (signed
manifest), 9.1 (scope); `templates/dashboard.html`; `cli/wuwei/commands/dashboard.py`;
the manifest build of #245 (`scripts/build-release.py`).

## Spike: what the host supports (verified 2026-10-01)

| Question | Verified | Source |
| --- | --- | --- |
| Can a plugin declare an MCP server? | Yes. `.mcp.json` at the plugin root, same shape as a project `.mcp.json` (with or without the `mcpServers` wrapper), started with the plugin. `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PROJECT_DIR}` substitute in a stdio server's `command`, `args` and `env`; only `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are exported to the process. Server name `plugin:<plugin>:<server>`, tool name `mcp__plugin_<plugin>_<server>__<tool>`. | https://code.claude.com/docs/en/plugins/components (section "MCP servers") and https://code.claude.com/docs/en/plugins-reference (field `mcpServers`, section "Environment variables"), fetched 2026-10-01 |
| Does Claude Code render an MCP Apps UI resource returned by a tool? | Not documented. The Claude Code MCP page documents text, image and file tool output only and does not mention MCP Apps, `ui://` resources or `_meta.ui`. The terminal renders text only. The desktop app on macOS did render MCP Apps widgets (tools with `_meta.ui.resourceUri`) in v2.1.234 and stopped on 2026-08-20 after a staged `server/discover` version-negotiation rollout; that report is open. | https://code.claude.com/docs/en/mcp (fetched 2026-10-01); https://github.com/anthropics/claude-code/issues/88370 (read 2026-10-01) |
| What does an MCP App need? | Tool `_meta.ui.resourceUri` naming a `ui://` resource; `resources/read` returns it with `mimeType` `text/html;profile=mcp-app`; the host renders it in a sandboxed iframe whose default CSP is `connect-src 'none'` with inline scripts allowed; the view sends `ui/initialize` over `postMessage` JSON-RPC, then `ui/notifications/initialized`, and receives `ui/notifications/tool-result` carrying the tool's `content` and `structuredContent`. `structuredContent` is for the view and is not added to model context; `content` is the text for the model and for text-only hosts and must stand on its own. | https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx (read 2026-10-01) |

Conclusion: the first condition holds; the second holds only partially and undocumented
(desktop app, currently broken upstream; never in the terminal). Both of the issue's
branches are therefore built into one tool result, without detecting the host: every call
returns the compact text board (the guaranteed path) and also declares the UI resource, so
a host that renders MCP Apps shows the cockpit template inline and every other host shows
the table. What would close the gap: Claude Code documenting MCP Apps rendering, or #88370
being fixed upstream. If that fix needs servers to answer `server/discover`, it is a
follow-up issue; this server answers unknown methods with JSON-RPC "method not found".

## Root cause (read on main, fb3be19)

Nothing exposes the board inside the conversation:

- The plugin declares no MCP server: there is no `.mcp.json` at the repository root and
  `.claude-plugin/plugin.json` has no `mcpServers`.
- The board data exists only behind the loopback HTTP server. `dashboard.run`
  (`cli/wuwei/commands/dashboard.py:157-174`) builds the `board.json` dict inline
  (`dashboard.py:162-164`) and the template path inline (`dashboard.py:160`), so no other
  caller can reuse them. `cockpit_snapshot` (`dashboard.py:17`) is already a pure read.
- The template can only fetch: `get()` (`templates/dashboard.html:66`) calls `fetch`, which
  an MCP Apps iframe forbids (`connect-src 'none'`), and the page starts polling
  unconditionally (`dashboard.html:196`).
- The release build copies a fixed list of top-level names
  (`scripts/build-release.py:14-19`), so a new root `.mcp.json` would be left out of the
  signed asset and its manifest.
- Shipping a server changes S3. `mcp.discover` (`cli/wuwei/mcp.py:72-75`) adds every
  installed plugin's `.mcp.json`, so WUWEI's own file would be discovered. With the default
  `adapters.scanner = "none"` (`scanner/none.py` `mcp` returns exit 2), a workspace with no
  other MCP server goes from "no attached servers, clean" to "unmeasured": `cached()`
  returns exit 2 when no status exists and `discover` is non-empty (`mcp.py:132-134`), so
  `plan propose` (`cli/wuwei/plan.py:111-114`) and every seat launch
  (`cli/wuwei/guards/agent_launch.py:61-64`) would refuse after an upgrade.

No dry-run workspace is named for this item; the reproduction above is by reading main.

## User Scenarios & Testing

### User Story 1 - The owner sees the day board in the conversation (Priority: P1)

In a Claude Code session inside a WUWEI workspace, the `wuwei_board` tool shows the day:
lanes by phase, items with status and gate verdicts, owned PRs with what they wait on,
pending decisions, pages and nudges, and the status line. Where MCP Apps render, the same
cockpit template as `wuwei dashboard` renders inline; elsewhere the tool shows Markdown
tables.

**Independent Test**: `python -m pytest -q tests/test_board_mcp.py`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given a workspace whose day has items in two phases (one with a gate
   verdict and a PR URL), one owned PR with a recorded watch episode, one pending `D-`
   decision and one nudge, when `tools/call` `wuwei_board` runs, then the text content
   starts with `status.line(...)` of the same day's `status --json`, lists every item in
   `state.PHASES` order with phase, status, gate verdicts and PR, the PR with its state,
   waiting-on and deadline, the decision with its question, route and command, and each
   attention row with tier, lane and reason; and `structuredContent` carries
   `./board.json`, `./state.json`, `./events.jsonl` and `./cockpit.json` whose parsed
   values equal what `wuwei dashboard` serves for the same day.
2. Given `tools/list`, then there is exactly one tool, `wuwei_board`, with an empty-object
   input schema, `annotations.readOnlyHint` true and `destructiveHint` false, and
   `_meta.ui.resourceUri` `ui://wuwei/board.html`.
3. Given `resources/read` for `ui://wuwei/board.html`, then the content text is
   `templates/dashboard.html` exactly, with `mimeType` `text/html;profile=mcp-app`.
4. Given the template in a node harness as an MCP App (a `window.parent` distinct from
   `window`, `fetch` rejecting), when the harness answers `ui/initialize` and posts
   `ui/notifications/tool-result` whose `structuredContent` is a call's result, then the
   page posts `ui/initialize` then `ui/notifications/initialized`, and renders the same
   columns, decisions and PR cells as the HTTP harness for the same data, with escaping
   unchanged and no load error left showing; a message whose `source` is not
   `window.parent` is ignored.
5. Given the dashboard over HTTP (no parent frame), then the page behaves as before: the
   existing node harness tests pass unchanged.

### User Story 2 - The tool cannot write (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_board_mcp.py -k write`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given a populated workspace, when every method (`initialize`,
   `notifications/initialized`, `ping`, `tools/list`, `tools/call`, `resources/list`,
   `resources/read`, an unknown method, an unparseable line) is served, then every file
   under the workspace root keeps its bytes and no file is added or removed; with
   `workspace.atomic_write` and `state.append_event` patched to raise, every call still
   succeeds.
2. Given WUWEI's `.mcp.json` installed as a plugin and `adapters.scanner = "ziran"`, then
   `mcp.discover` returns that file, so the ZIRAN `scanner.mcp` check covers the server's
   static tool description like any installed plugin's.

### User Story 3 - The server ships signed and stays out of the default gate (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_integrity.py tests/test_mcp.py tests/test_board_mcp.py -k "release_package or own_server or mcp_json"`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given the release build, then `.mcp.json` and
   `cli/wuwei/commands/board.py` are in the staged inventory and in `MANIFEST.sha256`, and
   `integrity.measure(stage)` is exit 0.
2. Given the repository root `.mcp.json`, then it declares exactly one stdio server
   `cockpit` with `command` `${CLAUDE_PLUGIN_ROOT}/bin/wuwei`, `args` `["board"]` and
   `env` `{"CLAUDE_PROJECT_DIR": "${CLAUDE_PROJECT_DIR}"}`.
3. Given `adapters.scanner = "none"` and no MCP server other than WUWEI's own, then
   `mcp.discover` returns no file, so `mcp.cached` and `mcp.check` stay exit 0 as before
   this feature.

### Edge Cases

- Outside a WUWEI workspace (9.1): `tools/call` returns the text
  `No WUWEI workspace here; run bin/wuwei init to create one.` with `isError` false and no
  `structuredContent`.
- Workspace without today's day directory: the board shows `WUWEI no plan yet | ...` and
  `None` tables (`read_state` defaults); no directory is created.
- Unreadable or invalid state, decisions or events (any `OSError`, `ValueError`,
  `KeyError`, `TypeError`, `UnicodeError` from the reads): `isError` true, text
  `WUWEI board unmeasured: <reason>`, no `structuredContent`. Never an empty board that
  looks clean.
- `tools/call` with another tool name, or `resources/read` with another URI: JSON-RPC
  error `-32602`. Unknown method with an id: `-32601`. A notification (no id): no response.
  Unparseable line: `-32700` with `id` null. The loop continues after each.
- Untrusted text in item ids, questions, reasons and PR refs: in table cells `|` becomes
  `\|` and newlines become spaces; the template keeps its existing HTML escaping.
- Credentials: responses go through the CLI's redacting stdout, so loaded credential values
  never leave in a response; the server flushes after every response line.

## Requirements

### Functional Requirements

- **FR-001**: `bin/wuwei board` runs a stdio JSON-RPC 2.0 MCP server: one JSON object per
  line on stdin, one response line per request on stdout, flushed; it returns 0 at EOF.
  Stdlib only, no SDK.
- **FR-002**: It answers `initialize` (echoes the client's `protocolVersion` string, else
  `2025-06-18`; capabilities `tools` and `resources`; `serverInfo` name `wuwei` and the
  plugin version), `ping`, `tools/list`, `tools/call`, `resources/list` and
  `resources/read`, and ignores notifications.
- **FR-003**: `wuwei_board` scopes the workspace from `CLAUDE_PROJECT_DIR` (else the
  current directory) through `workspace.guard_scope`, then reads today's day through
  `cockpit_snapshot`, `board_snapshot`, `state.read_state`, `status.attention` and the day's
  `events.jsonl`. It writes nothing and launches nothing.
- **FR-004**: The text content is the status line, then the Markdown tables Work (Item,
  Phase, Status, Gates, PR), PRs (PR, State, Waiting on, Deadline), Decisions (ID,
  Question, Route, Command) and Attention (Tier, Lane, Reason), each `None` when empty,
  then the line `Full cockpit: run bin/wuwei dashboard and open the printed loopback URL.`
- **FR-005**: The UI resource is `templates/dashboard.html` as shipped. The template gains
  an MCP Apps bridge that renders from the tool result's `structuredContent` instead of
  fetching. One template serves both surfaces.
- **FR-006**: `dashboard.run` and the server share `board_snapshot(directory)` and
  `TEMPLATE` from `cli/wuwei/commands/dashboard.py`.
- **FR-007**: `.claude-plugin/plugin.json` `mcpServers` declares the server (amended at
  ship, tasks T020-T021: a root `.mcp.json` doubled as a project MCP file of every WUWEI
  checkout and made a managed WUWEI repo unmeasured); the manifest covers it and the
  server module. No root `.mcp.json` exists.
- **FR-008**: `mcp.discover` is unchanged from main. The server is measured by the
  integrity check (7.1), not by the registry; any `.mcp.json`, including one added to the
  install or one copying the cockpit entry, is discovered and checked like every other
  file. This supersedes User Story 2 scenario 2 and User Story 3 scenarios 2 and 3.
- **FR-009**: Docs: `docs/site/daily.md` names the tool next to the status line;
  `docs/site/configuration.md` (MCP registry checks) states the FR-008 rule.

### Key Entities

- **Board tool result**: `content` (one text item), `structuredContent` (four strings keyed
  by the template's fetch paths), `isError`.

## Success Criteria

- **SC-001**: The three issue acceptance scenarios pass as tests.
- **SC-002**: The full suite passes; the existing dashboard harness tests are unchanged.
- **SC-003**: `cli/wuwei/commands/board.py` stays under 150 lines.

## Assumptions

- Items on main carry no "tier" field. The issue's "items with tier" is met by the
  Attention table (page and nudge rows, including `item.escalated`) and by the parked and
  escalated phases. No new state field is invented.
- "Gate state" is the item's `gate_verdicts` entries rendered `role round: verdict`, joined
  with `, `, else `none`.
- "The dashboard URL" cannot be known by the tool (the dashboard binds a random loopback
  port per run), so the text names the command that prints it.
- The server reads in-process through the CLI functions behind `status --json`
  (`status.snapshot`, via `cockpit_snapshot`) rather than spawning `status --json`; the core
  never imports `subprocess`. Adapter reads that `status --json` already performs (the
  configured calendar) are part of that snapshot and are accepted.
- The template is read from the plugin directory, not the workspace; every workspace read
  stays under the scoped root.
- The UI resource is declared to every client. Hosts that do not render MCP Apps ignore
  `_meta.ui` and show the text. No client-capability detection.
- The tool takes no arguments and always returns the current day.
- The widget is a snapshot of the call and does not poll (the iframe has no network); the
  owner calls the tool again for a fresh board.
- Actions from the widget (answer a decision, approve a draft) are out of scope and remain
  CLI owner actions; the widget shows the commands, as the cockpit does.
- With `adapters.scanner = "ziran"`, the first check after the upgrade registers the new
  server; any drift finding follows the existing S3 decision path.
- FR-008 is a deliberate narrowing of S3 for the default `none` scanner: without it every
  install with no other MCP server would refuse `plan propose` and seat launches after the
  upgrade. The exclusion matches only the running install's own file, which every sweep
  already verifies against the signed manifest. The reviewer should confirm this trade.
- In the WUWEI repository itself, Claude Code may offer the root `.mcp.json` as a project
  server where `${CLAUDE_PLUGIN_ROOT}` does not resolve; the developer declines it. When
  that checkout is the running plugin and a configured repo, FR-008 also excludes it.
