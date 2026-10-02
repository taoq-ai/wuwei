# Feature Specification: shareable calibration profiles: export a promoted calibration and interview, import as a proposal

**Feature Branch**: `313-calibration-profiles`
**Created**: 2026-10-02
**Status**: Ready for implementation
**Input**: Issue #313, feat(calibrate). Design section 6 and 6.8 (charter overrides, propose
and promote); #278 calibrate, #279 interview, #280 tiered gates, #282 cruise ceilings
(design 5.8.1); #48 redactor port. Owner agreement 2026-10-02.

## Root cause (read on main, d6385b2)

A promoted calibration exists only inside the workspace that made it. Nothing reads it out,
and nothing feeds an outside one back in through the owner gates.

- Reproduced read-only in a scratch directory: `bin/wuwei calibrate export python-library`
  and `bin/wuwei calibrate import x.json` both exit 2 with `unrecognized arguments`.
  `cli/wuwei/commands/calibrate.py:11-21` registers only `--repo`, `--interview`,
  `--questions` and `--answer`.
- `wuwei config promote` builds its settings from the checkout survey and today's
  interview answers only (`cli/wuwei/commands/config.py:126-128`:
  `calibrate.propose(raw, results, interview.settings(answers, config))`). There is no
  input for a third source of settings.
- The pieces a profile needs already exist and are reused, not rewritten:
  `calibrate.propose`, `settle`, `apply` and `_table` place settings in `config.toml` and
  validate the result against `workspace.SCHEMA` (`cli/wuwei/calibrate.py:384-390`,
  `:560-592`); `calibrate.instruction_like` flags agent-directed text
  (`cli/wuwei/calibrate.py:67-70`); the redactor port (`adapters/redactor/builtin.py:18-35`,
  registry contract `cli/wuwei/registry.py:18`) finds secrets, emails and phone numbers;
  `promotion.promote` lands charter proposals with ledger reasons
  (`cli/wuwei/promotion.py:218-267`); `decision.level` gives the cruise level a class runs
  at (`cli/wuwei/decision.py:20-24`); the gate floors are ordered
  `("light", "standard", "full")` in `workspace.SCHEMA` (`cli/wuwei/workspace.py:52`).
- `templates/profiles/` does not exist. Everything under `templates/` already ships in the
  release asset (`scripts/build-release.py:15`) and in the signed inventory
  (`cli/wuwei/integrity.py:31-47` walks every file), so starter profiles need no manifest
  edit.
- The day files only the CLI writes are listed in the protect_state guard
  (`cli/wuwei/guards/protect_state.py:194`); a new day file `profile.json` must join that
  list, as `interview.json` did.

## User Scenarios & Testing

### User Story 1 - Export a promoted calibration without anything personal (Priority: P1)

The owner of a calibrated workspace runs `bin/wuwei calibrate export <name>`. It writes
`<name>.json` in the current directory: the configuration that differs from the shipped
template, the lines the workspace charter overrides add to the shipped charters with the
ledger reasons that landed them, and a manifest of everything it dropped. Owner name, ids,
tokens, channel ids, repository names and absolute paths never reach the file.

**Why this priority**: without export there is nothing to share; the redaction is the
security core of the feature.

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k export`.

**Acceptance Scenarios**:

1. Given a workspace whose config sets `owner.name`, `owner.handles`,
   `control_plane.owner`, `shepherd.review_channel`, a repository `acme/widget` at an
   absolute path, `repos.fast_checks`, `repos.gates.floor = "full"` and
   `repos.gates.trust_paths`, and whose `.wuwei/charters/builder.md` override adds lines
   naming `acme/widget`, the owner name, a `ghp_` token and an absolute path next to plain
   rule lines, then `calibrate export team` exits 0 and the file text contains none of the
   owner name, the handle, the channel id, the control-plane ids, the token, the
   repository name, the workspace path or the home directory; it keeps the fast checks,
   the floor, the trust paths and the plain rule lines; and its `dropped` list names each
   dropped key or charter line with why (`personal`, `absolute path`, a redactor finding
   kind, `outside what a profile may carry`) without quoting the value.
2. Given `merge.auto = true` or `gates.floor = "light"` for the exported repository, or
   `shepherd.autostart = true`, then the key is not in the profile and `dropped` names it
   as outside what a profile may carry.
3. Given `--repo acme/gadget`, then the repository part comes from that repository;
   without it, from the first configured repository. An unknown name, an existing
   `<name>.json`, a name that is not a lowercase slug, a symlinked charter override, an
   unreadable ledger or a redactor that cannot run exits 2 and writes nothing.

### User Story 2 - Import a profile as a proposal (Priority: P1)

The owner of another workspace runs `bin/wuwei calibrate import <file, https URL or
starter name>`. It lists each change the profile proposes (the `config.toml` diff and one
charter proposal per role), writes them as proposals and changes nothing else. Nothing
applies until the owner runs `bin/wuwei config promote` in a host terminal and
`bin/wuwei promote`.

**Why this priority**: import is the other half of sharing and carries the trust boundary.

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k "import or profile_promote"`.

