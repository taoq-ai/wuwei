# Feature Specification: mcp check writes one report per server per result, the decision summarises the findings, and mcp decide records the outcome without hand edits

**Feature Branch**: `350-mcp-reports`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #350, "fix(mcp): mcp check writes one report per server per check,
the decision summarises the findings, and mcp decide records the outcome without hand
edits". Evidence: the owner's second first-day trial, 2026-10-03 (development build of
0.12.0): seven `mcp.checked` events, three report directories (two identical, one empty),
a planner that spent four refused commands opening them and then told the owner to edit
`Decided-by` and `Outcome` in the decision file by hand. Main is ed28ab4 (v0.12.0).

## Root cause (read and reproduced on main, ed28ab4)

Reproduction (read-only, in a throwaway workspace under the session scratchpad; the notes
name no dry-run workspace): `adapters.scanner = "ziran"`, `scanner.mcp.timeout_seconds =
2`, a project `.mcp.json` with two approved servers (`docs`, whose ZIRAN stub reports one
high `tool_poisoning` row and exits 1; `slow`, whose stub sleeps past the timeout), three
`mcp.check` runs. Result: six `report-*` directories (three with the same report, three
empty), D-1, D-2 and D-3 each queued, and D-3's context listing all six paths, three of
them pointing at files that do not exist.

1. `adapters/scanner/ziran.py:108-109` creates a fresh `report-<random>` directory with
   `mkdtemp` and appends its path to `measured['reports']` before `subprocess.run` (line
   110). Every call makes a new directory, so an unchanged result is stored again, and a
   run that times out or fails (except at line 125) leaves the empty directory behind with
   its path still in the result.
2. `cli/wuwei/mcp.py:427` extends `reports` with every server's paths, measured or not.
3. `cli/wuwei/mcp.py:441-448` queues a new decision on every check that has a high,
   critical or blocking finding, even when the same findings are already pending, and
   appends every path to `record['reports']`.
4. `cli/wuwei/mcp.py:340-353` (`_queue`) writes only `Reports: <paths>` as the context:
   no finding, no server, no hint of first measurement or change.
5. `cli/wuwei/mcp.py:525-528` (`decide`) accepts findings only when the owner has already
   typed `Outcome: proceed` into the record by hand. The reasons say the same:
   `mcp.py:271` and `:280` ("owner decision required in <path>"), `mcp.py` check reason
   ("owner decision open in <path>"), `commands/doctor.py:335` ("set Outcome: proceed"),
   `commands/setup.py:257`, and `skills/wuwei-plan/SKILL.md:14`.
6. Nothing records what the owner accepted: `decide` (`mcp.py:542`) clears `pending`, so a
   static finding such as `tool_poisoning` queues a new decision on the very next check.
7. `cli/wuwei/commands/dashboard.py:59` gives every pending `D-n` on the board the command
   `bin/wuwei decision route D-n`, which does not answer an MCP decision.
8. `cli/wuwei/guards/protect_state.py:88-89` (`_pair`) drops flags, so `wuwei mcp decide
   --help` matches the owner row at line 48 and is refused at lines 158-159.

## User Scenarios & Testing

### User Story 1 - One report per server per distinct result (Priority: P1)

Checks run several times in a morning (init, setup, the plan skill, `plan propose`). Each
server's result is stored once under `.wuwei/ziran/<server>/<digest>.json`. A repeat with
the same result writes nothing and says `unchanged`; a run that fails leaves nothing.

