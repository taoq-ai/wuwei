# Feature Specification: adapters.scanner = none turns the MCP gate off with one nudge line instead of an unmeasured exit 2 from init, mcp check and the launch gate

**Feature Branch**: `424-scanner-none-off`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #424, found by the v0.13.0 release smoke (2026-10-03). On a fresh
`bin/wuwei init .` with the template config (`adapters.scanner = "none"`, posture guarded),
`init` and `mcp check` exit 2 with `scanner.mcp: unmeasured` and `MCP registry unmeasured;
cockpit: unmeasured`. #360 made "scanner off unless asked" the setup default, so a scanner set
to `none` is a choice, not a failure. Builds on #325 (attached servers, per-server
unmeasured), #331 (posture), #351 (MCP warns under guarded, a check that could not run
blocks), #358 (`wuwei next`) and #360, all on `main`.

## Root cause (reproduced on main, 50d22fe)

Reproduced with the worktree's `bin/wuwei init .` in a scratch `git init` directory on this
host (template config, posture guarded, an installed WUWEI plugin listed in
`~/.claude/plugins/installed_plugins.json` at a different directory from the running CLI):
`init` exit 2 and `mcp check` exit 2, both printing `scanner.mcp: unmeasured` and `MCP
registry unmeasured; cockpit: unmeasured`; `.wuwei/ziran/status.json` holds `exit 2` with
`unmeasured: [["cockpit", ...]]`; `events.jsonl` holds `adapter: none` and `mcp.checked
{"exit": 2}`.

1. **`none` is treated as a scanner that failed.** `cli/wuwei/mcp.py` `check` (line 488)
   returns early only for `security.areas.mcp = "off"` (lines 492-493). Otherwise it
   discovers servers, loads the configured adapter (`registry.load('scanner', config)`, line
   512) and calls `scanner.mcp` per server (line 530). `adapters/scanner/none.py` `mcp`
   returns `registry.record_none('scanner', 'mcp', root)`, which prints `scanner.mcp:
   unmeasured` and returns exit 2 (`cli/wuwei/registry.py` lines 151-162). `check` files the
   server as unmeasured (lines 547-554) and exits 2 (line 567). `init`
   (`cli/wuwei/commands/init.py` `_register_mcp`, lines 150-155), `setup`
   (`cli/wuwei/commands/setup.py` lines 325-335, which also owes `bin/wuwei mcp decide
   proceed-unmeasured cockpit`) and `mcp check` (`cli/wuwei/commands/mcp.py` lines 39-46)
   return that exit. The `mcp.checked` exit-2 event becomes a nudge (`cli/wuwei/signal.py`
   lines 50-51), and doctor shows `mcp cockpit: warn unmeasured`. `cached` (line 317) has the
   same gap: only `level == 'off'` short-circuits (lines 326-327), so under strict the
   unmeasured server refuses every launch.
2. **A configured scanner that cannot start is not treated as "could not run".** With
   `adapters.scanner = "ziran"` and no `ziran` on `PATH`, `adapters/scanner/ziran.py` `mcp`
   fails in `_version()` before any server and returns `Result(2, None, 'ziran
   watch-registry: unmeasured: FileNotFoundError')` (outer `except`, lines 151-152). `check`
   files that as a per-server unmeasured result (lines 547-554), so `_gate` (lines 308-314)
   treats it as a posture-controlled unmeasured server and the guarded launch gate exits 0
   (reproduced: `check` 2, `cached` 0). #325 assumed "ZIRAN missing or the `none` adapter
   counts as per-server unmeasured"; this issue reverses both halves.
3. **Why the smoke saw `cockpit`.** The cockpit server came from the installed v0.11.0 WUWEI
   plugin, whose install directory is not `integrity.PLUGIN` (the release asset under test),
   so `discover` (lines 92-102) correctly measured it as another plugin's server. With the
   gate off for `none`, discovery does not run and nothing is filed as unmeasured.

## User Scenarios & Testing

### User Story 1 - A team without ZIRAN starts its first day without an MCP wall (Priority: P1)

The owner runs `bin/wuwei init .` (or `setup`) with the template config on a host without
ZIRAN, then the morning plan. The MCP registry gate is off because no scanner is configured;
each command exits on its real result, and the first MCP check of the day prints one line
saying the registry is not measured and how to measure it.

