# Feature Specification: delete the telemetry proposals; telemetry and DORA stay

**Feature Branch**: `809-telemetry-proposals-out`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #809, part 6 of the #789 deletion pass: "Delete the telemetry proposals: the rules that turn a week's counts into config proposals for the owner, the `telemetry proposals` action and its question widget, and the `next` row that presents them. Telemetry itself (the weekly counts, preview, off, send) and DORA stay (owner, 2026-10-11)."

## Context

Design 5.13 has three layers: the signals the CLI records, a weekly aggregate computed by the
watch sweep, and proposals derived from a finalised week. The proposals are five fixed rules
(`floor-raise`, `floor-lower`, `area-block`, `wait-hours`, `fast-checks`) in
`telemetry.proposals`, stored in the week file under `proposals` with their inputs under
`evidence`. `wuwei telemetry proposals [--widget]` lists them or prints one yes-or-no card per
proposal once (`presented`, event `telemetry.presented`), and `wuwei next` returns a
`telemetry` card row after the morning gate so the planner asks them.

That is process machinery: a card the model must ask the owner about how WUWEI is tuned,
not about building, reviewing or fixing. It goes. The aggregate, the week files, `metrics
--week`, preview, off, send, anonymous sharing, the OpenTelemetry export and every DORA key
stay unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No proposal card in the day (Priority: P1)

After the morning gate the planner is never asked to present telemetry proposals: `wuwei next`
has no `telemetry` row, and `wuwei telemetry` has only `preview`, `off` and `send`.

**Why this priority**: it is the issue.

**Independent Test**: walk `wuwei next` past the gate and calibration; no `next.action` event
names the `telemetry` state. `wuwei telemetry proposals` is refused by the parser.

**Acceptance Scenarios**:

1. **Given** an approved day with calibration answered, **When** the planner runs
   `wuwei next --json`, **Then** the next row is the first decision, build or close row, and no
   `next.action` event in `events.jsonl` has state `telemetry`.
2. **Given** any workspace, **When** `wuwei telemetry proposals` runs, **Then** the parser
   exits 2 with an invalid-choice message and nothing is written.
3. **Given** any workspace, **When** `wuwei telemetry --help` runs, **Then** it lists
   `preview`, `off` and `send` only.

---

### User Story 2 - Telemetry and DORA keep working (Priority: P1)

The weekly aggregate, every 5.13 metric including the DORA keys, the week files, preview,
off, send, anonymous sharing and the OpenTelemetry export behave as before.

**Why this priority**: the owner keeps telemetry and DORA (2026-10-11).

**Independent Test**: the existing tests of `tests/test_telemetry.py` and `tests/test_dora.py`
for aggregation, sharing, preview, off, send and OTLP pass unchanged apart from the removed
proposal assertions.

**Acceptance Scenarios**:

1. **Given** two seeded days in a finished week, **When** the week is finalised, **Then** the
   file holds `schema`, `week`, `versions`, `config`, `metrics` and `final: true`, with no
   `proposals` and no `evidence` key, and the metrics are the same values as before.
2. **Given** a week file with `shared` and `ready`, **When** the week is recomputed, **Then**
   those marks are kept.

---

### User Story 3 - A stored week with proposals still loads (Priority: P1)

A workspace upgraded from a version that wrote proposals keeps its week files. A final week
that carries `proposals`, `evidence` and `presented` loads, previews and shares as before;
the extra keys are ignored and never leave the machine.

**Why this priority**: the issue's second acceptance line; no upgrade step is added.

**Independent Test**: save a final week with the three legacy keys; `telemetry.load_week`
returns it, `wuwei telemetry preview` exits 0 and prints no `proposals` text, and
`telemetry.validate(telemetry.payload(found))` passes.

**Acceptance Scenarios**:

1. **Given** `.wuwei/metrics/2026-W39.json` with `proposals`, `evidence` and `presented`,
   **When** `wuwei telemetry preview` runs, **Then** it exits 0 and the payload it prints has
   only the 5.13 payload keys.
