# Feature Specification: A broken config.toml can be read and fixed from the session

**Feature Branch**: `326-config-failure-mode`
**Created**: 2026-10-03
**Status**: Draft
**Input**: Issue #326, fix(config): a broken config.toml can be read and fixed from the
session, the template cannot produce the most likely TOML error, and config check names it.
Design spec 3.1 (repository layout), 4 (guards, hook table 4.1), 9 and 9.1 (fail closed,
guard scope); builds on #171 (templates and recovery cues) and #247 (config errors name
config.toml). Evidence: the owner's first-run trial of v0.11.0 (2026-10-03), findings B3
and B4.

## Root cause (reproduced read-only on main, 69453ed)

Reproduced in a scratch workspace outside the repository: the shipped template with a
`[[repos]]` table appended, plus a measured integrity verdict, then each hook replayed
through `python3 -P -m wuwei hook <event>`.

- `templates/workspace/config.toml:5` ships `repos = []` and line 6 says "Replace repos = []
  with one or more tables like:". Appending `[[repos]]` while keeping line 5 is a TOML error:
  `tomllib` reports `Cannot mutate immutable namespace ('repos',) (at line 229, column 8)`,
  the position of the `[[repos]]` header, not of the line to delete.
- `cli/wuwei/workspace.py:495-496` `load_config` wraps that as
  `ConfigError("config.toml: <tomllib message>")` with no hint. Every caller gets the same
  text: hooks, `config check`, `init --upgrade`.
- `cli/wuwei/guards/integrity.py:7-15` `check` is a PreToolUse guard for every tool
  (matcher `None`). It calls `workspace.guard_scope`, which calls `workspace.scope`
  (`workspace.py:255`), which calls `load_config`; the `ConfigError` becomes `(2, message)`.
  So `Read` of `.wuwei/config.toml`, `Grep`, `Glob` and `ToolSearch` all exit 2 with
  the config error. `cli/wuwei/guards/outward.py:73` and `:125` add a second, generic
  refusal (`outward: cannot read or validate policy or payload`) for Bash and MCP tools.
- `cli/wuwei/commands/hook.py:22-53` `run` has no notion of a config failure: it runs every
  guard and refuses with all their reasons.
- `cli/wuwei/guards/stop.py:15` `check` calls `guard_scope`, so the `ConfigError` lands in
  `except watch.ERRORS` (lines 39-40) as `Stop unmeasured: config.toml: ...`, exit 2, and
  `hook.refuse` prints `{"decision": "block", ...}`: the turn cannot end.
- `cli/wuwei/commands/config.py:25-30` `run` already exits 1 on a `ConfigError` and prints
  it; it only lacks the fix.
- `cli/wuwei/commands/init.py:214-216` `upgrade` parses the file (`tomllib.loads`, then
  `load_config`) before any migration, so a config with both `repos = []` and `[[repos]]`
  exits 2 and is never migrated.

Observed: Read of `.wuwei/config.toml` exit 2, Grep exit 2, ToolSearch exit 2, Bash exit 2
(two reasons), `mcp__terminal__read_terminal` exit 2 (three reasons), Stop exit 2 with a
block decision, SessionStart exit 0 with the error twice, `config check` exit 1 without a
fix.

## User Scenarios & Testing

### User Story 1 - The session can read the config it is told to fix (Priority: P1)

The owner's config does not load. The planner session can still read `.wuwei/config.toml`
and the charters, and can still load deferred tools, so it can show the owner the exact
line. Everything else stays refused with the error and its hint.

**Independent Test**: replay PreToolUse payloads through `wuwei hook` in a workspace whose
config has `repos = []` next to `[[repos]]`.

**Acceptance Scenarios**:

1. Given a config with the immutable-namespace error, when `Read` of `.wuwei/config.toml`
   goes through PreToolUse, then the hook exits 0 with empty stdout.
2. Given the same config, when `Read` of a file under `.wuwei/charters/`, `Grep` with
   `path` `.wuwei/config.toml`, `Glob` with `path` `.wuwei/charters`, or `ToolSearch` goes
   through PreToolUse, then each exits 0.
3. Given the same config, when Bash (`ls`) goes through PreToolUse, then the hook exits 2
   with one deny decision whose reason starts with `config.toml:` and contains
   `repos is assigned on line N; delete that line before using [[repos]] tables`, N being
   the line of `repos = []`.
4. Given the same config, `Write` of `.wuwei/config.toml`, `Read` of any other file,
   `Grep` without a `path`, `Agent`, and an MCP tool each exit 2 with that same single
   reason.
5. Given the same config and a session whose cwd is outside the workspace while the Read
   target is the workspace's `.wuwei/config.toml`, then the Read exits 0, and a Bash call
   from that cwd is unaffected by this feature (exit 0, outside scope).

### User Story 2 - The turn can end (Priority: P1)

**Acceptance Scenarios**:

1. Given a config with the immutable-namespace error, when the Stop hook runs, then it
   exits 0, stdout is empty (no block decision), and stderr holds the config error with its
   hint exactly once.

### User Story 3 - The template cannot produce the error, and the error names its fix (Priority: P1)

**Acceptance Scenarios**:

1. Given the shipped template with a `[[repos]]` table (`name`, `path`,
   `default_branch`) appended at the end, then the text parses and `load_config` returns
   that repository.
