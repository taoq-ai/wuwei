# Feature Specification: posture profiles: what warns and what blocks is configurable by where the plugin runs and for what purpose

**Feature Branch**: `331-security-posture`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #331, "feat(security): posture profiles: what warns and what blocks is
configurable by where the plugin runs and for what purpose". Evidence: the owner after the
v0.11.0 trial (2026-10-03): one hard default for everything makes the plugin unusable on a
real project, and a soft one makes it pointless on a sensitive one. Depends on #336 (the MCP
gate's `scanner.mcp.block`) and #338 (read-only shell forms, shadow records them), both on
main (e5e2070).

## Root cause (read and reproduced on main, e5e2070)

Reproduction (read-only, a throwaway workspace under the session scratchpad; the item names
no dry-run workspace): `workspace.load_config(root, raw='[security]\nposture = "observe"\n')`
raises `config.toml: unknown key security.posture at line 2`, and the same for
`[security.areas]`. An empty config loads `security == {'required': False}`,
`guards.mode == 'enforce'`, `profile == 'strict'`.

What warns and what blocks is decided today by three unrelated switches, none of them by
area, none of them with an "off":

1. `cli/wuwei/workspace.py:46`: the `security` table accepts only `required`; there is no
   posture key.
2. `cli/wuwei/commands/hook.py:146-167` (`shadow`) with `cli/wuwei/guards/__init__.py:37`
   (`NEVER_SHADOWED`): the only relaxation of hook refusals is all-or-nothing
   `guards.mode = "shadow"`, per guard module, with a fixed never-shadowed set. Outside shadow
   every guard blocks (`hook.py:92-96`).
3. `cli/wuwei/mcp.py:274-280` (`_gate`, used by `cached` at 283-295): the MCP launch gate has
   its own list, `scanner.mcp.block`. The `profile` key (`workspace.py:113`,
   `guards/__init__.py:51-59`) relaxes only the outward lint.

So the owner cannot say "warn on seats and outward text, block publishing" or "do not check
MCP here", and there is no table of floors that no setting lowers.

## User Scenarios & Testing

### User Story 1 - Observe a project without blocking it, records still protected (Priority: P1)

The owner runs a first week on a project, or a personal sandbox, with
`security.posture = "observe"`: the guards record what they would refuse and let the call
through, while WUWEI's own records stay protected and every refusal says why.

**Independent Test**: `tests/test_e2e_day.py` with the `day` fixture and
`security.posture = "observe"`.

**Acceptance Scenarios**:

1. Given `security.posture = "observe"`, when a seat runs `git push --force origin main` in a
   configured repo, then the hook exits 0 and today's last event is `guard.would_refuse` with
   `guard: commit_push`, `area: publish`, `level: warn`, `posture: observe`.
2. Given `observe`, when a `Write` targets `.wuwei/days/<date>/state.json`, then it is
   refused (exit 2, deny) and the deny reason names the area and level:
   `posture: records = block (floor; no setting lowers it)`.
3. Given `observe`, an owner-only action (`wuwei decision outcome D-1 A`) is still refused.
4. Given `observe`, refusals from the `deploy` and `pr` guards and from the outward approval
   tier are still enforced (owner-only floor).
5. Given `observe`, an unconfirmed plugin change is recorded as `guard.would_refuse` with
   `area: integrity` and the call is allowed.

### User Story 2 - Per-area overrides, MCP off (Priority: P1)

**Independent Test**: `tests/test_posture.py` and `tests/test_mcp.py`.

**Acceptance Scenarios**:

1. Given `[security.areas] mcp = "off"`, when the owner runs `wuwei mcp check`, then it exits
   0, prints `MCP registry: not checked (security.areas.mcp = "off")`, runs no scanner and
   writes no `mcp.checked` or `mcp.finding` event.
2. Given `mcp = "off"` and a discovered MCP server with no registry record, when the morning
   plan is proposed, then the plan gate proceeds, the sweep line says not checked, and
   `status` shows no nudge from the MCP check.
3. Given `[security.areas] seats = "block"` under `guarded`, an Agent launch with no logged
   brief is refused and the reason carries `posture: seats = block (set security.areas.seats)`.
4. Given an area set to `off`, a refusal from that area's guard is neither enforced nor
   recorded.

### User Story 3 - Floors no setting lowers (Priority: P1)

**Acceptance Scenarios**:

1. Given `[security.areas] records = "warn"` (or `"off"`), when the owner runs
   `wuwei config check`, then it exits 1 and the message names `security.areas.records` and
   its floor; every hook then fails closed as for any config finding (#326 repair reads
   still pass).
2. Given any posture and any override, refusals from `deploy`, `pr` and the outward approval
   tier (`outward.check_tier`) always block (owner-only actions).
3. Given `guarded` or `strict` and `mcp = "warn"`, an MCP finding at a severity in
   `scanner.mcp.block`, or a registry check that could not run, still blocks launches (the
   trust-boundary floor); under `observe` with `mcp = "warn"` it does not.