2. **Given** the same file, **When** sharing builds its payload
   (`telemetry.validate(telemetry.payload(found, token=...))`, the call `_share` and preview
   make), **Then** it validates and holds none of the legacy keys.

### Edge Cases

- A day's `events.jsonl` written before the upgrade holds a `telemetry.presented` event: it
  is read like any unknown kind (no reader depends on it).
- A week finalised before the upgrade is never recomputed, so its legacy keys stay on disk;
  nothing reads them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `telemetry.proposals` and the five rules MUST be deleted.
- **FR-002**: `telemetry.aggregate` MUST NOT return an `evidence` key; the external-wait
  computation that only fed it MUST go. Every metric value MUST stay the same.
- **FR-003**: `telemetry.week_file` MUST NOT add `proposals` to a final week and MUST NOT
  carry `presented` from the previous file; it keeps carrying `shared`, `ready` and `otlp`.
- **FR-004**: `wuwei telemetry` MUST offer `preview`, `off` and `send` only; the `proposals`
  action, its `--widget` flag and `_proposals` MUST be deleted.
- **FR-005**: `wuwei next` MUST NOT return a `telemetry` row.
- **FR-006**: The `telemetry.presented` event kind MUST be removed from the classifier's
  silent list and from the reserved-event map; no code writes it.
- **FR-007**: `telemetry.load_week`, `latest_final`, `payload`, `validate`, preview and send
  MUST accept a stored week that carries `proposals`, `evidence` or `presented`.
- **FR-008**: Where they still exist at rebase, the guide widget list and the
  `commands.WRITES` set MUST drop `telemetry proposals`, and `docs/site/agent.md`'s generated
  block MUST match the guide.
- **FR-009**: The design spec 5.13 and the docs pages MUST stop describing proposals; the
  constitution sentence about telemetry proposals MUST go.

### Key Entities

- **Week file** (`.wuwei/metrics/<week>.json`): `schema`, `week`, `versions`, `config`,
  `metrics`, `final`, and the marks `shared`, `ready`, `otlp`. Legacy files may also hold
  `proposals`, `evidence`, `presented`, which nothing reads.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `grep -n "proposals" cli/wuwei/telemetry.py cli/wuwei/commands/telemetry.py
  cli/wuwei/commands/next.py` finds nothing.
- **SC-002**: The touched test files pass: `tests/test_telemetry.py`, `tests/test_next.py`,
  `tests/test_signal_status.py`, `tests/test_handback.py`, `tests/test_parallel_dispatch.py`,
  `tests/test_docs.py`, `tests/test_dora.py`, `tests/test_telemetry_worker.py`.
- **SC-003**: No test is loosened: every removed assertion covered deleted code.

## Assumptions

- No config key is retired: proposals had no key of their own. `telemetry.enabled` stays and
  now stops the aggregate, sharing and the export. `decisions.wait_hours` stays (its other
  reader is the decision router, a later part). Nothing to add to `workspace.RETIRED`.
- No upgrade step: legacy keys in old week files are harmless and are not rewritten, so no
  migration and no `init --upgrade` change.
- `telemetry.presented` is not kept in the classifier for old logs: an old event on the
  upgrade day classifies as an unknown kind for that day only, and nothing counts it.
- `latest_final` stays: preview and send read it through `_final`.
- `decision.weekday_hours` stays: the decision router also calls it.
- The design spec is amended by the owner's instruction in #789 (owner, 2026-10-11); each
  edited passage in 5.13 is marked with that date and issue. The constitution sentence goes
  with a patch version bump and a dated amendment line.
- Order: part 6 merges after parts 3 to 5. Part 3 (#800) deletes `guide.py`,
  `commands.WRITES`, the agent.md generated block and the guide assertion of
  `test_telemetry_is_documented`; part 4 (#801) renames the classifier tier `nudge` to `warn`.
  Edits to files or lines a merged part removed are skipped.
- The pass plan's PR 6 line predates the owner's call; this spec follows the issue: only the
  proposals go.