2. The shipped template has no top-level `repos` key; its repository guidance is the
   commented `# [[repos]]` example only.
3. Given `repos = []` next to a `[[repos]]` table, then `wuwei config check` exits 1 and
   stderr names the exact fix: `repos is assigned on line N; delete that line before using
   [[repos]] tables`.
4. Given the same config, `load_config` raises a `ConfigError` carrying that hint, so every
   CLI command that loads the config prints it.

### User Story 4 - init --upgrade repairs the known shape (Priority: P2)

**Acceptance Scenarios**:

1. Given an existing config with a one-line top-level `repos = []` and one or more
   `[[repos]]` tables, when `wuwei init --upgrade --dry-run` runs, then it exits 0, reports
   that it would remove `repos = []`, and writes nothing.
2. Given the same config, when `wuwei init --upgrade` runs, then it exits 0, the file no
   longer has the `repos = []` line, every other line (owner comments included) is kept, the
   result loads with the configured repositories, and a second run reports
   `No workspace changes needed`.
3. Given an existing config with `repos = []` and no `[[repos]]` table, upgrade leaves that
   line alone.

### Edge Cases

- A config that fails for another reason (unknown key, bad value, another TOML error) gets
  the same PreToolUse carve-out and Stop behaviour, without the hint.
- A missing or unreadable `config.toml` (`OSError`) is not a config failure for this
  feature; the guards measure it as today.
- Outside every workspace nothing changes: the hook returns 0 (spec 9.1).
- Shadow mode cannot relax the config refusal: with no loadable config the mode is unknown,
  so the hook enforces (the rule `hook.shadow` already follows).
- SessionStart, PostToolUse, PreCompact and SubagentStop keep today's behaviour.

## Requirements

### Functional Requirements

- **FR-001**: When a workspace in scope has a `config.toml` that raises `ConfigError`, the
  PreToolUse hook MUST exit 0 for `ToolSearch` and for `Read` (`file_path`), `Grep` and
  `Glob` (`path`) whose resolved target is that workspace's `.wuwei/config.toml`, its
  `.wuwei/charters` directory, or a path inside it. It MUST refuse every other call with
  exit 2 and the error as the single reason.
- **FR-002**: In the same state the Stop hook MUST print the error once to stderr and exit
  0 without a block decision.
- **FR-003**: `load_config` MUST append `; repos is assigned on line N; delete that line
  before using [[repos]] tables` when the TOML error is the immutable `repos` namespace.
- **FR-004**: The workspace template MUST NOT assign `repos`; it keeps the commented
  `# [[repos]]` example.
- **FR-005**: `wuwei config check` MUST exit 1 with the FR-003 fix for `repos = []` beside
  `[[repos]]`, through `load_config` (no second detector).
- **FR-006**: `wuwei init --upgrade` MUST remove a one-line top-level `repos = []` when the
  file has `[[repos]]` tables, report it (`Would upgrade` / `Upgraded`), honour
  `--dry-run`, and validate the repaired text before writing anything.
- **FR-007**: The FR-001 refusal MUST be recorded as `hook.refusal` like any other
  PreToolUse refusal (except for the heartbeat session).

## Success Criteria

- **SC-001**: In the trial shape the session reads the line it must delete with no owner
  round trip; the owner fixes the file in one edit.
- **SC-002**: A new workspace cannot reach the immutable-namespace error by following the
  template's comments.
- **SC-003**: Hook latency budgets under `WUWEI_BENCH=1` still pass.

## Assumptions

- A1: "Fail closed for writes, Bash, outward tools and dispatch" is met by refusing every
  PreToolUse call outside the read carve-out. Dispatch reaches the session through Bash
  and `Agent`, both refused; the CLI commands themselves already fail on the config error.
- A2: `Grep` and `Glob` pass only with an explicit `path`; their `pattern` and `glob` are
  not inspected. They are reads, and WUWEI guards no read outside this failure mode, so
  this widens nothing.
- A3: The carve-out passes before the integrity gate runs. Reading two workspace files is
  no wider than what a session could read before WUWEI was installed, and nothing can
  write while the config is broken.
- A4: "Prints the error once" means one copy of the message per Stop invocation (today two
  guards each report it), not once per session.
- A5: Only PreToolUse and Stop change. The issue names those two; SessionStart already
  exits 0 with the error in context; SubagentStop, PostToolUse and PreCompact are left as
  they are.
- A6: The hint covers the one known shape the issue names, the immutable `repos`
  namespace. `repos` is the only top-level array of tables in `SCHEMA`, so the `[[repos]]`
  wording is always right for it. Other shapes get a hint when they are seen.
- A7: The `init --upgrade` repair is the literal reading of "removes an empty `repos = []`
  when `[[repos]]` tables exist": that file is never valid TOML, so the repair runs before
  upgrade parses it. A `repos = []` without tables is valid and stays.
- A8: A cwd outside the workspace (a seat in a worktree, or `WUWEI_WORKSPACE` set) reaches
  the config error while the hook resolves scope; it gets the same handling, and the
  carve-out is decided from the target path.
- A9: The owner's trial report contains client names and local paths; none of them appear
  in this feature. Tests use neutral fixture names.
- A10 (added during implementation): an older workspace without `security.json` makes
  `init --upgrade` read `config.toml` a second time in `security.load`; that read also
  takes the repaired text, so the repair works on those workspaces too.