**Why this priority**: today every fresh workspace without ZIRAN exits 2 from `init` and
`mcp check`, setup owes a proceed-unmeasured decision, and strict refuses every launch.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k no_scanner`.

**Acceptance Scenarios**:

1. **Given** the template config (`adapters.scanner = "none"`, guarded) and an attached
   server, **when** `init` runs, **then** it exits 0 and stderr holds exactly one MCP line,
   `mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)`;
   no `scanner.mcp: unmeasured`, no `MCP registry unmeasured`, no `status.json` record and no
   `adapter: none` event.
2. **Given** the same on a fresh day, **when** `mcp check` runs, **then** it exits 0 and
   prints the line; a second `mcp check` the same day exits 0 and prints nothing.
3. **Given** the same on a fresh day, **when** `plan propose` runs, **then** it returns the plan
   path, prints the line on stderr, and the plan's `- mcp:` sweep line carries the line; `wuwei
   next` then moves on to the morning gate.
4. **Given** the same, **when** the launch gate runs (`mcp.cached`, `mcp.launch`,
   `agent_launch.check_mcp`) under observe, guarded or strict, **then** it exits 0 with the
   line as its reason.
5. **Given** the same, **when** `setup` reaches its MCP step, **then** it owes no `mcp decide`
   or `mcp check` step.

### User Story 2 - A configured scanner that fails still refuses (Priority: P1)

The owner set `adapters.scanner = "ziran"`, but `ziran` is not on `PATH` (or is the wrong
version). The registry check could not run; that blocks launches under guarded and strict as
#351 and the design spec posture floor say.

**Why this priority**: turning `none` off must not soften the case where the owner asked for
measurement and did not get it.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k scanner_cannot_start`.

**Acceptance Scenarios**:

1. **Given** `adapters.scanner = "ziran"`, an attached approved server and no `ziran` on
   `PATH`, **when** `mcp check` runs, **then** it exits 2, its reason starts `MCP registry
   could not run:` and carries the adapter's reason (`ziran watch-registry: unmeasured:
   FileNotFoundError`), and `status.json` holds `exit 2` with `unmeasured: []`.
2. **Given** that record, **when** the launch gate runs under guarded or strict, **then** it
   exits 2 with the could-not-run reason; under observe it warns (exit 0), as today.
3. **Given** a scanner that starts but returns exit 2 for one server (data present: an
   unreachable server or a per-server timeout), **then** that server stays per-server
   unmeasured and guarded still warns (#325 and #351 behaviour, unchanged).

### User Story 3 - Doctor shows the gate as a choice (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `adapters.scanner = "none"`, **when** `wuwei doctor` runs, **then** the `mcp gate`
   row is `ok` with the line as its value, each server in WUWEI's own signed
   `.claude-plugin/plugin.json` has an `ok` row `mcp <name>` with value `covered by plugin
   integrity`, and no `mcp <name>` row from a `status.json` record appears, even one written
   earlier today.
2. **Given** `adapters.scanner = "ziran"`, the doctor rows are unchanged.

### Edge Cases

- `security.areas.mcp = "off"` keeps its own reason (`MCP registry: not checked
  (security.areas.mcp = "off")`); it is checked first.
- A workspace switched from `ziran` to `none` keeps its `status.json` and snapshots; the gate
  ignores them while the scanner is `none` and uses them again when it is set back.
- The once-per-day marker is today's `mcp.checked` event with `"scanner": "none"`; the next
  day prints the line again.
- `mcp decide` and `mcp check --widget` need no change: with no record there is no pending
  decision.
- S2 (traces) and S4 (agent surface) keep their current `none` behaviour; only S3, the
  registry gate, changes.

## Requirements

### Functional Requirements

- **FR-001**: With `adapters.scanner = "none"`, `mcp.check` MUST exit 0 without discovering
  servers, loading the scanner, writing `status.json` or appending `adapter: none`. It MUST
  return the reason `mcp: not measured (no scanner configured; set adapters.scanner =
  "ziran" to measure)` on its first call of the day and an empty reason after, and MUST mark
  the first call with an `mcp.checked` event `{"exit": 0, "servers": {}, "scanner": "none"}`.
- **FR-002**: With `adapters.scanner = "none"`, `mcp.cached` (and through it `mcp.launch`,
  `agent_launch.check_mcp`, the runtime adapters, `plan propose` and doctor) MUST return exit
  0 with the same line as its reason in every posture, after the `security.areas.mcp =
  "off"` check, with no new import on the hook path.
- **FR-003**: `init`, `init --upgrade`, `setup` and `mcp check` MUST exit 0 for the MCP step
  under `none`; their exit codes follow the three-state contract for real findings only.
- **FR-004**: `plan propose` MUST print the check's reason on stderr when it is the
  no-scanner line, and its `- mcp:` sweep line MUST carry the line on every run of the day.
- **FR-005**: When the configured scanner cannot start (its `mcp` call returns exit 2 with no
  data: not on `PATH`, wrong version, a version-probe timeout), `mcp.check` MUST record a
  check that could not run (`exit 2`, `unmeasured: []`, reason `MCP registry could not run:
  <adapter reason>`), roll snapshots back as for any check that could not run, and return
  exit 2 with that reason. The launch gate then refuses under guarded and strict through the
  existing `_gate` rule.
- **FR-006**: Under `none`, doctor MUST show the `mcp gate` row `ok` with the line, one `ok`
  row `mcp <name>` with value `covered by plugin integrity` per server in WUWEI's own
  `.claude-plugin/plugin.json`, and no record-derived server rows.
- **FR-007**: `docs/site/security.md` and `docs/site/configuration.md` MUST say that `none`
  turns the registry gate off, what that gives up (no drift or tool-poisoning detection on
  attached servers, no per-server rows, nothing in briefs), and that a configured scanner that
  cannot start is a check that could not run.

### Key Entities

- **No-scanner line**: the constant `mcp.NO_SCANNER`, the one text for every surface.
- **`mcp.checked` with `"scanner": "none"`**: the existing reserved event kind, written only
  by `mcp.check`; silent tier (exit 0), and it already clears `mcp.finding` rows in
  `status.attention`.

## Success Criteria

- **SC-001**: A fresh `init` with the template config on a host without ZIRAN exits 0 and
  prints one MCP line (the v0.13.0 smoke exits 2 today).
- **SC-002**: With `adapters.scanner = "ziran"` and no `ziran` on `PATH`, `mcp check` exits 2
  and the guarded launch gate exits 2 (it exits 0 today).
- **SC-003**: The full suite passes; no doc still says the `none` adapter makes the registry
  unmeasured.

## Assumptions

- A1. "Once per day" applies to the printed line: the first `mcp.check` of the day returns it,
  so whichever of `init`, `setup`, `mcp check` or `plan propose` runs first prints it, and
  later checks that day exit 0 silently. Doctor and the launch gate (`mcp.cached`) always
  carry the line as their reason, because they report state rather than nudge. The issue's
  acceptance naming `init`, `mcp check` and `plan propose` is read as "each, when it is the
  first MCP check of its day"; tests use a fresh workspace per command.
- A2. "As a nudge" means a printed line, not a `wuwei nudges` row: the marker event is
  `mcp.checked` with exit 0, which `signal.tier` files as silent. A deliberate owner choice
  does not belong on the attention list.
- A3. `none` turns the gate off in every posture, strict included, as the issue says ("treat
  it as `security.areas.mcp = "off"` for the registry part"). `config check` is not changed
  to flag strict plus `none`; deferred unless the owner asks.
- A4. "The cockpit server row says covered by plugin integrity" is a doctor row per server in
  WUWEI's own signed `plugin.json` (`integrity.PLUGIN`), shown only under `none`. Under
  `ziran` the check reason already says covered. The smoke's cockpit came from an older
  installed WUWEI at another directory; that is another plugin's server by design (#325:
  coverage follows the install directory) and is simply not measured under `none`.
- A5. "A configured scanner that fails (not on PATH, wrong version, timeout)" is detected as
  the adapter returning exit 2 with `data is None`, which is how `adapters/scanner/ziran.py`
  reports a failure before any server (its outer `except`). A per-server failure (data
  present, including a per-server `watch-registry` timeout) stays per-server unmeasured, so
  #325 and #351 behaviour for unreachable or unpinned servers does not change.
- A6. The release smoke `_pipeline/release.sh` is outside this repository; changing its `init`
  line to expect exit 0 is the orchestrator's step, listed in tasks.md and not done by the
  builder.
- A7. Design spec conflict, raised per the constitution: `docs/specs/2026-09-24-wuwei-design.md`
  section 7 says "With the adapter set to `none` or ZIRAN absent, S2 to S4 report
  'unmeasured' (exit 2)", and constitution principle II says an absent scanner "reports
  unmeasured and is never counted as clean". This issue turns S3 off for `none`. The line
  says "not measured", never clean, so principle II holds in substance. The design spec is
  amended only by its owner; the builder does not edit it. Suggested owner amendment: "S3 is
  off with `none`; a configured scanner that cannot start is a check that could not run; S2
  and S4 report unmeasured."
- A8. A `status.json` record written before a switch to `none` may still list today's
  unmeasured servers in `mcp.unmeasured` (the brief header). That is informational, lasts one
  day at most, and is left alone.
- A9. With no attached servers (and no earlier record) `mcp.check` under `none` stays as on
  main: no line, no marker event, no day directory (`init` on an empty project creates no day).
  The nudge is about servers left unmeasured, so it prints only when there are some. The launch
  gate and doctor still carry the line as their reason.
