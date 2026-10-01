# Implementation Plan: the day board as an inline widget through a plugin MCP server

**Branch**: `281-board-widget` | **Date**: 2026-10-01 | **Spec**: `specs/281-board-widget/spec.md`

## Summary

Ship one stdlib stdio MCP server inside the plugin, `bin/wuwei board`, declared by a root
`.mcp.json`. Its single read-only tool `wuwei_board` returns a Markdown board for the model
and every text-only host, plus the four strings the cockpit template already fetches as
`structuredContent`, and declares `ui://wuwei/board.html`, which is
`templates/dashboard.html` itself. The template gains a short MCP Apps bridge so it renders
from the tool result where it cannot fetch. The dashboard and the server share the board
dict and the template path. The release build ships `.mcp.json`. S3 discovery skips WUWEI's
own `.mcp.json` only under the default `none` scanner so upgrading does not turn every
install without ZIRAN into "unmeasured".

## Technical Context

- Python 3.11+ stdlib only at runtime; pytest and node (already used by
  `tests/test_dashboard.py`, skipped when absent) in tests.
- Protocol: MCP JSON-RPC 2.0 over stdio, one JSON object per line; MCP Apps extension
  `io.modelcontextprotocol/ui` (spec 2026-01-26) for the UI resource. Sources in spec.md,
  "Spike".
- Reuse: `dashboard.cockpit_snapshot` (decisions, drafts, PRs, status, signals),
  `status.snapshot` (via the cockpit) and `status.line`, `status.attention`,
  `state.read_state`, `state.PHASES`, `workspace.guard_scope`, `workspace.day_dir`,
  `integrity.PLUGIN`, the CLI's redacting stdout from `__main__.main`.
- Test command: `python -m pytest -q` from the repository root.

## Constitution Check

- I Stdlib only: yes; no SDK, no new dependency.
- II Three-state exits: the command returns 0 at EOF; read failures become an `isError`
  tool result naming the reason (`WUWEI board unmeasured: ...`), never a clean-looking
  empty board.
- III One behaviour, one function: the board read is `board.read(root)`; the dashboard's
  board dict lives once in `dashboard.board_snapshot`.
- IV Test first: every task pair below.
- V Ponytail: one new module under 150 lines, one new JSON file, no class, no capability
  negotiation, no polling in the widget, no actions.
- VII Security: no write path, no network, scope via the shared helper, redacted output,
  untrusted text escaped in table cells and HTML.

## Design

### 1. `cli/wuwei/commands/dashboard.py` (shared spot)

- Add module constant `TEMPLATE = Path(__file__).resolve().parents[3] / 'templates/dashboard.html'`.
- Add `board_snapshot(directory)` returning
  `{'phases': [p for p in state.PHASES if p not in ('parked', 'escalated')], 'build_phases': state.BUILD_PHASES, 'cap': state.read_state(directory=directory)['cap']}`.
- `run` uses both: `page = TEMPLATE.read_bytes()`,
  `board=json.dumps(board_snapshot(directory)).encode()`. Behaviour unchanged.

### 2. `cli/wuwei/commands/board.py` (new; discovered by `__main__` by module name)

Module constants:

