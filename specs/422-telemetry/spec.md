# Feature Specification: Telemetry: signals on existing records, weekly aggregation off the hook path, metrics with proposals, and sharing the owner chooses

**Feature Branch**: `422-telemetry`
**Created**: 2026-10-03
**Status**: Ready for planning
**Input**: Issue #422, feat(telemetry), with the owner's two additions of 2026-10-03
("anonymous means no login" and "OpenTelemetry"). Implements design section 5.13
(`docs/specs/2026-09-24-wuwei-design.md`, added by #421, merged as ea5aceb). Where the issue
text and 5.13 differ, 5.13 wins (constitution: the design spec is the source of truth); each
difference is listed under Assumptions.

## Root cause (read on main, ea5aceb)

A missing feature, not a runtime failure; the orchestrator notes name no dry-run workspace.
What exists and what is missing, read in the worktree:

- Two facts are dropped at the point they are known. `cli/wuwei/commands/hook.py` line 111
  appends `(guard.check, message)` and discards `code`, so `refuse` (line 330) writes
  `{'guard', 'reason'}` rows and `posture` (line 259) writes `guard.would_refuse` without the
  exit class: a refusal (exit 1) and a guard that could not run (exit 2) look the same.
  `cli/wuwei/heartbeat.py` `_exit` (lines 36 to 37) receives `(code, line, ms)` from
  `adapters/watch_service.py` `probe` and keeps only the code, so the hook latency the
  heartbeat measures every clock tick is lost.
- `cli/wuwei/metrics.py` `collect` (line 498) is a per-day view that also calls the code host
  and reads transcripts. Nothing aggregates a week, `cli/wuwei/watch.py` `sweep` (lines 236 to
  304) has no telemetry step, nothing proposes from the numbers, nothing is shared, and
  `[telemetry]` is not in `workspace.SCHEMA` (line 45).
- No `wuwei telemetry` command, no `issue` operation on the code host port, no `post` beside
  `ping` in the watch-service adapter, no interview question, no collector.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner sees whether WUWEI itself works, week by week (Priority: P1)

The watch computes a weekly aggregate from the events the CLI already records, at most once
a day, off the hook path, and the owner reads it with `wuwei metrics --week` or on the board.

**Independent Test**: a fixture workspace with a seeded ISO week of day directories; run the
telemetry step and `wuwei metrics --week`; compare with the expected dict.

**Acceptance Scenarios**:

1. **Given** a seeded week of events (refusals with exit 1 and 2, warnings, heartbeat probes
   with `ms`, seats launched and stopped, approvals and phase moves to `merged` and `fix`,
   gate rounds and tiers, a negotiation loop, a park, routed, decided and reversed decisions
   with `Class:` lines, owner host actions and `remote.*` events, traces), **When** the watch
   sweep runs the telemetry step, **Then** `.wuwei/metrics/<week>.json` holds every metric key
   of the 5.13 table with the expected values, a value that cannot be computed is
   `"unmeasured"` (never zero), and `wuwei metrics --week <week>` and the board's Telemetry
   table show the same values.
2. **Given** a day over the aggregation budget (an `events.jsonl` over the byte cap, or the
   wall-time budget spent), **When** the step runs, **Then** it stops, keeps the previous week
   file, records exactly one `telemetry.skipped` event with the week and the reason, the
   board's Telemetry table says `unmeasured` with that reason, and the sweep's exit is
   unchanged.
3. **Given** the step ran less than 24 hours ago, **When** the sweep runs again, **Then**
   nothing is aggregated.
4. **Given** `telemetry.enabled = false`, **When** the sweep runs, **Then** no aggregate, no
   proposal, no share and no export happens, and the day's events are recorded as before.

### User Story 2 - No hook does more work (Priority: P1)

Telemetry adds two fields to records that already exist and nothing else to a hook.

**Independent Test**: the hook tests in `tests/test_hooks.py` and `tests/test_heartbeat.py`.

**Acceptance Scenarios**:

1. **Given** the hook tests, **When** a call is allowed, refused or warned, **Then** it appends
   0, 1 and 1 events respectively (pinned per path), the refusal rows and the
   `guard.would_refuse` record carry `exit` (1 or 2), and the import-graph tests pass with
   `wuwei.telemetry` added to the modules a hook must never load.
2. **Given** a heartbeat tick, **When** the four hook probes (`refused`, `allowed`,
   `state_write`, `read_loop`) return, **Then** each probe row carries `ms`, and the probe
   calls still record no refusal.

### User Story 3 - Proposals from a finalised week (Priority: P2)

A finalised week evaluates the five fixed rules of 5.13; each proposal carries its rule, one
line of evidence and one owner command, presented once at the next morning gate, never
applied on its own.

**Independent Test**: three aggregate fixtures, one per proposal kind, through
`telemetry.proposals`; a table test for all five rules at and below their thresholds.

**Acceptance Scenarios**:

1. **Given** finalised aggregates meeting `floor-raise`, `area-block` and `wait-hours`,
   **Then** each yields one proposal naming the rule, its evidence and exactly the 5.13
   command (`bin/wuwei config set repos.<n>.gates.floor '"<next tier>"'`,
   `bin/wuwei config set security.areas.<area> '"block"'`,
   `bin/wuwei config set decisions.wait_hours <n>`).
2. **Given** a final week with proposals not yet presented, **When**
   `wuwei telemetry proposals --widget` runs, **Then** it prints one yes-or-no widget per
   proposal (yes recommended, the command as `record`) and records `telemetry.presented`
   once; a second run prints `[]`. Without `--widget` it lists them and writes nothing.

### User Story 4 - Sharing is the owner's choice, and anonymous means no login (Priority: P1)

**Independent Test**: `tests/test_telemetry.py` with a fake watch service and a fake code host;
no network.

**Acceptance Scenarios**:

1. **Given** `share = "anonymous"` or `"attributed"` and a final week, **When**
   `wuwei telemetry preview` runs, **Then** the payload holds exactly `schema`, `week`,
   `versions`, `config`, `metrics` (plus `token` for anonymous), contains no repository name,
   path, handle, ticket, item id, reason text or time finer than the ISO week (the
   anonymiser corpus seeds each kind into the week and asserts none reaches the payload, and
   `telemetry.validate` rejects each kind injected as a key or value), and the attributed
   issue body the send opens equals the body the preview prints.
2. **Given** `share` unset (`""`), **When** the sweep runs, **Then** nothing is posted and no
   issue is opened, and `wuwei doctor` lists the telemetry interview question as pending
   with the command that asks it.
3. **Given** `wuwei telemetry off`, **Then** `config.toml` has `share = "off"` without a
   confirmation and one `telemetry.off` event is recorded.
4. **Given** `share = "anonymous"`, **When** the sweep finalises a week, **Then** the payload
   is posted as JSON over HTTPS to `endpoint` with the workspace token; 2xx or 409 records
   `telemetry.shared` and marks the file; no endpoint, a network error or another status
   records `telemetry.unsent` and keeps the week for the next run (four newest weeks at most);
   nothing blocks.
5. **Given** `share = "attributed"`, **When** the sweep finalises a week, **Then** it records
   `telemetry.ready` once; `bin/wuwei telemetry send` (an owner action refused from agent
   tools) prints the issue, asks yes or no on the host terminal, runs the canary and
   honeytoken check, and opens it through the code host port without the token.

### User Story 5 - The owner's own OpenTelemetry platform (Priority: P3)

**Independent Test**: fixture day through `telemetry.spans` and `telemetry.otlp_metrics`, a
fake watch service.

**Acceptance Scenarios**:

1. **Given** `[telemetry.otlp] endpoint` set, **When** the sweep runs, **Then** the records
   appended since the `otlp_at` mark are posted as OTLP/HTTP JSON to `<endpoint>/v1/traces`
   with the `wuwei.*` attributes and no command text or reason, and each newly finalised week
   to `<endpoint>/v1/metrics`; the mark advances only on a 2xx answer; a failure records
   `telemetry.unsent` with mode `otlp`; the header value named by `headers_env` never appears
   in events or output.

### User Story 6 - The project side (Priority: P3)

**Acceptance Scenarios**:

1. **Given** `scripts/telemetry-worker/`, **Then** its pure `accept` function validates with
   the same `telemetry.validate`, accepts only a week among the four ISO weeks before the week
   of receipt, answers 409 for a repeat token and week, 429 past the per-IP or daily limit,
   and returns the dataset path `data/<week>/<token>.json`; `summary.py` summarises a dataset
   directory; a repository workflow labels issues titled `telemetry: `.

### Edge Cases

- A week with no traces and no refusals: rates are `"unmeasured"`.
- The workspace's earliest day falls outside the week: `first_hour_refusals` is absent.
- A `hook.refusal` without rows (a config that does not load, #326) counts as guard `config`,
  exit 2. A row written before this change (no `exit`) counts as exit 1.
- A heartbeat probe that timed out carries no `ms` and is not in `hook_latency_ms`.
- An adapter name that is not shipped, or an empty plugin version: the payload fails
  validation and `telemetry.unsent` records the rule; nothing is sent.
- A calibration profile with a `telemetry` key: refused on import and dropped on export.
- The watch not running: nothing aggregates; `wuwei metrics --week` computes on demand.
- A day directory archived (older than retention) is not read.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `hook.py` MUST keep each guard's exit code and write it as `exit` on each
  `hook.refusal` refusal row and on `guard.would_refuse`, with no new append, import or step.
- **FR-002**: `heartbeat.measure` MUST add `ms` to the `refused`, `allowed`, `state_write` and
  `read_loop` probe rows when the call returned an exit code.
- **FR-003**: `workspace.SCHEMA` MUST define `[telemetry]` (`enabled` true, `share` `""` with
  values `""`, `off`, `anonymous`, `attributed`, `endpoint` `""`, `repository`
  `taoq-ai/wuwei`) and `[telemetry.otlp]` (`endpoint` `""`, `headers_env` `""`), and the
  config cache version MUST change.
- **FR-004**: The watch sweep MUST run one telemetry step at most once per 24 hours (a
  `telemetry_at` mark) that refreshes the current week (`final: false`) and finalises each
  earlier week of the last four that has day directories and no final file (`final: true`,
  with proposals), within 10 seconds of wall time and 20 MB per `events.jsonl`, recording
  `telemetry.skipped` past either. The step MUST never change the sweep's exit or owed counts.
- **FR-005**: The aggregate MUST compute every metric of the 5.13 table from `events.jsonl`,
  `traces.jsonl` line counts, day state and decision records only; it MUST never call an
  adapter or read transcripts.
- **FR-006**: `.wuwei/metrics/` MUST be a protected record (`protect_state`), written only by
  the CLI with the shared atomic writer.
- **FR-007**: `wuwei metrics --week [<week>]` MUST print a week's file, computing and writing
  it when absent.
- **FR-008**: `telemetry.proposals` MUST implement exactly the five 5.13 rules with their
  thresholds and commands; `wuwei telemetry proposals [--widget]` MUST present them as 5.13
  states.
- **FR-009**: `telemetry.payload` and `telemetry.validate` MUST implement the 5.13 payload and
  anonymisation rules (allowlisted keys, value patterns, 16 KB cap); no payload is sent or
  shown as sendable without passing `validate`.
- **FR-010**: Anonymous mode MUST post from the sweep through the watch-service adapter
  (stdlib `urllib`, `https://` only, 5 second timeout) with the token from
  `.wuwei/metrics/token` (`secrets.token_hex(16)`, created on first use).
- **FR-011**: Attributed mode MUST record `telemetry.ready` once per final week and send only
  through `bin/wuwei telemetry send` (owner action, host confirm, `security.outbound`, code
  host `issue(repo, title, body)`), title `telemetry: <week>`, body a two-column Markdown table
  of the payload without the token.
- **FR-012**: `wuwei telemetry preview [<week>]` MUST print exactly what each mode would send
  and the mode in force; `wuwei telemetry off` MUST set `share = "off"` without confirmation
  and record `telemetry.off`.
- **FR-013**: Every `telemetry.*` kind MUST be CLI-only (event command producers);
  `telemetry.ready` is a nudge and the rest are silent.
- **FR-014**: The interview MUST ask the 5.13 question after `posture` with the three choices
  and texts in order; `doctor` MUST show it as pending while `share` is `""` and telemetry is
  enabled; a calibration profile MUST never carry a `telemetry` key.
- **FR-015**: The OTLP exporter MUST post from the sweep only, with stdlib only, carry only the
  `wuwei.*` attributes and counts, advance `otlp_at` only on 2xx, and record failures as
  `telemetry.unsent` with mode `otlp`.
- **FR-016**: `scripts/telemetry-worker/` MUST hold `worker.py` (pure `accept` plus a thin
  platform entry), `summary.py` and a deploy `README.md`; `.github/workflows/telemetry-label.yml`
  MUST label issues whose title starts with `telemetry: `.
- **FR-017**: Docs MUST cover the config keys, the commands, the heartbeat `ms`, what leaves
  and what never does (security page), and one OpenTelemetry paragraph; the plan skill MUST
  run `wuwei telemetry proposals --widget` after the morning gate.

### Key Entities

- **Weekly aggregate** (`.wuwei/metrics/<week>.json`): see data-model.md.
- **Payload**: the shareable subset of a final aggregate; see data-model.md.
- **Proposal**: `{rule, evidence, command}`.
- **Token** (`.wuwei/metrics/token`): 32 hex characters, the only anonymous identifier.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every acceptance scenario above has a test that failed before its code and
  passes after.
- **SC-002**: The per-hook event count and the hook import graph are unchanged (pinned tests).
- **SC-003**: `python -m pytest -q` passes; no network in any test.
- **SC-004**: No em-dash, emoji or absolute local path in any changed file.

## Assumptions

- 5.13 is the contract; the issue body predates it. Dropped or reshaped from the issue, as
  #421 already recorded: `sample_rate` (no clock in a hook), `share_every` (a constant),
  `share_auto` (attributed is always the owner's yes, 4.9 floor), `share = true` (now
  `"anonymous"`, `"attributed"` or `"off"`), `wuwei telemetry share` (now `send`, attributed
  only; anonymous sends from the sweep), aggregation in close, report, retro and consolidate
  (one point: the sweep, plus `metrics --week` on demand), `[telemetry.otlp] every` (every
  sweep), the issue template (the label workflow finds issues by title).
- The issue's proposal acceptance ("two long loops and a high refusal rate under guarded") is
  restated with 5.13's rules: 5.13 has no long-loop or refusal-rate rule (a new rule amends
  5.13), and proposals never name items. The three fixtures are `floor-raise`, `area-block`
  and `wait-hours`; the table test covers all five.
- The board shows telemetry, contrary to #421's assumption, because #422's acceptance names
  the board: one Telemetry table from the current week's file, or `unmeasured` with the reason
  when today's step skipped.
- The `telemetry_at` mark lives in the day state's `watch` record like `steward_at`, so the
  first sweep of a new day may run again before 24 hours have passed: at most once per
  calendar day. The mark advances on every attempt, skipped or not; the next day retries.
- Hook latency counts only probe calls that returned; a timed-out probe has no `ms` (its
  value is the timeout, not the hook's time) and stays `unmeasured` in the heartbeat.
- A refusal row recorded before this change has no `exit` and counts as exit 1, what it was
  recorded as.
- The attributed issue goes through the code host API (`POST repos/<repo>/issues` through the
  existing allowlisted `_api`), from the owner's `gh` login, instead of `gh issue create`.
- The OTLP export reads `events.jsonl` only (the source of truth): hook-call spans are the
  refusal and warning records; allowed calls live in `traces.jsonl`, which carries tool
  arguments and is not exported. A `ponytail:` comment names that ceiling.
- `wuwei telemetry preview` creates the token when absent, so the anonymous payload it prints
  is exactly the one sent.
- `wuwei telemetry off` is not an owner-only action: it only narrows what leaves.
- Glossary entries for telemetry are not added (no glossary test needs them).
- The worker's platform entry (a serverless Python worker) is a thin untested wrapper over the
  pure `accept`; deploying it, the dataset repository and the bot token are owner steps.
- Spec-kit strict mode steps `clarify`, `analyze` and `checklist` are not run by this spec
  author (the brief scopes steps 1 to 4); no clarification was needed.