**Acceptance Scenarios**:

1. Given a profile with `repos.fast_checks`, `repos.gates.floor = "full"`, `deploy.deny`
   and a builder charter block, then `calibrate import` exits 0, prints the config diff
   and the charter proposal path, writes `.wuwei/days/<date>/profile.json` and
   `proposals/profile-builder.json`, and leaves `config.toml` and every charter unchanged.
2. Then `config promote` lists each profile change in the digested summary and, on
   confirmation, writes them for every configured repository; `wuwei promote` lands the
   builder block with the profile reason in the ledger.
3. Given `--skip repos.gates.floor` or `--skip charters.builder`, then that change is not
   recorded and promote never applies it. A `--skip` naming nothing in the profile exits 2.
4. Given a profile that sets `repos.merge.auto = true`, raises a cruise level
   (`decisions.cruise.levels.approach = 2` where the workspace runs it at L1, or
   `decisions.cruise.enabled = true` where it is false), lowers `repos.gates.floor`
   below the workspace's value, sets `shepherd.autostart = true`, sets any `adapters.*`
   key or a credential key (`calendar.url`, `watch.ping_url`, `codex.command`), or carries
   a private key (for example `owner.name`), then import exits 1, prints `refused: <key>`
   for each, and writes nothing.
5. Given a forged `profile.json` in today's directory that carries a refused key or
   instruction-like text, then `config promote` exits 2 and writes nothing.

### User Story 3 - Instruction-like profile text is flagged, never proposed (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k instruction_like_profile`.

**Acceptance Scenarios**:

1. Given a profile whose builder charter has a line that reads as an instruction to an
   agent (an override of previous instructions, or a push to main), then import exits 1,
   prints the flag with role, line number and rule (never the text), writes no
   `profile-builder.json`, and the other roles and the config changes are still proposed.