- `URI = 'ui://wuwei/board.html'`, `MIME = 'text/html;profile=mcp-app'`.
- `TOOL`: `name` `wuwei_board`, `title` `WUWEI day board`, a static `description`
  ("Read-only view of today's WUWEI board: items by phase with status and gate verdicts,
  owned PRs and what they wait on, pending decisions, pages and nudges, and the status
  line. Takes no arguments and writes nothing."), `inputSchema`
  `{'type': 'object', 'properties': {}, 'additionalProperties': False}`, `annotations`
  `{'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}`,
  `_meta` `{'ui': {'resourceUri': URI}}`.

Functions:

- `register(subparsers)`: `board` subcommand, help `serve the day board to Claude Code over MCP stdio`; `func=run`.
- `run(args)`: `return serve(sys.stdin, sys.stdout)`. `sys.stdout` is the CLI's
  `redact.Output` here, so credential values are filtered; `serve` calls `flush()` after
  each line because `redact.Output.write` does not flush the underlying stream.
- `serve(stdin, stdout)`: for each non-blank line: `json.loads` (on `ValueError` reply
  `-32700`, id `None`); `reply = handle(message)`; when not `None`, write
  `json.dumps(reply) + '\n'` and flush. Return `CLEAN` at EOF.
- `handle(message)`: non-dict, `-32600`; no `id`, `None` (notification); dispatch on
  `method`:
  - `initialize`: `{'protocolVersion': params.protocolVersion if it is a str else '2025-06-18', 'capabilities': {'tools': {}, 'resources': {}}, 'serverInfo': {'name': 'wuwei', 'version': <plugin.json version via integrity.PLUGIN>}}`.
  - `ping`: `{}`.
  - `tools/list`: `{'tools': [TOOL]}`.
  - `tools/call`: `params.name != 'wuwei_board'` gives `-32602`; else `call()`.
  - `resources/list`: `{'resources': [{'uri': URI, 'name': 'wuwei-board', 'mimeType': MIME}]}`.
  - `resources/read`: `params.uri != URI` gives `-32602`; else
    `{'contents': [{'uri': URI, 'mimeType': MIME, 'text': dashboard.TEMPLATE.read_text(encoding='utf-8')}]}`.
  - otherwise `-32601`.
  Replies are `{'jsonrpc': '2.0', 'id': id, 'result': ...}` or
  `{'jsonrpc': '2.0', 'id': id, 'error': {'code': c, 'message': m}}` through one small
  `_reply(id, result=None, error=None)` helper.
- `call()`: `root = workspace.guard_scope({'cwd': os.environ.get('CLAUDE_PROJECT_DIR') or str(Path.cwd())})`.
  `None` gives the text result `No WUWEI workspace here; run bin/wuwei init to create one.`
  with `isError` False. Otherwise `text, files = read(root)` and return
  `{'content': [{'type': 'text', 'text': text}], 'structuredContent': files, 'isError': False}`.
  Any `OSError`, `ValueError`, `KeyError`, `TypeError`, `UnicodeError`, `RecursionError`
  (the set `status.run` catches) from scope or read gives
  `{'content': [{'type': 'text', 'text': f'WUWEI board unmeasured: {exc}'}], 'isError': True}`.
- `read(root)`: `directory = workspace.day_dir(root)`; `cockpit = dashboard.cockpit_snapshot(directory)`;
  `data = state.read_state(directory=directory)`; `events` is the day's `events.jsonl`
  text, `''` when absent; `files = {'./board.json': json.dumps(dashboard.board_snapshot(directory)), './state.json': json.dumps(data), './events.jsonl': events, './cockpit.json': json.dumps(cockpit)}`.
  Text, in order:
  - `status.line(cockpit['status'])`;
  - `## Work`: rows for items sorted by `list(state.PHASES).index(item['phase'])` (stable,
    so insertion order inside a phase): `id`, `phase`, `status`, gates, `pr_url` or `none`.
    Gates: `', '.join(f"{v['role']} {v['round']}: {v['verdict']}" for v in data['gate_verdicts'].values() if v.get('item') == id)` or `none`;
  - `## PRs`: `cockpit['prs']` rows `ref`, `state`, `waiting_on`, `deadline`;
  - `## Decisions`: `cockpit['decisions']` rows `id`, `question`, `route`, `command`;
  - `## Attention`: `status.attention(directory)` rows `tier`, `lane`, `reason`;
  - last line `Full cockpit: run bin/wuwei dashboard and open the printed loopback URL.`
  Each table is a header, a `| --- |` row and one row per entry, or the line `None`. One
  `_cell(value)`: `' '.join(str(value).split()).replace('|', '\\|')`.

No write, no event, no subprocess, no network. The module imports `dashboard`, `status`,
`state`, `workspace`, `integrity` (for `PLUGIN`) and the exit constant.

### 3. `templates/dashboard.html` (one template, two surfaces)

- Before `get`, add `let embedded = null;` with a comment: MCP Apps host, the tool result's
  `structuredContent` keyed by fetch path.
- `get(path)`: when `embedded` is set, return `embedded[path]` if it is a string, else
  throw `new Error(path + " missing")`; otherwise the existing fetch.
- Replace the last line `tick(); setInterval(tick, POLL_MS);` with: when
  `globalThis.window && window.parent !== window` run the bridge below, else `tick()`; then
  `setInterval(tick, POLL_MS)` in both cases. Top-level HTTP is unchanged (the existing node
  harness defines no `window`). In a frame there is no immediate fetch, so the first render
  comes from the tool result without racing a failing fetch; a dashboard that happens to be
  framed over HTTP still loads on the first interval tick; once `embedded` is set, ticks
  read it and never fetch.
- The bridge: a `message` listener that ignores any
    event whose `source !== window.parent` or whose `data.jsonrpc !== "2.0"`; on the reply
    with `id === 1` and a `result`, post `{jsonrpc: "2.0", method: "ui/notifications/initialized", params: {}}`;
    on `method === "ui/notifications/tool-result"` with an object
    `params.structuredContent`, set `embedded` and call `tick()`. Then post
    `{jsonrpc: "2.0", id: 1, method: "ui/initialize", params: {protocolVersion: "2026-01-26", appInfo: {name: "wuwei-board", version: "1"}, appCapabilities: {availableDisplayModes: ["inline"]}}}`
    to `window.parent` with target origin `"*"` (the host's sandbox origin is not known in
    advance; the messages carry no data).
- Rendering, escaping and the HTTP endpoints do not change.

### 4. `.mcp.json` (new, repository root = plugin root)

```json
{
  "mcpServers": {
    "cockpit": {
      "command": "${CLAUDE_PLUGIN_ROOT}/bin/wuwei",
      "args": ["board"],
      "env": {"CLAUDE_PROJECT_DIR": "${CLAUDE_PROJECT_DIR}"}
    }
  }
}
```

The tool appears to Claude as `mcp__plugin_wuwei_cockpit__wuwei_board`; it matches none of
the outward `tool_patterns`.

### 5. `scripts/build-release.py`

Add `'.mcp.json'` to the `copyfile` tuple (`README.md`, `LICENSE`, `NOTICE`,
`pyproject.toml`). `write_manifest` and `measure` then cover it; `cli/` already carries the
server module. `scripts/headless_e2e.py` mirrors the release inputs into its
scratch source by the same kind of fixed list, so `.mcp.json` is added there too (found when
the full suite ran).

### 6. `cli/wuwei/mcp.py` (`discover`)

In `discover`, compute once
`own = PLUGIN / '.mcp.json' if config['adapters']['scanner'] == 'none' else None`
(`from wuwei.integrity import PLUGIN`; integrity does not import mcp, so no cycle), and at
the top of the inner `add(path, ...)` return early when `path.resolve() == own`. This
covers both the installed-plugin path and a development checkout that is also a configured
repo. With any other scanner nothing changes. Comment: WUWEI's own file is covered by the
signed manifest (7.1); scanning it needs a scanner.

### 7. Docs

- `docs/site/daily.md`, next to `bin/wuwei status --line` (line 111): one short paragraph:
  in a session, ask for the board or call `wuwei_board`; it shows items by phase, PRs,
  decisions and attention as a table, and renders the cockpit inline where the host renders
  MCP Apps; it is read-only, and owner actions stay CLI commands.
- `docs/site/configuration.md`, section "MCP registry checks (S3)": one sentence: WUWEI
  ships its own read-only board server in `.mcp.json`; with `adapters.scanner = "none"`
  discovery skips that one file (the signed manifest covers it), with ZIRAN it is
  registered and checked like any other server.

## What must not change

- `cockpit_snapshot`, `status.snapshot`, `status.line`, `status.attention`: no edits.
- The dashboard HTTP surface (`DayHandler`, endpoints, loopback Host check, POST refusal)
  and the template's rendering and escaping. The existing node harness tests in
  `tests/test_dashboard.py` pass without edits.
- `mcp.discover` behaviour for every file other than WUWEI's own, and for WUWEI's own file
  whenever a scanner is configured; `mcp.check`, `cached`, `decide` untouched.
- `integrity.inventory` and `measure`: no edits (they already walk every file).
- No new state key, event kind, guard, hook or config key.

## Risks

- Desktop rendering is upstream-broken (#88370). The text board is the guaranteed path and
  is what the tests pin; the widget is best effort until Claude Code documents MCP Apps.
- The text content is model context and carries seat-written text (decision questions,
  item ids), as `wuwei nudges` already does; cells are flattened and pipe-escaped only.
- `structuredContent` can be large on a long day (the events file); acceptable for one day.
- FR-008 narrows S3 under the `none` scanner; flagged for the reviewer in spec.md
  Assumptions.