**Why this priority**: it removes the duplicate and empty paths that sent the planner on
refused reads, and it is what the baseline in story 3 is keyed by.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "report"`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given three checks of an unchanged server, then exactly one file
   exists under `.wuwei/ziran/<server>/`, and the second and third `mcp.checked` events
   record that server as `unchanged` (two `unchanged` events).
2. (Issue acceptance 2) Given a check whose ZIRAN run times out, then no new directory or
   file appears under `.wuwei/ziran/`, the server is unmeasured, the `mcp.checked` event
   records it as `unmeasured`, and the check reason names it.
3. Given a server whose result changes, then a second file appears beside the first and
   the event records it as `new`.
4. Given unchanged findings already pending in D-1, then a recheck queues no D-2.
5. Given `report-*` directories from an earlier version, then `wuwei doctor` shows a
   `mcp reports` row and `doctor --fix` removes the empty ones and moves each readable
   one to `<server>/<digest>.json`, leaving any a pending decision still references.

### User Story 2 - The decision shows the findings (Priority: P1)

The owner reads the decision, not five JSON files. D-n's context is a table of the
findings with a sanitized snippet, and says per server whether this is the first
measurement or a change since the accepted baseline. Report paths follow as references,
and each exists.

**Why this priority**: the owner cannot accept what they cannot see; the trial planner
could not open the reports.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "decision_table"`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given D-n for a first measurement, then its context table has one
   row per finding with `first measurement` in the last column, and every path under
   `Reports:` exists.
2. Given a server with an accepted baseline from 2026-10-01 and a new digest, then its rows
   read `changed since 2026-10-01`.
3. Given a snippet with `|`, a newline, backticks, `<!--` or a credential, then the cell
   holds none of them (redacted, whitelisted, at most 60 characters) and the record still
   passes `decision.evaluate`.
4. The table has exactly six columns: Server, Tool, Flag, Severity, Snippet, Since. An
   unmeasured server at queue time is one row with `unmeasured` as its flag.

### User Story 3 - The owner decides with one command (Priority: P1)

`wuwei mcp decide D-n proceed` (or `defer`) from the host terminal writes the outcome and
a timestamp into the record, stores the accepted digests as the baseline on proceed, and
re-runs the check, so `plan propose` sees the result. Every surface names that command.

**Why this priority**: the issue's core complaint: no Markdown edits to accept a scan.

**Independent Test**: `python -m pytest -q tests/test_mcp.py -k "decide or help"
tests/test_dashboard.py tests/test_setup.py tests/test_doctor.py`.

**Acceptance Scenarios**:

1. (Issue acceptance 4) Given D-1 pending and `mcp decide D-1 proceed` confirmed at the
   host terminal, then D-1 reads `Decided-by: owner`, `Outcome: proceed` and a `Notes:`
   line with the ISO timestamp, an `accepted-*.json` record holds the `[server, digest]`
   baseline, and the next `mcp check` with the same reports exits 0, queues nothing and
   records the server `unchanged`.
2. Given `mcp decide D-1 defer`, then D-1 reads `Outcome: defer` with the timestamp, no
   baseline is stored, the launch gate still refuses as before, and `mcp decide D-1
   proceed` later still works.
3. Given `mcp decide D-2 proceed` while D-1 is the pending MCP decision, or an option not
   in the record, then exit 1 and nothing written; declined confirmation, exit 1, nothing
   written.
4. Given a seat runs `bin/wuwei mcp decide --help` (or `-h`), then the guard allows it and
   help prints with exit 0; `bin/wuwei mcp decide D-1 proceed` and `bin/wuwei mcp decide
   -- --help` stay refused.
5. Given a pending MCP decision, then the `plan propose` refusal, the check reason, the
   doctor fix, the setup `Still owed` line and the board's command for that D-n each give
   `bin/wuwei mcp decide D-n proceed` and none says to edit the file.

### Edge Cases

- A server named `servers`, `snapshots` or `snapshot-backup` would share a directory with
  registry storage; the adapter reports it unmeasured with a reason naming the collision.
- A scanner result for a measured server that carries no report path, or a path that is
  not `.wuwei/ziran/<that server>/<64 hex>.json` or does not exist, fails the check closed
  (exit 2).
- A check that could not run, a stale record and an interrupted check keep today's
  behaviour (exit 2, snapshot recovery unchanged).
- `mcp decide proceed-unmeasured <server>...` is unchanged.
- A pending decision from v0.12.0 with `report-*` paths stays decidable; those paths
  contribute no baseline pair.

## Requirements

### Functional Requirements

