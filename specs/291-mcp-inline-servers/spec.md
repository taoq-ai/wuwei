# Feature Specification: the registry gate measures servers declared inline in a plugin's plugin.json

**Feature Branch**: `291-mcp-inline-servers`

**Created**: 2026-10-01

**Status**: Draft

**Input**: GitHub issue #291, "fix(mcp): the registry gate measures servers declared inline in
a plugin's plugin.json, not only .mcp.json files". Depends on #281 (merged as PR #290, main
8084fe9).

## Root cause (read and reproduced on main, 8084fe9)

`mcp.discover` (`cli/wuwei/mcp.py:26-76`) reads one file per installed plugin:
`add(directory / '.mcp.json')` at `cli/wuwei/mcp.py:75` is the only per-plugin source. Claude
Code also starts servers declared under `mcpServers` in the plugin's
`.claude-plugin/plugin.json` (the form WUWEI itself uses for the cockpit since #281), and
substitutes `${CLAUDE_PLUGIN_ROOT}` with the install path when it starts them. Those servers
are never discovered, so they run without the ZIRAN metadata check, without a baseline and
without an owner decision on drift.

Reproduction (read-only, in a throwaway directory; no dry-run workspace is named for this
item): a workspace with `adapters.scanner = "ziran"`, a v2 `installed_plugins.json` listing one
user-scope plugin whose only server is
`{"mcpServers": {"docs": {"command": "${CLAUDE_PLUGIN_ROOT}/server"}}}` in
`.claude-plugin/plugin.json`. Result: `discover` returns `[]`, `cached` and `check` both
return exit 0 with no reason. Expected: the file is discovered, `cached` is exit 2 until the
first check, and `check` measures it.

Two facts shape the fix:

- `add(path, user=True)` (`cli/wuwei/mcp.py:31-42`) already reads a file whose servers sit under
  a top-level `mcpServers` key and validates the map; plugin.json has exactly that shape.
- The ZIRAN adapter passes each file to `ziran watch-registry --from-claude-config <file>` and
  keys its snapshot directory on the file's resolved path (`adapters/scanner/ziran.py:97`).
  ZIRAN must see the server as Claude Code starts it, so `${CLAUDE_PLUGIN_ROOT}` has to be
  expanded in a file WUWEI writes, at a path that stays the same across checks so baselines
  and drift carry over.

## User Scenarios & Testing

### User Story 1 - A third-party plugin's inline server is gated like any other (Priority: P1)

The owner installs a plugin that declares its MCP server only inside
`.claude-plugin/plugin.json`. The morning check registers it with ZIRAN and later flags a
changed tool description before any seat launches.

**Why this priority**: it closes the gap the issue names; without it such servers bypass S3.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k inline`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given an installed plugin whose only server is inline in plugin.json
   and `adapters.scanner = "ziran"`, when `mcp check` runs, then discovery returns that
   plugin.json, the scanner measures a file whose server command has `${CLAUDE_PLUGIN_ROOT}`
   replaced by the install path, the first registration writes a baseline snapshot and the
   check exits 0.
2. (Issue acceptance 1) Given that registered plugin, when the server's description in
   plugin.json changes and `mcp check` runs again, then the same snapshot directory is used,
   the change is reported as drift (exit 1) and an owner decision opens.
3. Given the same plugin and no check yet today, then `mcp.cached` is exit 2 (unmeasured), as
   for any other discovered server.

### User Story 2 - WUWEI's own cockpit is covered by integrity, reported, not scanned (Priority: P1)

**Why this priority**: reading plugin.json must not turn every WUWEI install into
"unmeasured" under the default `none` scanner, nor scan WUWEI's signed file twice.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "own_server or lookalike"`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given WUWEI's own plugin.json installed as a plugin (scanner `none` or
   `ziran`), then `discover` returns no file for it, `cached` and `check` exit 0, and the
   `check` reason states that WUWEI's plugin.json servers are covered by plugin integrity
   (signed manifest) and not scanned.
2. Given another plugin whose plugin.json declares a `cockpit` entry identical to WUWEI's
   (a lookalike), then it is discovered and measured like any other server: with the `none`
   scanner `cached`, `check` and `launch` are exit 2 (unmeasured, refused).
3. (Issue acceptance 3) The #281 negative tests stay green unchanged: a lookalike `.mcp.json`
   in WUWEI's install or in the workspace is discovered and returns unmeasured and refused.

### Edge Cases

- A plugin without `.claude-plugin/plugin.json`, or whose plugin.json has no `mcpServers`, or
  an empty one, contributes nothing (as an absent `.mcp.json` does today).
- A plugin with both `.mcp.json` and inline servers contributes both files; each keeps its own
  snapshot.
