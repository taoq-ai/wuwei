# Feature Specification: Shadow mode: hooks record what they would refuse, for a first week on a project

**Feature Branch**: `308-shadow-mode`
**Created**: 2026-10-02
**Status**: Draft
**Input**: Issue #308, feat(guards). Design spec 4 (guards, hook table 4.1, profiles 4.4),
4.5 (matching and bypass resistance), 9.1 (threat model and guard scope); builds on #278
(calibrate), #279 (interview), #222 (owner-action table), #114 (producer-only events),
#303 (owner verbosity). Evidence: owner agreement 2026-10-02.

## Root cause (read on main, b420c12)

The orchestrator notes name no dry-run workspace; this is missing behaviour, read from code:

- `cli/wuwei/commands/hook.py:53-87` `run` turns every guard result with a nonzero code into
  a reason (`reasons.append(message)`, line 76) and every reason into a refusal
  (`refuse(...)`, lines 85-87). Nothing between the guard result and the exit code reads a
  mode, so a new owner gets every refusal from the first command.
- `cli/wuwei/workspace.py:37-148` `SCHEMA` has no `guards` table. Reproduced read-only in a
  scratch workspace: a `config.toml` with `[guards]` and `mode = "shadow"` fails
  `load_config` with `config.toml: unknown key guards at line 1`.
- `cli/wuwei/guards/__init__.py:40-44` `Guard` records carry no module name; the module is
  reachable as `guard.check.__module__` (precedent: `tests/test_guard_mutation.py:173`).
- No `guard.would_refuse` kind in `cli/wuwei/commands/event.py:11-68` or
  `cli/wuwei/signal.py:6-23`; no shadow part in `cli/wuwei/commands/status.py:254-275`
  `line`; no shadow nudge in `scan` (lines 26-175); no shadow line in
  `cli/wuwei/guards/lifecycle.py:26-79` `session_start`; no `--shadow` in
  `cli/wuwei/commands/init.py:26-34`; no guards question in `cli/wuwei/interview.py:64-170`;
  no shadow section in `cli/wuwei/report.py:25-91`; no `shadow` command.

## User Scenarios & Testing

### User Story 1 - Shadowed refusals are recorded, not enforced (Priority: P1)

An owner trying WUWEI on real work sets `guards.mode = "shadow"`. Every guard still runs as
today. When a shadowable guard would refuse, the hook records a `guard.would_refuse` event
and exits 0, so the session keeps working.

**Independent Test**: replay a PreToolUse force push through the hook in a workspace whose
config says `mode = "shadow"`; check the exit code and the event.

**Acceptance Scenarios**:

1. Given shadow mode and a force push (`git push --force origin main`) through PreToolUse,
   when the hook runs, then it exits 0 with no deny output, and today's `events.jsonl` holds
   one `guard.would_refuse` event whose payload has `guard` `commit_push`, the guard's
   `reason`, `target` (the normalised command), `session` (the payload session id) and
   `item` (the item this session claims, or null); no `hook.refusal` event is written; and
   `wuwei shadow report` lists it under `commit_push`.
2. Given shadow mode and a Stop, SubagentStop, PostToolUse or PreCompact guard that would
   refuse, then the hook exits 0 and records the same event.
3. Given shadow mode and the heartbeat probe session (`wuwei-heartbeat`), then refusals are
   enforced exactly as in enforce mode, so the heartbeat keeps measuring real guards.
4. Given shadow mode and an event that cannot be recorded (the append raises), then the
   refusal is enforced as in enforce mode and stderr says it could not be recorded (fail
   closed).

### User Story 2 - Records, integrity, owner actions and deploys are never shadowed (Priority: P1)

Shadowing these would corrupt the evidence the report and every policy rely on.

**Independent Test**: in shadow mode, replay a direct Write to `.wuwei/state.json` and an
owner-only command through PreToolUse.

**Acceptance Scenarios**:

1. Given shadow mode and a direct Write to `.wuwei/state.json` (or today's
   `.wuwei/days/<date>/state.json`), then it is still refused with exit 2 and a deny
   decision.
2. Given shadow mode and an owner-only action (`wuwei decision outcome D-1 A`), then it is
   refused with exit 2.
3. Given shadow mode and an unconfirmed plugin change, then the integrity gate still denies
   PreToolUse calls in the workspace.
4. Given shadow mode and a deploy command the deploy guard refuses, then it is refused with
   exit 2 (Assumption A3).
5. A meta-test pins the never-shadowed set: every name in it is a real guard module in
   `guards.MODULES`, and a stub guard installed under each of those names still refuses in
   shadow mode while a stub under any other name is shadowed.