- **FR-001**: The ZIRAN adapter MUST run `watch-registry` into a temporary directory inside
  `.wuwei/ziran/` and, only after the report validates, move it to
  `.wuwei/ziran/<server>/<digest>.json`, where digest is the SHA-256 of the report's
  canonical JSON (`sort_keys`, compact separators). An existing file with that name is
  left untouched. The temporary directory is always removed. A failed run returns no
  report path.
- **FR-002**: The adapter MUST accept one server per config file and validate the server
  name (the registry `NAME` pattern, not one of the storage names) before using it as a
  directory.
- **FR-003**: `mcp.check` MUST require one existing, correctly named report per measured
  server, and record per server `new`, `unchanged` (the file existed before the call) or
  `unmeasured` in the `mcp.checked` payload under `servers`.
- **FR-004**: A server whose `[name, digest]` is in an accepted baseline MUST NOT queue a
  decision, raise the exit code or emit `mcp.finding`; the reason notes it as accepted.
- **FR-005**: A new decision MUST be queued only when a report with a queued severity is
  not already referenced by the pending one.
- **FR-006**: The decision context MUST hold the six-column findings table described in
  story 2, read from the referenced reports and sanitized, followed by `Reports:` with
  each path.
- **FR-007**: `mcp decide <D-n> <option>` MUST, after the existing host confirmation,
  write the outcome and a `Notes: Decided at <timestamp> at the host terminal.` line, emit
  `mcp.decided`, on `proceed` store the baseline pairs and clear the pending decision as
  today, then release the lock and re-run `mcp.check`, returning its exit with the reason
  prefixed by `D-n recorded: <option>`. The bare `mcp decide` form is removed.
- **FR-008**: One helper MUST give the decide command for the pending decision, and every
  surface listed in story 3 scenario 5 MUST use it.
- **FR-009**: The owner-action guard MUST allow an owner command whose words before any
  `--` include exactly `-h` or `--help`.
- **FR-010**: `doctor` MUST report legacy `report-*` directories and `doctor --fix` MUST
  migrate them as in story 1 scenario 5, bound to its preview.

### Key Entities

- **Report**: `.wuwei/ziran/<server>/<digest>.json`, ZIRAN's JSON as written, one per
  server per distinct result, never rewritten.
- **Baseline**: `[server, digest]` pairs in the `baseline` list of an `accepted-*.json`
  record written by `mcp decide ... proceed`; its date is the decision path's day.

## Success Criteria

- **SC-001**: Three checks of an unchanged server leave one report file and one decision.
- **SC-002**: No path named in a decision is missing on disk.
- **SC-003**: Accepting findings takes one command and no file edit.
- **SC-004**: The full test suite passes.

## Assumptions

- `wuwei decide <D-n> <option>` (the generic command in the issue's parentheses) is
  delivered by #354, which chains after this issue and owns "Decisions by command"; this
  issue leaves `mcp.decide(root, decision, option)` callable so #354 wires it in one line.
  The typed-digest confirmation also stays until #354.
- "First measurement" means the server has no accepted baseline, as the issue defines it;
  a server measured clean before and flagged now reads `first measurement`.
- The DM is the planner relaying the check or `plan propose` reason (Remote Control); the
  reason is the one line, and the plan skill says to relay it. No new DM path.
- ZIRAN's `server_name` in a report equals the config key; doctor uses it to place a
  legacy report. A legacy report with no rows (clean) is removed rather than moved.
- The snippet is `current_value` when it is a string, else `message`, else `-`.
- Untrusted text policy: raw descriptions still live only in report files; the decision
  carries a redacted, whitelisted snippet of at most 60 characters, which the issue asks
  for.
- Report filenames use a canonical-JSON digest so key order or whitespace changes in
  ZIRAN's output do not count as a new result; the stored bytes are ZIRAN's own.
- Owner remark relayed with this run (shadow implies observe): main already does this.
  `init --shadow` maps to `posture = observe` (`commands/init.py:41`) and `setup --shadow`
  proposes `security.posture = "observe"` (`commands/setup.py:217-219`); under observe the
  MCP gate warns (`mcp.cached`). No change here.

## Deferred

- `wuwei decide <D-n> <option>`, y/N confirmation, `--workspace`: #354.