- plugin.json that is unreadable, not JSON, a dangling symlink, or whose `mcpServers` is not an
  object of objects: discovery raises, the gate is exit 2 with the existing
  `MCP registry unmeasured: <ExceptionType>` reason (fail closed).
- WUWEI's own install is recognised only by path: the resolved plugin.json equals
  `integrity.PLUGIN / '.claude-plugin/plugin.json'`. A `.mcp.json` in WUWEI's install is
  still discovered (the #281 rule); any other plugin's plugin.json is measured whatever its
  server names.
- `${CLAUDE_PLUGIN_ROOT}` values that contain characters JSON escapes (quotes, backslashes,
  non-ASCII) are substituted as escaped JSON string content, so the written file is valid.

## Requirements

### Functional Requirements

- **FR-001**: For every installed plugin in scope (unchanged scope rules), `discover` reads
  `<installPath>/.mcp.json` as today and also `<installPath>/.claude-plugin/plugin.json`,
  taking its servers from the top-level `mcpServers` object, validated by the existing `add`.
- **FR-002**: WUWEI's own plugin.json (resolved path equal to
  `PLUGIN / '.claude-plugin/plugin.json'`) is not returned by `discover`; it is recorded as
  covered so `check` can report it.
- **FR-003**: Before calling the scanner, `check` replaces each discovered plugin.json with a
  file under `.wuwei/ziran/plugins/`, named by the SHA-256 of the plugin.json path, holding
  `{"mcpServers": <the plugin's servers>}` with every `${CLAUDE_PLUGIN_ROOT}` replaced by the
  install directory. The name is stable per source path, so the adapter's snapshot key, the
  baseline, drift, backup and recovery, findings, events and the owner decision flow are the
  existing ones, unchanged.
- **FR-004**: When WUWEI's own plugin.json was seen, the `check` reason carries
  `WUWEI plugin.json servers covered by plugin integrity (signed manifest), not scanned`:
  alone (exit 0) when nothing else is discovered and no status exists, appended after `; `
  to the measured or unmeasured reason otherwise.
- **FR-005**: `.mcp.json` files (workspace, repos, user file, plugin installs) are passed to
  the scanner by their own path as today; no expansion, no new snapshot key.
- **FR-006**: Docs: `docs/site/configuration.md`, section "MCP registry checks (S3)", names
  both plugin sources and states that WUWEI's own plugin.json is covered by integrity and
  reported as such by `mcp check`, while any other plugin's inline servers, including a
  lookalike cockpit, are registered and checked.

### Key Entities

- **Expanded plugin servers file**: `.wuwei/ziran/plugins/<sha256 of plugin.json path>.json`,
  `{"mcpServers": {...}}`, rewritten on every `check`, protected like the rest of
  `.wuwei/ziran/` by `protect_state`.

## Success Criteria

- **SC-001**: The reproduction above returns the plugin.json from `discover`, exit 2 from
  `cached` before the first check, exit 0 from the first `check` and exit 1 after a
  description change.
- **SC-002**: `python -m pytest -q` passes with every existing test in `tests/test_mcp.py` and
  `tests/test_board_mcp.py` unchanged except the added integrity-reason assertion.

## Assumptions

- Only the object form of plugin.json `mcpServers` is measured. The path form (a string or a
  list of config file paths) fails closed as invalid input (exit 2, unmeasured); measuring
  it is a follow-up if a real plugin needs it.
- Only `${CLAUDE_PLUGIN_ROOT}` is expanded, as the issue states. `${CLAUDE_PROJECT_DIR}`,
  `${CLAUDE_PLUGIN_DATA}` and user environment references stay literal.
- Plugin `.mcp.json` files are not expanded. Expanding them would move their snapshot key to
  a new path and silently re-baseline existing servers once, which would accept any drift
  that happened in between.
- The install directory used for expansion is the resolved plugin.json path's grandparent
  (the resolved install path, so a symlinked home or temp directory is harmless). Only a
  plugin that ships its own `.claude-plugin` or plugin.json as a symlink would expand to the
  link target instead of the install path; the server is still measured, never skipped, and
  that plugin's author already controls what its server runs.
- "Covered by integrity" means the file is in the signed manifest (`scripts/build-release.py`
  stages `.claude-plugin`); whether integrity currently verifies is the integrity gate's
  verdict (spec 7.1), not re-checked by `mcp check`.
- The whole of WUWEI's own plugin.json is skipped, not only the `cockpit` entry: any other
  entry added to that signed file is integrity drift.
- Stale expanded files for uninstalled plugins are left in `.wuwei/ziran/plugins/`; they are
  never passed to the scanner.
- No dry-run workspace is named for this item; the reproduction was run in a throwaway
  directory against the worktree code.