### User Story 3 - Enforce mode is unchanged (Priority: P1)

**Acceptance Scenarios**:

1. Given no `[guards]` table, or `mode = "enforce"`, then every existing guard, mutation and
   hook-level test passes unchanged and no `guard.would_refuse` event is written.
2. Given an unreadable or invalid config, then the hook behaves exactly as today (the mode
   falls back to enforce; the config error is not a new refusal).
3. A clean tool call reads no config for the mode; the mode is read once per hook process,
   only after a guard refused, so every `WUWEI_BENCH=1` budget holds.

### User Story 4 - The owner sees what would have been refused (Priority: P2)

**Acceptance Scenarios**:

1. Given `guard.would_refuse` events across shadow days, when the owner runs
   `wuwei shadow report`, then the output groups them by guard with a count and the three
   most frequent forms with their counts, guards in descending count order, and exits 0.
2. Given a form refused more than 3 times with no page-tier event recorded after its first
   refusal in the report window, then the report lists it under "Candidates for a guard fix
   or a calibration proposal"; a form followed by a page-tier event is not listed.
3. Given today's events hold `guard.would_refuse` events, then the day report
   (`wuwei report`) carries a `## Shadow` section with the same grouping for today; given
   none, the day report is byte-identical to today's output.
4. Given no `guard.would_refuse` events, then `wuwei shadow report` prints `none` and exits
   0.

### User Story 5 - Shadow is visible and time-boxed (Priority: P2)

**Acceptance Scenarios**:

1. Given shadow mode, then `wuwei status --line` includes a `shadow` part and
   `status --json` has `"shadow": true`; in enforce mode the line has no such part and the
   JSON has `"shadow": false`.
2. Given shadow mode, then the SessionStart additional context carries one line saying
   shadow mode is on, what still refuses, and to run `wuwei shadow report`; in enforce mode
   it does not.
3. Given `guards.shadow_since` seven days before today and the default
   `guards.shadow_days = 7`, then `wuwei nudges` (and the status nudge count) shows exactly
   one nudge with source `guards.shadow` asking the owner to set `guards.mode = "enforce"`
   or raise `guards.shadow_days`; at six days there is none; in enforce mode there is none.

### User Story 6 - Shadow is set by init or the interview (Priority: P2)

**Acceptance Scenarios**:

1. Given `wuwei init --shadow <path>`, then the new `config.toml` has `mode = "shadow"` and
   `shadow_since` set to today; plain `init` still writes the template bytes unchanged;
   `--shadow` with `--upgrade` is refused.
2. Given the interview answer `guards = Shadow first week`, then `interview.settings`
   yields `guards.mode = "shadow"` and `guards.shadow_since = <today>`, which
   `wuwei config promote` proposes like any other answer; `Enforce` yields
   `guards.mode = "enforce"` only.

### Edge Cases

- Several guards refuse one call in shadow mode: each shadowable one is its own event; any
  never-shadowed refusal still blocks, with only the enforced reasons in the deny output.
- A Bash command that does not parse: `target` is the raw command.
- A malformed payload or failed guard discovery stays enforced: no guard ran, so there is
  no guard to shadow. Outside a workspace guards already return 0 (spec 9.1).
- SessionStart never blocks today; its refusal handling is unchanged by the mode.
- The mode is read from `config.toml`, which seats cannot write (protect_state, never
  shadowed), so a seat cannot switch itself into shadow.

## Requirements

### Functional Requirements

- **FR-001**: Config gains `[guards]` with `mode` (`"enforce"` default, or `"shadow"`),
  `shadow_days` (int, default 7, minimum 1) and `shadow_since` (`""` default, or an ISO
  date `YYYY-MM-DD`; any other value is a `ConfigError` naming `guards.shadow_since`).
- **FR-002**: `hook.run` applies shadow at one point, after all guards ran: when the event
  is not SessionStart, the session is not `wuwei-heartbeat`, at least one guard refused and
  the workspace config says shadow, each refusal from a module outside
  `guards.NEVER_SHADOWED` is recorded as `guard.would_refuse` and dropped from the reasons;
  the remaining reasons go through the existing `refuse` path unchanged.
