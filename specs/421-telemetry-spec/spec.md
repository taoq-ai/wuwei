# Feature Specification: Telemetry: an execution signal set recorded at no hook cost, weekly aggregation into effectiveness metrics with proposals, and anonymous sharing the owner can turn off

**Feature Branch**: `421-telemetry-spec`
**Created**: 2026-10-03
**Status**: Ready for verification (the amendment text is already in the working tree)
**Input**: Issue #421, spec(telemetry), with the owner's addition of 2026-10-03 ("anonymous
means no login"). Adds design section 5.13 and one constitution constraint, before the
implementation (#422, same chain). References: 5.6 owner metrics, #288 quality by hour,
#302 loops and asks, #280 escaped defects, #287 heartbeat, #278 calibration proposals,
#174 draft queue, #359 widgets, #346 hook latency, #414 owner yes or no.

## Root cause (read on main, 9434cc0)

A spec gap, not a runtime failure; the orchestrator notes name no dry-run workspace to
reproduce against. What exists and what is missing:

- The raw signals mostly exist as events: `hook.refusal` (`cli/wuwei/commands/hook.py`
  `refuse`), `guard.would_refuse` (`hook.py` `posture`), `seat launched`, `seat stopped`,
  `seat.usage` (`cli/wuwei/dispatch.py`, `cli/wuwei/state.py`), `gate.received`,
  `gate.tiered` (`dispatch.py`), `build.parked` (`cli/wuwei/commands/build.py`),
  `decision.routed` (`cli/wuwei/decision.py` `route_owner`), `decision.decided`,
  `decision.reversed`, `negotiation.loop` (`cli/wuwei/steward.py`), the `remote.*` events,
  and the heartbeat record (`cli/wuwei/heartbeat.py` `beat`).
- Two facts are lost today. The guard's exit code: `hook.py` `run` appends
  `(guard.check, message)` and drops `code`, so a refusal (exit 1) and a guard that could
  not run (exit 2) look the same in `hook.refusal` and `guard.would_refuse`. The hook
  latency: `heartbeat.measure` receives `(code, line, ms)` per probe call from
  `adapters/watch_service.py` `probe`, and `_exit` keeps only the code.
- `cli/wuwei/metrics.py` `collect` is a per-day view that also calls the code host (`gh`)
  and reads Claude Code transcripts; nothing aggregates a week, nothing runs it
  periodically, nothing turns numbers into proposals, nothing is shared.
- The constitution says "No hosted service or database", which an anonymous collector
  would contradict unless it is stated as the project's, outside the plugin.

## User Scenarios & Testing

### User Story 1 - The #422 builder finds every telemetry decision in 5.13 (Priority: P1)

The builder of #422, a reviewer or the owner reads design section 5.13 and finds the
signal vocabulary and its version, the recording rule, the aggregation point and budget,
each derived metric with its definition, the proposal rules with their commands, the
sharing modes, the payload and its anonymisation rules, the config keys and defaults, and
the interview question, each stated once.

**Independent Test**: the phrase check in plan.md "Verification commands" fails on a
`git archive main` export and passes on the worktree.

**Acceptance Scenarios**:

1. Given the amended spec, then section 5.13 defines the signal vocabulary and version
   (`schema`, starting at 1), the recording rule (two fields on existing records, no record
   and no step in a hook), the aggregation point (one watch-sweep step at most once per 24
   hours) and budget (10 s wall, 20 MB per `events.jsonl`, `telemetry.skipped`), the
   derived metrics with their definitions (one table), the proposal rule (fixed rules, one
   owner command each, nothing applied on its own), the sharing payload and its
   anonymisation, the config keys and defaults (`enabled`, `share`, `endpoint`,
   `repository`), and the interview question.
2. Given the spec, then #422 can be built without further design decisions: every file,
   event kind, command, threshold and default it needs is named in 5.13 or in plan.md.

### User Story 2 - Anonymous means no login (Priority: P1)

The owner chooses whether anything leaves the machine and, if so, whether it is tied to
their GitHub account.

**Independent Test**: the same phrase check (sharing and interview phrases).

**Acceptance Scenarios**:

1. Given 5.13, then `share` is unset until the interview asks and behaves as off; the
   interview offers Anonymous first, then Attributed, then Off, and states the sender
   difference in one line.
2. Given `share = "anonymous"`, then the payload goes as JSON over HTTPS to `endpoint`
   with a random per-workspace token as the only identifier, no login and no secret in the
   plugin; an unreachable endpoint keeps the week locally and never blocks.
3. Given `share = "attributed"`, then the owner sends the week as a GitHub issue from
   their own `gh` account through an owner command with a yes or no; the issue carries no
   token.
4. Given either mode, then `wuwei telemetry preview` prints exactly what would be sent and
   `wuwei telemetry off` stops sharing at once.

### User Story 3 - The constitution states the hook rule and the collector (Priority: P1)

**Acceptance Scenarios**:

1. Given the constitution, then it says telemetry adds no record and no step to a hook,
   aggregation runs only in CLI commands, and what it derives is a proposal the owner
   applies; and the no-hosted-service constraint names the project's optional collector as
   outside the plugin.

### User Story 4 - Nothing else moves (Priority: P1)

**Acceptance Scenarios**:

1. Given the change, then only `docs/specs/2026-09-24-wuwei-design.md`,
   `.specify/memory/constitution.md` and `specs/421-telemetry-spec/` differ from main, and
   the full suite passes.

### Edge Cases

- A week with no traces and no refusals: rates are `"unmeasured"`, never zero.
- The workspace's first day falls in an earlier week than the one aggregated:
  `first_hour_refusals` is absent from that week.
- A day directory archived (older than 30 days) is not read; aggregation covers `days/`
  only, and at most the last four weeks are finalised or retried.
- `endpoint` empty (the project has not deployed the collector yet) under `anonymous`:
  `telemetry.unsent`, the week is kept, and the preview says nothing would be sent.
- A configured value the vocabulary does not know (an adapter name not shipped): the
  payload fails validation and is not sent.
- An attributed week after anonymous weeks: the issue carries no token, so it cannot tie
  the anonymous weeks to the owner.
- The watch is not running: nothing aggregates; `wuwei metrics --week` computes a week on
  demand.

## Requirements

### Functional Requirements

- **FR-001**: Design section 5.13 MUST exist, titled `### 5.13 Telemetry (owner, 2026-10-03,
  #421)`, placed after 5.9 (after 5.12 once #411, #416 and #418 merge).
- **FR-002**: 5.13 MUST define the config keys and defaults: `telemetry.enabled` true,
  `telemetry.share` `""` (behaves as off; values `anonymous`, `attributed`, `off`),
  `telemetry.endpoint` the project's collector URL (empty until deployed),
  `telemetry.repository` `taoq-ai/wuwei`; and that a calibration profile never carries a
  `telemetry` key.
- **FR-003**: 5.13 MUST define the signal vocabulary from existing events, the two added
  fields (`exit` on refusal rows and `guard.would_refuse`; `ms` on the heartbeat's four
  hook probes), and `schema` as the version.
- **FR-004**: 5.13 MUST define one aggregation point (the watch sweep, at most once per 24
  hours), the output `.wuwei/metrics/<week>.json` (CLI-written, protected), the budget and
  its `telemetry.skipped` event, and `wuwei metrics --week`.
- **FR-005**: 5.13 MUST define each weekly metric in one table, with `"unmeasured"` for a
  value that cannot be computed.
- **FR-006**: 5.13 MUST define the proposal rules (`floor-raise`, `floor-lower`,
  `area-block`, `wait-hours`, `fast-checks`) with thresholds and one owner command each,
  presented once per final week at the morning gate through `wuwei telemetry proposals
  --widget` and never applied on their own.
- **FR-007**: 5.13 MUST define the payload, the anonymisation rules checked before every
  send and by the collector, and the three modes with their events (`telemetry.unsent`,
  `telemetry.shared`, `telemetry.ready`, `telemetry.off`, `telemetry.presented`), the
  owner command `wuwei telemetry send`, `wuwei telemetry preview` and `wuwei telemetry off`.
- **FR-008**: 5.13 MUST define the interview question and its three choices in order.
- **FR-009**: 5.13 MUST define the project side: `scripts/telemetry-worker/` (validation,
  one payload per token and week, dataset writes with a worker-only bot token, deploy
  note, `summary.py`) and the label workflow for attributed issues; and state the residual
  risks.
- **FR-010**: The design spec MUST stay consistent: the non-goal on hosted services, the 3.3
  workspace layout (`metrics/`), the 5.9 nudge list and the section 8 `code_host` row
  (`issue(repo, title, body)`) point to 5.13.
- **FR-011**: The constitution MUST carry the telemetry constraint and name the collector
  as outside the plugin; version 1.2.0, amended 2026-10-03.
- **FR-012**: No runtime, test, template or site file changes in this feature.
- **FR-013**: 5.13 MUST define the OpenTelemetry mapping (day as trace, hook calls and seat
  runs as spans with the `wuwei.*` attributes, span events, counters and histograms) and the
  optional `[telemetry.otlp]` exporter (`endpoint`, `headers_env`, OTLP/HTTP JSON from the
  watch sweep with stdlib only, an `otlp_at` mark, retry without blocking), never sent to
  the project (owner addition, 2026-10-03).

### Key Entities

- **Weekly aggregate**: `.wuwei/metrics/<week>.json`: `schema`, `week`, `final`, facts,
  metrics, proposals, `shared`, `presented`.
- **Payload**: the shareable subset of a final aggregate (`schema`, `week`, versions,
  facts, metrics), plus `token` in anonymous mode only.
- **Proposal**: rule, evidence line, one owner command.

## Success Criteria

- **SC-001**: The phrase check fails on main and passes on the worktree.
- **SC-002**: `git diff --stat main` lists only the design spec, the constitution and
  `specs/421-telemetry-spec/`.
- **SC-003**: `python -m pytest -q` passes, `tests/test_docs.py` included.
- **SC-004**: No em-dash, emoji or absolute local path in any changed file.

## Assumptions

- The amendment text is written by the spec author, as for #301; the builder of this
  feature verifies and reviews it and writes no runtime code.
- Hook latency comes from the heartbeat's existing probes (every clock tick), not from a
  clock in the hook. The issue's `telemetry.sample_rate` is dropped: an in-hook clock and
  append would contradict "nothing new runs in a hook" and the owner's "telemetry should
  not impact performance".
- The issue's `share_every = "week"` is dropped: a value that never changes is a constant
  (constitution V).
- The issue's `share_auto` is dropped. An issue opened from the owner's account on another
  organisation's repository is approve-tier outbound (4.9), and 9.1 makes approve-tier
  text a floor no setting lowers. The automatic mode is the anonymous one, which carries
  no identity; attributed is always the owner's yes.
- Attributed issues go through an owner command (`wuwei telemetry send`, yes or no per
  #414) instead of the #174 draft queue: the draft approve path runs the outward-text lint,
  whose internal-state patterns (`wuwei`, `claude`, `agents`) would refuse a body that
  names the runtime adapter. The canary and honeytoken checks still apply.
- Aggregation runs at one point, the watch sweep, at most daily, instead of the issue's
  five (watch ticks, close, report, retro, consolidate): one call site, one budget, and the
  sweep already runs off the hook path. `wuwei metrics --week` covers on-demand reads.
- Proposals are presented at the morning gate (where cruise promotions are approved,
  5.8.1), not also in the retro. Cruise promotion is not a telemetry rule; the steward
  already proposes it. "Switch a gate" has no rule: no recorded signal says a gate is
  wrong beyond the tier floor rules; it is added when such evidence exists.
- Reason codes are the guard module name plus the exit class (1 refused, 2 could not run).
  Refusal reasons are free text and never leave the machine; a per-guard code vocabulary
  is not built.
- The board does not show telemetry in #422; `wuwei metrics --week` does.
- The collector's default URL does not exist yet. `telemetry.endpoint` ships empty, so
  anonymous weeks stay local until the project deploys `scripts/telemetry-worker/` and sets
  the default in `cli/wuwei/workspace.py`. Deploying it, and creating the dataset
  repository and the bot token, are owner steps outside the plugin.
- The collector targets a serverless worker with a Python runtime (for example Cloudflare
  Python Workers): the validation is a pure function the repository's pytest imports, and
  the platform entry is a thin wrapper. The platform is the owner's choice at deploy time.
- `gh issue create` cannot set a label for an author without push access, so the client
  sends none; a repository workflow labels issues by their `telemetry: ` title.
- Section 5.13 is numbered after the 5.10, 5.11 and 5.12 amendments in this wave (#411,
  #416, #418); on this branch it follows 5.9, and the merge places it after 5.12.
- The OpenTelemetry addition was added to 5.13 by the builder; the first draft of this
  spec missed it. The issue's `[telemetry.otlp] every` is dropped: the export runs on every
  watch sweep, a constant. It runs from the sweep only, not from `close`, because `close`
  can run in a seat and 5.13 keeps telemetry work out of seats. Hook-call spans have no
  duration because hooks keep no clock. Docs (one OpenTelemetry paragraph shaped like
  ZIRAN's guide) and the on-call seat reading alerts from the same platform (#415) are
  left to #422 and #415.