2. Given a config string value or a ledger reason that reads as an instruction, then that
   key (or that role's block) is flagged the same way and not proposed.

### User Story 4 - Starter profiles ship with WUWEI (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_calibrate.py -k starter tests/test_docs.py`.

**Acceptance Scenarios**:

1. `templates/profiles/python-library.json` and `templates/profiles/cli-tool.json` exist;
   each imports into a fresh workspace with one repository with exit 0 (no refusal, no
   flag) and its config diff applies through `calibrate.propose`.
2. `bin/wuwei calibrate import python-library` finds the starter by name.
3. `docs/site/configuration.md` has a `## Calibration profiles` section after
   `## Owner interview` naming `calibrate export`, `calibrate import`, `--skip`,
   `profile.json`, `templates/profiles/`, both starters and every refused key;
   `docs/site/reference.md` mentions export and import in the `bin/wuwei calibrate` row.

### Edge Cases

- No configured repository and a profile with a `repos` part: import exits 2 with the
  calibrate `NO_REPOS` reason. A profile without a `repos` part imports without one.
- `--repo NAME` on import applies the `repos` part to that repository only; default all.
- A charter line already present in the target charter (workspace override, else the
  shipped charter) is left out of the proposal, so `promote` does not reject the block as a
  duplicate add; a role left with no lines gets no proposal.
- The same key from a profile and from today's interview answers: the interview answer
  wins and the profile setting is dropped before `propose`, so two settings never target
  one key.
- Re-import on the same day replaces `profile.json` and rewrites `profile-<role>.json`
  files, removing a stale one whose role is no longer proposed.
- A profile key the schema does not know, or a value of the wrong type: the import
  preview (`calibrate.propose`) fails and import exits 2 with the schema reason.
- URL import: `https` only, 30 second timeout, at most 1 MiB, a redirect to a non-https
  URL fails; any failure exits 2.
- A file over 1 MiB, not JSON, or not the profile shape (`wuwei_profile` 1, slug `name`,
  `config` object, `charters` of shipped role names each with `text` and `reasons`)
  exits 2.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei calibrate export NAME [--repo NAME]` writes `NAME.json` (refusing to
  replace an existing file) with `wuwei_profile` 1, `name`, `config`, `charters` and
  `dropped`. `config` holds every leaf of the validated workspace config that differs from
  the validated shipped template, with `repos` as one table: the selected repository
  compared with a default repository.
- **FR-002**: Export drops, and lists in `dropped` as `{where, why}`: every key in the
  private table (owner, people, channel, repository identity, workspace-state and
  machine-path keys); every key the deny table refuses against the template; any key whose
  name or value, and any charter line or ledger reason, containing a private value (whole
  word), an absolute path, or a redactor finding. A redactor that cannot run fails the
  export (exit 2).
- **FR-003**: `charters` holds, per workspace override `.wuwei/charters/<role>.md` of a
  shipped role, the non-blank lines not in the shipped charter, and the reasons of landed
  ledger records for that target.
- **FR-004**: One deny table lists what a profile may never carry, each row a key pattern
  and a refusal rule against the current value: `decisions.cruise.enabled` turned on,
  `decisions.cruise.levels.*` above the level the class runs at (`decision.level`),
  `repos.gates.floor` lowered, `repos.merge.auto` true, `shepherd.autostart` true, and
  `adapters.*`, `calendar.url`, `watch.ping_url`, `codex.command` always. Private keys are
  always refused. Import refuses a profile with any such key: exit 1, each key named,
  nothing written.
- **FR-005**: `wuwei calibrate import SOURCE [--repo NAME] [--skip KEY ...]` reads a starter
  name under `templates/profiles/`, an `https` URL or a file; validates the shape; refuses
  (FR-004); flags instruction-like config values and charter roles
  (`calibrate.instruction_like` on each string, line and reason) and leaves them out; drops
  `--skip` keys; previews the config with `calibrate.propose`; writes today's
  `profile.json` (only the accepted part) and `proposals/profile-<role>.json` add
  proposals with reason `profile <name>: <reasons>` and evidence `profile.json`; prints
  the diff, the proposal paths, the flags and the next step. Exit 0 clean, 1 refused or
  flagged, 2 could not run.
- **FR-006**: `wuwei config promote` reads today's `profile.json` (absent: nothing),
  re-runs the shape check, the deny table and the instruction scan against the current
  config (any hit or a malformed file is exit 2), puts its settings before the interview
  settings (dropping a profile setting whose key an interview answer sets), and lists
  `Profile <name>: <key> = <value>` lines in the digested summary.
- **FR-007**: `profile.json` is a protected day file: an agent tool write is refused by
  protect_state, like `interview.json`.
- **FR-008**: Two starter profiles, `python-library` and `cli-tool`, derived from WUWEI's
  own configuration, ship under `templates/profiles/` and are documented in
  `docs/site/configuration.md`.
- **FR-009**: The profile module stays off every hook path.

### Key Entities

- **Profile file**: JSON object `{wuwei_profile: 1, name, config, charters, dropped}`.
  `config` is nested like `config.toml`, except `repos` is one table applied to each
  repository. `charters` maps a shipped role to `{text, reasons}`. `dropped` is
  `[{where, why}]`, informative only; import ignores it.
- **profile.json** (day file): the accepted part of an import, in the same shape, plus
  `repos`, the repository names it targets. Written only by the CLI, re-validated on read.

## Success Criteria

- **SC-001**: An exported profile from a workspace seeded with personal values contains
  none of them (string search over the file text), and lists each drop.
- **SC-002**: Every row of the deny table is refused by import with its key named, in a
  table test, and its allowed direction (lowering a cruise level, raising the floor,
  `merge.auto = false`) is accepted.
- **SC-003**: No profile change reaches `config.toml` or a charter without
  `config promote` or `wuwei promote`.
- **SC-004**: Both starter profiles import clean; the full suite passes.

## Assumptions

- "Promoted calibration" is the workspace's current `config.toml` and charter overrides:
  both change only through owner promotes or owner edits. Export does not require
  `.wuwei/calibration.json`.
- Interview answers travel through their promoted effects (config keys and charter
  override lines). The voice profile (`memory/voice.md`) is personal and is never exported.
- Private keys, dropped on export and refused on import: `owner`, `control_plane.owner`,
  `repos.name`, `repos.path`, `repos.default_branch`, `repos.identity`,
  `repos.merge.bot_login`, `voice`, `outbound.work_channels`, `outbound.external_channels`,
  `outbound.company_domains`, `outbound.code_host_orgs`, `outbound.people`,
  `shepherd.review_channel`, `shepherd.lead_login`, `shepherd.authors`,
  `tracker.backlog_filter`, `retro.repo`, `metrics.transcripts`, `scanner.mcp` and
  `guards` (the guard mode and shadow start belong to one workspace's first week).
- "Adapter credential": credentials live in the environment, not config. A profile may not
  set any `adapters.*` key (the adapter choice comes with host credentials) nor the
  credential-like keys `calendar.url`, `watch.ping_url` and `codex.command`.
- Repository names are matched as the full configured `name` (for example `acme/widget`),
  not its parts, so a common word that is also a repository's short name is not dropped
  everywhere.
- An absolute path is a token starting with `~/`, a drive letter and a slash, or `/`
  followed by at least two path segments; a slash command such as `/wuwei plan` is not a
  path. The redactor's secret patterns also catch field words such as `token:`; such
  lines are dropped (conservative).
- Per-change acceptance is `--skip` at import plus the existing gates: the digest of
  `config promote` (all or nothing for what is listed) and `wuwei promote` per charter
  proposal. No new interactive selection.
- A refused key refuses the whole profile (fail closed); instruction-like text drops only
  its key or its role block, as calibrate drops only the affected source.
- Profile list values replace the workspace's list (as interview settings do), except
  `deploy.deny` and `deploy.workflows`, which only grow (`calibrate.settle`). Other
  weakening keys (for example `outward.patterns = []`) are not in the deny table; the owner
  sees each in the digest. The issue names the deny list; widening it is a later issue.
- Export writes `<name>.json` in the current directory. Import from a URL uses stdlib
  `urllib.request` directly (no external tool, no new adapter).
- No new event kind or state key.