- **FR-003**: `guards.NEVER_SHADOWED = frozenset({'protect_state', 'integrity', 'deploy', 'outward', 'pr'})`.
  `protect_state` covers state, events, generated instructions, config and the owner-action
  table (#222).
- **FR-004**: `guard.would_refuse` is producer-only: listed in `EVENT_PRODUCERS` as written
  by `wuwei hook (shadow mode)` (so `wuwei event guard.would_refuse` is refused), classified
  `silent` in `signal.SILENT`, and pinned in the emitted-kinds tier test.
- **FR-005**: `wuwei shadow report` reads the day directories from `guards.shadow_since`
  (all days when empty) to today and prints the grouping of US4; the day report adds the
  same grouping for today only when today has such events.
- **FR-006**: `status.scan` adds one `guards.shadow` nudge row when shadow mode has run
  `shadow_days` or more calendar days since `shadow_since`; `snapshot` adds
  `shadow: bool` and `line` adds a `shadow` part.
- **FR-007**: `lifecycle.session_start` appends one shadow line to its context in shadow
  mode.
- **FR-008**: `init --shadow` and the interview `guards` question set the mode and the
  start date.
- **FR-009**: Docs: `daily.md` (first week in shadow), `concepts.md` (shadow mode, what
  never shadows), README quick start (shadow as the first-week path),
  `configuration.md` (the three keys), `reference.md` (`bin/wuwei shadow` row, the status
  `shadow` part, the event kind).

### Key Entities

- **guard.would_refuse event** (`.wuwei/days/<date>/events.jsonl`): payload
  `{guard, reason, target, session, item}`; written only by the hook.
- **Form**: the first three whitespace-separated words of `target`; the report's grouping
  key inside a guard.

## Success Criteria

- **SC-001**: The four issue acceptance criteria pass as tests (US1-1, US2-1, US3-1, US5-3).
- **SC-002**: The full suite passes; enforce-mode hook latency is unchanged under
  `WUWEI_BENCH=1`.

## Assumptions

- A1. Shadow is decided per guard module, from `guard.check.__module__`, at the single point
  in `hook.run` (orchestrator notes, binding). No per-guard flag and no guard code changes.
- A2. The whole `protect_state` module is never shadowed, including its top-level `cd`
  containment rule: the module also holds the records and owner-action rules, and
  splitting it would need a per-message rule.
- A3. Conflict raised: the issue lists records, integrity and owner actions as never
  shadowed. Constitution VII says "nothing ever deploys" and spec 4.4 keeps the deployment
  ban under the relaxed profile, so `deploy` is added to the never-shadowed set. A deploy
  ban refusal has no calibration value (it always refuses), so the first week loses no
  evidence. Removing it is a one-word change if the owner disagrees.
- A4. Resolved after review: `outward` and `pr` are in `NEVER_SHADOWED`. `outward` blocks
  canary and honeytoken egress and `pr` blocks forged owner disposition markers; both are
  trust boundaries, not habits to calibrate. The `target` of `guard.would_refuse` is
  redacted (credentials, canary, honeytoken) before it is recorded. Original note: the `pr` guard (merge policy, approve and `--admin`
  refusals, pre-PR gates) is shadowed as the issue says. Constitution VII says a merge
  happens only through the merge policy. During the shadow week the guarantee rests on the
  boundaries spec 4.5 and 9.1 name: the protected base branch with required checks, no
  approve or release token in seat environments, and the `permissions.deny` rules
  `wuwei init` writes for approve and `--admin` merges, which do not depend on hooks. The
  owner should confirm, or add `pr` to `NEVER_SHADOWED` (that would also keep the pre-PR
  gate refusals on).
- A5. The heartbeat probe session is never shadowed: its probes assert that a force push
  and a state write are refused, so shadowing them would page a false "degraded".
- A6. `item` is the first item (sorted) that `state.claims` maps to the payload session;
  null when none or when state cannot be read. The item lookup never turns a shadowed
  refusal into a block.
- A7. `target` is the normalised Bash command (`shell.normalize`, each command's argv
  joined with `shlex.join`, commands joined with `; `), the raw command when it does not
  parse, else `tool_input.file_path`, `notebook_path` or `path`, else the tool name.
  Redaction is the existing known-value redaction in `state._append_jsonl`.
- A8. "No later incident" means no page-tier event (`signal.classify(event, {})[0] ==
  'page'`) recorded after the form's first `guard.would_refuse` in the report window. N is
  a module constant, 3 ("more than 3 times"), not config.
- A9. The nudge counts calendar days from `guards.shadow_since`. With shadow on and
  `shadow_since` empty (a hand edit) there is no nudge; the status line `shadow` part and
  the SessionStart line still show the mode. Extending means raising `shadow_days`.
- A10. SessionStart says so on every SessionStart hook (startup, resume, clear, compact);
  each starts a fresh context, so this is once per session context.
- A11. The day report section and `shadow report` ignore `owner.verbosity`: the grouping is
  already the short form.