### User Story 4 - Strict is today's behaviour, guarded is the default (Priority: P1)

**Acceptance Scenarios**:

1. Given `security.posture = "strict"`, then every hook guard blocks exactly as on main and
   the MCP gate blocks every high or critical finding and every unmeasured server (the
   pre-#325 list); the existing guard, mutation and hook-level tests pass under `strict`.
2. Given no `security.posture` key, then the posture is `guarded`: records, publish and
   integrity block; mcp, outward and seats warn. The existing guard, mutation and hook-level
   tests pass under the default except those that depend on seats, outward or MCP blocking,
   which pin `strict`.
3. A guard refusal from a module the area table does not name (a test stub, a module added
   later) blocks, with no posture line.

### User Story 5 - Visible and set by the owner (Priority: P2)

**Acceptance Scenarios**:

1. `wuwei config check` prints a `Posture: <name>` section with one line per area and its
   effective level, marking overrides and the records floor, and a line that owner-only
   actions block in every posture.
2. `status --line` shows the posture name as a part when it is not `guarded`;
   `status --json` carries `posture`.
3. `wuwei init --posture observe|guarded|strict <path>` writes `security.posture`;
   `observe` also sets `guards.shadow_since` to today. `--shadow` stays as
   `--posture observe`. Neither combines with `--upgrade`.
4. The owner interview asks the posture (`posture` question: Observe, Guarded, Strict);
   `Observe` also proposes `guards.shadow_since` today.
5. Given `observe` and `guards.shadow_since` `guards.shadow_days` or more days ago, one
   `guards.shadow` nudge asks to set `security.posture = "guarded"` or raise
   `guards.shadow_days`. SessionStart says observe is on.
6. A warning recorded under `guarded` or `strict` (an area set to `warn`) is a nudge, one
   row per guard per day, naming the guard, the reason and `security.areas.<area>`; under
   `observe` warnings are silent (the day report and `shadow report` list them).

### User Story 6 - Shadow mode is observe (Priority: P2)

**Acceptance Scenarios**:

1. Given the deprecated `[guards] mode = "shadow"`, then the effective posture is `observe`
   whatever `security.posture` says, and `config check` prints one deprecation line naming
   `security.posture = "observe"`; it is not a finding.
2. `guards.shadow_days` and `guards.shadow_since` keep the time box for `observe`.

### Edge Cases

- Several guards refuse one call: each warn-level one is its own `guard.would_refuse`; any
  block-level one still denies, with only the enforced reasons and their posture lines.
- No readable config (outside a workspace, or a config that does not load on a non-config
  event): every refusal is enforced with no posture line, as before.
- The heartbeat session (`wuwei-heartbeat`) and SessionStart are not subject to the posture
  (unchanged from #308).
- A warning that cannot be recorded is enforced, with `could not record shadow refusal` on
  stderr (unchanged from #308).
- `config.toml` is protected by `protect_state` (records, always block), so a seat cannot
  lower its own posture.

## Requirements

### Functional Requirements

- **FR-001**: Config: `security.posture` (`"observe"`, `"guarded"` default, `"strict"`) and
  `security.areas.<area>` for `integrity`, `mcp`, `publish`, `records`, `outward`, `seats`,
  each `""` (from the posture, default), `"off"`, `"warn"` or `"block"`.
- **FR-002**: One posture table in `workspace.py` (`POSTURES`) and one resolver
  `workspace.posture(config) -> (name, levels)`: `observe` = every area warn except records
  block; `guarded` = records, publish, integrity block, mcp, outward, seats warn; `strict` =
  every area block. Overrides replace the posture's level; `guards.mode = "shadow"` makes
  the name `observe`.
- **FR-003**: Floors: `workspace.FLOORS = {'records': 'block'}`; `load_config` raises a
  `ConfigError` naming `security.areas.<area>` and the floor for a lower override.
  `guards.OWNER_ONLY` (`deploy`, `pr`, `outward.check_tier`) block in every posture. The MCP
  gate keeps `scanner.mcp.block` findings and an unrunnable check blocking under `guarded`
  and `strict`.
- **FR-004**: `guards.AREAS` maps every guard module in `MODULES` (and
  `agent_launch.check_mcp` to `None`: the MCP gate applies its own posture) to an area; a
  test pins it. It replaces `NEVER_SHADOWED`.
- **FR-005**: `hook.posture` replaces `hook.shadow` at the same single point: per refusal,
  `off` drops it, `warn` records `guard.would_refuse` `{guard, area, level, posture, reason,
  target, session, item}` and allows, `block` enforces it with a posture line naming area,
  level and the key (or the floor). The config is read only when a guard refused.
- **FR-006**: `agent_launch` gains a `check_mcp` guard record holding the MCP launch gate
  (moved out of `_check`), so the seats level never relaxes an MCP floor.
- **FR-007**: `mcp.check` and `mcp.cached` apply the `mcp` level: `off` is not checked
  (exit 0, no scan, no event); `block` blocks the pre-#325 list (`scanner.mcp.block` plus
  high, critical, unmeasured); `warn` blocks `scanner.mcp.block` (and an unrunnable check)
  under `guarded` and `strict` and nothing under `observe`. Non-zero reasons and the observe
  pass name the mcp level and key.
- **FR-008**: Surfaces: `config check` posture table and deprecation line; `status` posture
  part and JSON field and the observe time-box nudge; `guard.would_refuse` nudge tier outside
  observe; SessionStart observe line; `why` prints the posture of a warning; `init
  --posture`; interview `posture` question; `security` is private in calibration profiles.
- **FR-009**: Docs: `docs/site/security.md` (table, floors, where to run observe and strict),
  design spec 9.1 amendment with the table, `docs/site/configuration.md` keys,
  `reference.md`, `concepts.md`, `daily.md`, README quick start; template `[security]`.

### Key Entities

- **Posture**: a name and a level per area, resolved once per hook process that refused.
- **Area**: `integrity`, `mcp`, `publish`, `records`, `outward`, `seats`.
- **Level**: `off` (never checked), `warn` (recorded, never refuses), `block`.
- **guard.would_refuse event**: gains `area`, `level`, `posture`.

## Success Criteria

- **SC-001**: The four issue acceptance criteria pass as tests (US1-1/2, US2-1/2, US3-1,
  US4-1/2).
- **SC-002**: The full suite passes; no hook exceeds its `WUWEI_BENCH=1` budget (a clean call
  reads no extra config).

## Assumptions

- A1. "setup --posture" is `wuwei init --posture` (WUWEI has no setup command).
- A2. Guard modules map to areas: `protect_state`, `decision`, `verdict`, `traces`,
  `lifecycle` to records (the evidence and the session records); `commit_push`, `pr`,
  `deploy`, `stop` (owned-PR anchor, day close) to publish; `outward` to outward;
  `agent_launch` to seats; `integrity` to integrity. Under `observe` the decision and verdict
  lints and the planner wake (lifecycle Stop) now block where #308 shadowed them: they are
  records, and a shadowed wake is a lost wake.
- A3. Conflict raised: the issue makes `publish` (push, PR, merge, deploy) warn under
  `observe`. Constitution VII says nothing ever deploys and a merge happens only through the
  merge policy; spec 4.6, 4.7 and 9.1 make deploys, merges the policy does not clear,
  approvals and approve-tier messages owner decisions. They are read as the issue's floor
  "owner-only actions always need the owner": `deploy`, `pr` and `outward.check_tier` block
  in every posture (as in #308). Under `observe`, `publish` relaxes the commit and push rules
  and the PR anchor; under `guarded` with `outward = "warn"` only the outward text lint
  warns. Removing a name from `OWNER_ONLY` is a one-word change if the owner disagrees.
- A4. The "trust-boundary security finding" floor: gate findings already block through
  `scanner.py` and the charters, which the posture never touches. For the MCP gate it is a
  finding at a severity in `scanner.mcp.block` (default critical) or a check that could not
  run: these block under `guarded` and `strict` whatever `mcp` is, except `off` (nothing is
  measured). So `guarded` reproduces #336's default exactly. The plugin integrity gate is
  tamper evidence, not a 9.1 boundary (spec 7.1), so its override is not floored.
- A5. `strict` is "today" as of v0.11.0, before #336: the MCP gate blocks every high or
  critical finding and every unmeasured server. Hook guards under `strict` behave as on main.
- A6. `off` is applied after the guard ran (the result is dropped, nothing recorded), so a
  clean call still reads no config for the posture and the bench budgets hold. SessionStart
  context and the watch sweeps are unchanged by the posture.
- A7. `warn` is "recorded as a nudge and `guard.would_refuse`": the event always; a nudge
  when the posture is `guarded` or `strict` (an explicit relaxation the owner should see),
  one row per guard per day. Under `observe` the time-box nudge and the day report's
  `## Shadow` section carry it, as in #308. For the MCP gate the record is the existing
  `mcp.checked` and `mcp.finding` events.
- A8. The default changes to `guarded` for every workspace, including upgraded ones: seats,
  outward text and MCP warn by default. `init --upgrade` adds `posture = "guarded"` from the
  template; a workspace on `guards.mode = "shadow"` stays observe because shadow wins.
- A9. `profile` (`strict`/`standard`) and the CLI send path (`outward.check_call`) are
  unchanged; deprecating `profile` is out of scope.
- A10. Unknown guard modules (tests, later modules) block with no posture line, so stub
  tests keep byte-identical output; tests that need a stub to warn add it to `guards.AREAS`.
- A11. The interview question id changes from `guards` to `posture`; a recorded `guards`
  answer is ignored (the config value it promoted stays).
- A12. `security` joins the calibration profiles' private keys: a posture describes where
  this workspace runs and is never exported or imported.
- A13. The posture table lives in `workspace.py` (the config module the notes call
  config.py); the guard-to-area table lives next to `MODULES` in `guards/__init__.py`.
