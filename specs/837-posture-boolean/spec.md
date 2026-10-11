# Feature Specification: posture becomes one boolean, guards.enforce; the traces recorder never refuses

**Feature Branch**: `b5-guards` (feature directory `specs/837-posture-boolean/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #837, part 15 of the #789 deletion pass: "refactor(guards): posture becomes one
boolean, guards.enforce; the traces recorder never refuses".

## Context

Today a guard refusal passes through a posture:

- three named postures (`observe`, `guarded`, `strict`);
- six areas (`integrity`, `mcp`, `publish`, `records`, `outward`, `seats`), three levels per
  area (`off`, `warn`, `block`) and per-area overrides (`security.areas`);
- config floors (`FLOORS`), owner-only modules (`OWNER_ONLY`) and a records floor by reason
  prefix (`RECORDS_FLOOR`);
- the retired `guards.mode = "shadow"` and an observe countdown (`guards.shadow_days`,
  `guards.shadow_since`).

About thirty modules read the posture, most of them to ask one question: "is it strict?". Each
strict branch is a second behaviour with its own text, tests and docs, and the planner reads a
posture line under every refusal.

The owner decided (#789): one switch, `guards.enforce` (default true). A refusal either blocks,
or it is logged as `guard.would_refuse` and the call passes. The checks that stop a real process
error (the pass plan's "Process control kept" table) block whenever enforce is on. The traces
recorder never refuses.

Batches 1 to 4 and #831 are merged at the base (703b40de):

- `workspace.RETIRED` and `init` `RETIRED_FILES` exist (#799, #815);
- owner answers come from an Owner step card through `sessions.needs_owner` (#831);
- `tests/test_reasons.py` fails on any new host-terminal text; its LEFT rows name the texts
  later parts delete.

Part 16 (#838) is built next on the same branch and deletes the outward tier table, drafts and
learning cards. This part still stops their posture reads, without deleting them.

## What one switch means

| `guards.enforce` | A guard refusal off the floor | A floor refusal |
| --- | --- | --- |
| `true` (default) | blocks, with its reason and no posture line | blocks |
| `false` | recorded as `guard.would_refuse` (guard, reason, exit, target, session, item); the call passes; a launch refusal is also shown to the session (#660) | blocks |

The floor (constitution VII) is what the observe posture already kept blocking, so mapping
observe to `enforce = false` loosens nothing:

- records written by the workflow: the state-file guard (`protect_state.check_file`,
  `protect_state.check_bash`), the Owner step answer recorder (`answers`), `lifecycle`, the
  verdict lint, and every reason that starts with a `RECORDS_FLOOR` prefix (canary egress,
  owner disposition markers, a seat launch naming a brief that does not exist);
- the owner's edges: deploy (the `deploy` module), merge, admin, approval and branch protection
  (reasons that start with a `MERGE` prefix), and an outward send the tiers hold
  (`outward.check_tier`; part 16 replaces it with the allowlist check).

Some cases keep warning in both settings, as they do under the default posture today, until
part 17 deletes them: the unparsed command (`UNPARSED`), the workspace root `cd`
(`WORKSPACE_ROOT`) and the deploy guard's unknown git subcommand (`UNKNOWN_GIT`), each once per
call, and an opaque Bash call naming no publish target. Strict refused them; strict goes.

Code outside the hook that branched on `strict` takes the default (guarded) path, except two
rows the "Process control kept" table names:

- a seat launch that does not match a logged brief, including a WUWEI seat type launched with no
  brief line, is refused whenever enforce is on;
- a bare `gh pr create` for a recorded item is refused whenever enforce is on, naming
  `bin/wuwei pr raise ... --item`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every guard reads one switch (Priority: P1)

**Why this priority**: the issue's first acceptance line. The posture is machinery the planner
reasons about (which area, which level, which override). One switch is the owner's choice.

**Independent Test**: grep, and a table test of the hook over a refusal from each guard module,
with `guards.enforce` true and false.

**Acceptance Scenarios**:

1. **Given** `guards.enforce = true`, **When** any guard refuses, **Then** the hook blocks with
   the guard's reason and adds no `posture:` line.
2. **Given** `guards.enforce = false`, **When** a guard off the floor refuses (commit and push,
   the PR create shape, a seat launch, integrity, spec, stop, scratch), **Then** one
   `guard.would_refuse` event is appended with `guard`, `reason`, `exit`, `target`, `session`
   and `item` (no `area`, `level` or `posture`), and the call passes.
3. **Given** `guards.enforce = false`, **When** a floor guard refuses (a write to `state.json`,
   a merge, an admin merge, an approval, a deploy, a canary egress, a held outward send),
   **Then** the hook blocks as with enforce on.
4. **Given** the code at the end of this part, **When** it is grepped, **Then** no module under
   `cli/` reads `security.posture`, `security.areas`, `guards.mode`, `guards.shadow_days`,
   `guards.shadow_since`, `workspace.posture`, `workspace.AREAS`, `AREA_LEVELS`, `POSTURES`,
   `FLOORS`, `guards.AREAS`, `guards.level` or `OWNER_ONLY`. The one exception is
   `init --upgrade`, which reads the old keys from the file it migrates.
5. **Given** a config that cannot be read, **When** a guard refuses, **Then** the refusal
   blocks, as today.

---

### User Story 2 - init --upgrade maps observe to enforce = false and removes the old keys (Priority: P1)

**Why this priority**: the issue's second acceptance line. An observe workspace must stay in
observe after the upgrade.

**Independent Test**: `init --upgrade` on configs carrying each old shape.

**Acceptance Scenarios**:

1. **Given** `security.posture = "observe"`, **When** `init --upgrade` runs, **Then** it writes
   `guards.enforce = false`, removes `security.posture` and prints
   `Upgraded config.toml: guards.enforce = false (was security.posture = "observe")`.
2. **Given** `guards.mode = "shadow"`, **When** `init --upgrade` runs, **Then** the same, with
   `(was guards.mode = "shadow")`.
3. **Given** `security.posture = "guarded"` or `"strict"`, or `guards.mode = "enforce"`,
   **When** `init --upgrade` runs, **Then** the key is removed with
   `remove <key> (no longer read)` and `guards.enforce` keeps its default, true.
4. **Given** `[security.areas]`, `guards.shadow_days` or `guards.shadow_since`, **When**
   `init --upgrade` runs, **Then** each is removed and reported, as every retired key is (#799).
5. **Given** `--dry-run`, **When** the upgrade runs, **Then** each line reads `Would upgrade`
   and nothing is written.
6. **Given** a config that already sets `guards.enforce`, **When** the upgrade runs, **Then**
   the owner's value stays, whatever the old posture said.

---

### User Story 3 - The traces recorder never refuses (Priority: P1)

**Why this priority**: named in the issue title. Recording is not a gate.

**Independent Test**: `tests/test_traces.py` with a slow, unreadable and failing recorder.

**Acceptance Scenarios**:

1. **Given** the traces recorder times out, cannot read the security material, or cannot write
   the span, **When** the PostToolUse hook runs, **Then** it exits 0, prints the reason on
   stderr and appends `traces.slow` or `traces.gap` (as below strict today), whatever
   `guards.enforce` says.

---

### User Story 4 - The process checks keep blocking with enforce on (Priority: P1)

**Why this priority**: owner constraint (b): a check that stops a real process error is kept.

**Independent Test**: one case per row, with `guards.enforce = true` (the default).

**Acceptance Scenarios**:

1. **Given** a WUWEI seat type launched with no `WUWEI brief:` line, **When** the hook runs,
   **Then** it is refused naming `bin/wuwei brief <role> <item> <name>`. Today it registers an
   adhoc seat below strict.
2. **Given** a launch whose brief does not match (role, name, modified, head changed, gate tree
   dirty), **When** the hook runs, **Then** it is refused. Today it warns under guarded.
3. **Given** `gh pr create` for a recorded item that links no PR, **When** the hook runs,
   **Then** it is refused naming `bin/wuwei pr raise ... --item <item>`. Today it warns below
   strict.
4. **Given** `bin/wuwei pr raise --item` with a gate that has not passed at the head, **When**
   it runs, **Then** it refuses. With `guards.enforce = false` it records `guard.would_refuse`
   and raises, as observe does today.
5. **Given** a merge, an admin merge, an approval, a force push, a deploy, a state-file write
   and a verdict that fails the lint, **When** each runs, **Then** each is refused, as today.
6. **Given** an untyped launch (`general-purpose`, `Explore`), **When** the hook runs, **Then**
   it registers an adhoc seat and is never refused. That is the default today; strict's
   refusal goes.

---

### User Story 5 - The owner sees one line, not a table (Priority: P2)

**Independent Test**: `config check`, `doctor`, `status`, the SessionStart orientation, `why`.

**Acceptance Scenarios**:

1. **Given** `config check`, **Then** it prints `Guards: enforce (guards.enforce = true)` or
   `Guards: log only (guards.enforce = false); records, merges, deploys and held sends still
   refuse`, and the `scanner.mcp.block` line without a posture.
2. **Given** `doctor`, **Then** one `guards` row replaces the `posture` row and its countdown.
   It is ok in both settings; the false text names `bin/wuwei config set guards.enforce true`.
3. **Given** `status --json`, **Then** it carries `enforce` (true, false, or null without a
   config) in place of `posture`; `status --line` shows `observe` when enforce is false.
4. **Given** SessionStart, **Then** the orientation prints one of two sentences, chosen by
   `guards.enforce`. The no-workspace row names `bin/wuwei init --shadow`.
5. **Given** `wuwei why last refusal` on a `guard.would_refuse`, **Then** it shows the guard,
   rule and fix, with no `posture:` line.

### Edge Cases

- A `guard.would_refuse` written before the upgrade still carries `area`, `level` and
  `posture`. `why`, the report's `## Shadow` section and telemetry read it unchanged; none of
  them requires those fields.
- `init --shadow` on a new workspace writes `enforce = false`. `--posture` is gone, so argparse
  refuses it. `--shadow` with `--upgrade` is refused as today, naming `guards.enforce`.
- `spec.mode = "strict"` runs as advisory when `guards.enforce = false`, as it does under
  observe today.
- The MCP launch gate (`mcp.cached`): with enforce on, the findings in `scanner.mcp.block` and a
  check that could not run block (the guarded behaviour). With enforce off they pass with a
  note. `security.areas.mcp = "off"` goes; `adapters.scanner = "none"` turns the gate off, as
  today.
- An untyped launch refused under strict before the upgrade now registers as adhoc.
- Telemetry stays as it is (owner, 2026-10-11). The weekly record keeps its `config.posture`
  field, now `"guarded"` when `guards.enforce` is true and `"observe"` when false, so stored
  weeks and the collector keep validating. `telemetry.AREAS` and `telemetry.POSTURES` stay as
  the vocabularies of stored weeks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `workspace.SCHEMA` has `guards = {"enforce": (bool, True)}` and
  `security = {"required": (bool, False)}`. `POSTURES`, `AREAS`, `AREA_LEVELS`, `FLOORS`,
  `posture()`, `posture_source()`, and the `shadow_since` and floor validation go.
- **FR-002**: `workspace.RETIRED` gains `security.posture`, `security.areas`, `guards.mode`,
  `guards.shadow_days` and `guards.shadow_since`.
- **FR-003**: `guards/__init__.py` replaces `AREAS`, `OWNER_ONLY` and `level()` with `FLOOR`
  (module or `module.function` keys) and `floor(check, reason)`, true for a `FLOOR` key or a
  reason that starts with a `MERGE` or `RECORDS_FLOOR` prefix.
- **FR-004**: `commands/hook.py` `posture()` becomes `enforce()`. It blocks when the switch is
  on or the refusal is on the floor, else it records `guard.would_refuse` without area, level
  and posture. The warn-once cases and the opaque Bash warning keep their below-strict form.
- **FR-005**: Every strict-only branch in the modules listed in plan.md takes the default path,
  except the two table rows (brief line, `gh pr create` for a recorded item), which refuse.
- **FR-006**: `guards/traces.py` returns `(0, '')` on every path; `_strict` goes.
- **FR-007**: `init --upgrade` maps `security.posture = "observe"` and `guards.mode = "shadow"`
  to `guards.enforce = false` before the retired keys are removed, prints the line, honours
  `--dry-run` and never overrides an explicit `guards.enforce`.
- **FR-008**: `init --posture` goes; `init --shadow` writes `enforce = false`.
- **FR-009**: The constitution (VII) and the design spec (4.1, 4.3, 4.5, 5.9, 5.10, 5.11, 5.13,
  7, 9.1, 9.2) describe the switch and the floor instead of postures.
- **FR-010**: No new host-terminal text (tests/test_reasons.py). The three `tracker.py` LEFT
  rows whose strict-only texts go are deleted.

### Key Entities

- **guards.enforce**: one boolean in `[guards]` of config.toml; default true.
- **FLOOR**: the guard checks and reason prefixes that block whatever the switch says.

## Success Criteria *(mandatory)*

- **SC-001**: grep finds no posture reader under `cli/` except the migration in
  `init --upgrade`.
- **SC-002**: a hook table test over one refusal per guard module passes for enforce true and
  false.
- **SC-003**: an upgraded observe workspace keeps every refusal it had (the floor) and logs the
  rest.
- **SC-004**: the touched test files pass; CI is the gate.

## Assumptions

1. **The floor stays, as one constant.** The issue says the posture floors go. The config floors
   (`FLOORS`, the `security.areas` validation) go with the areas. The constitution VII floor
   (records, the owner's merge and deploy edges) is not a posture setting: observe kept it, and
   mapping observe to `enforce = false` must loosen nothing. It stays as `guards.FLOOR`, read by
   the hook only.
2. **Enforce on is the guarded default plus the table; no new walls (B5 lead call, 2026-10-11,
   overrides the earlier draft).** With enforce on, only the irreversible edges (merge,
   approve, admin, force push, deploy, outward send, records) and the process-control checks
   (a seat launch that matches a logged brief at an unchanged head; a bare `gh pr create` for a
   recorded item) are added to what blocked under the old guarded default. Every check that
   only warned under guarded stays a logged `guard.would_refuse`: CAP, the host seat ceiling,
   free memory and a missing ticket at launch, the outward prose lint (and a lint that could
   not read its policy), unknown MCP tool names and another item's scratch directory. The hook
   reads them from `guards.LOG_ONLY` (the `outward` module except the floor's `check_tier`,
   `protect_state.check_scratch`) and `guards.CAPACITY` (launch reason text). With enforce off,
   the floor still blocks as above. `guards.FLOOR` names the whole `pr` and `protect_state`
   modules (less `check_scratch`), as observe blocked them, so a push to the default branch or a
   gh alias change refused by the PR guard still refuses with enforce off.
3. **Strict-only extras go; they do not move under enforce.** Each takes its guarded branch:
   - a tag push refused from the session (the deploy guard's Owner step card stays);
   - a pre-push missing fast check refused (the warning stays);
   - a worktree without git hooks refused (the warning stays);
   - a counterpart reference fetch error refused (it stays optional evidence);
   - a scanner page for an unknown session (the `traces.unmatched` event stays);
   - D-n cards never confirming, ticket creation held back at approve and plan add;
   - strict tier rows, learning-card handling and the internal-state word refusal (part 16
     deletes the rest);
   - seat stop by Owner step card (the planner session check stays).
4. **`--shadow` stays as the one init flag**, because the no-workspace row of `next` names it.
5. **Opaque and unparsed commands warn in both settings** until part 17 deletes that machinery.
   An exception escaping the traces recorder only logs (`traces` is in `guards.LOG_ONLY`). The
   spec guard's could-not-run refusal now only logs with enforce off; dispatch keeps
   spec-before-gates, and part 21 deletes the spec hook.
6. **Status JSON renames `posture` to `enforce`.** Nothing outside the CLI reads it now that the
   cockpit is gone (#808).
7. **Docs.** Per the pass plan, `docs/site` is edited only where a test forces it: the
   `configuration.md` rows for the removed and added keys, and the `init` row in
   `reference.md`. The rest of the site and the README are rewritten in part 24; plan.md lists
   them.

## Deferred

- Part 17: CAP and host seat refusals become log-only; the opaque and unparsed handling goes.
- Part 24: the posture sections of `docs/site/security.md`, `concepts.md`, `daily.md`,
  `recovery.md`, `adapters.md`, `index.md`, `reference.md` and the README.
