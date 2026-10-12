# Feature Specification: doctor warns when codex.command is empty while Codex is wanted

**Feature Branch**: `860-codex-command-doctor`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #860: "fix(doctor): an empty codex.command is a warn row when the codex runtime is wanted or the companion is installed"

## Root cause

- `cli/wuwei/commands/doctor.py:250-253` (`_host`): the only Codex row checks the `codex`
  binary on PATH, and only when `adapters.runtime` or `gates.second_opinion` names codex.
  It never reads `codex.command`, which `adapters/runtime/codex.py:16-18` needs to run any seat.
- `cli/wuwei/commands/config.py:84-87` (`config check`) and `:174` (`missing`) flag an empty
  `codex.command` only when `adapters.runtime = "codex"`; a seat policy row or the second
  opinion on codex passes.
- `cli/wuwei/plan.py:331` and `:364`: the morning gate prints the seat policy as JSON and says
  nothing when a row names codex and the command is empty.

## User Scenarios & Testing

### User Story 1 - Doctor names the missing command and the companion path (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[codex] command = []` and the Codex Claude Code plugin installed, **When** the
   owner runs `doctor`, **Then** one warn row `codex.command` says
   `codex.command empty: runtime codex unavailable` and names the companion script path it
   found, with the `config set` line that uses it.
2. **Given** an empty `codex.command`, no plugin, and `gates.second_opinion = "codex:<model>"`
   (or `adapters.runtime = "codex"`, a `budget.codex` window, or today's seat policy naming
   codex), **Then** the same warn row appears, with a generic fix.
3. **Given** a set `codex.command`, or nothing that wants Codex and no plugin, **Then** no
   `codex.command` row appears.

### User Story 2 - The morning gate's seat-policy line says so (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a proposal whose seat policy names codex (runtime or alternate) and an empty
   `codex.command`, **Then** the plan's `Seat policy:` line and the gate card's seat policy
   end with `(codex.command empty: runtime codex unavailable)`.
2. **Given** a set `codex.command`, **Then** neither line carries it.

### Edge Cases

- An unreadable or malformed `installed_plugins.json` is no plugin (the row then depends only
  on the wanted conditions).
- A plugin entry whose script is missing on disk is no plugin.

## Requirements

### Functional Requirements

- **FR-001**: `doctor` appends one `host` warn row `codex.command` when `codex.command` is
  empty and either Codex is wanted (`adapters.runtime`, `gates.second_opinion`, a nonzero
  `budget.codex` window, today's seat policy runtime or alternate) or the Codex plugin's
  companion script exists.
- **FR-002**: The row's value names the companion path when found; its fix is
  `bin/wuwei config set codex.command '["node", "<path>"]'`, else a generic line.
- **FR-003**: The proposal's seat-policy line (plan and gate card) carries the same reason,
  from the same function, with the proposal's seat policy as the policy.

## Success Criteria

- **SC-001**: With an empty `codex.command` and the plugin installed, doctor prints one warn
  row naming the companion script path.

## Assumptions

- "Calibration names the codex runtime" reads as a `budget.codex` window set by the owner:
  that is the only codex-named setting the calibration and window work (#845) added.
- The installed plugin is read from the file the scanner already reads,
  `scanner.mcp.plugins_file` (default `~/.claude/plugins/installed_plugins.json`), by its
  `codex@<marketplace>` entry and `installPath`; the script is
  `<installPath>/scripts/codex-companion.mjs`.
- The row is warn, not fail: a day can run claude-only.
- `config check` keeps its scope; doctor is where the owner looks first.
