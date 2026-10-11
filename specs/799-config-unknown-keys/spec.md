# Feature Specification: unknown keys only warn, and init --upgrade removes the keys the schema no longer reads

**Feature Branch**: `799-config-unknown-keys`
**Created**: 2026-10-11
**Status**: Draft
**Input**: GitHub issue #799, part 2 of the deletion pass #789. Deleting a config key must never
break a live workspace. Unknown config keys only warn under every posture (today `strict`
raises), and `wuwei init --upgrade` removes every key or table the schema no longer reads, says
so per key, honours `--dry-run`, and does nothing when the workspace template is newer than the
plugin.

## Why (read on main at bfbf6a3)

`workspace.load_config` collects unknown keys as warnings (#353) and then, at
`cli/wuwei/workspace.py:812-815`, raises the first one as a `ConfigError` when the posture is
`strict` and `template_version` is not newer than the plugin. Every hook, `config check`,
`doctor` and `init --upgrade` loads the config, so under `strict` one stale key refuses every
tool call. The rest of the deletion pass (#789, PRs 3 to 24) deletes config keys and tables
(`nudges`, `telemetry`, `pace`, `grants`, `outbound.tiers` and more). Without this change each
of those merges would turn every `strict` workspace into a wall until the owner edits
`config.toml` by hand.

An unknown key is never read, so it cannot change what WUWEI does. Refusing over it stops no
process error from the #789 list (seat without a brief, gate on the wrong head, verdict missing
rows, fix round past budget, PR raised outside WUWEI, merge outside policy).

`wuwei init --upgrade` today refuses outright on such a workspace (exit 1 with the unknown key,
no writes; `tests/test_workspace.py::test_upgrade_rejects_unknown_key_without_writes`) and,
below `strict`, only prints a warning per key. The one key it already retires is
`guards.mode` (`_retired_mode`, #355), a key the schema still reads.

## User Scenarios & Testing

### User Story 1 - A strict workspace survives a deleted key (Priority: P1)

The owner runs `security.posture = "strict"`. A plugin update deletes a key their
`config.toml` still holds. Every hook, `config check` and `doctor` still load the config; each
names the key once as a warning.

**Independent Test**: write a `strict` config with one unknown key, call
`workspace.load_config(root, warnings=found)`; it returns and `found` holds exactly one text
naming the key and its line.

**Acceptance Scenarios**:

1. **Given** a `strict` config with `[scanner.mcp]` holding `blok = ["high"]`, **When** it
   loads, **Then** it returns the config and the warnings are exactly
   `config.toml: unknown key scanner.mcp.blok at line <n>; did you mean scanner.mcp.block?`.
2. **Given** the same config, **When** a PreToolUse hook runs `ls`, **Then** it exits 0 with
   no deny.
3. **Given** a `strict` config whose `[[outbound.tiers]]` row holds an unknown key, **When** it
   loads, **Then** it still raises in every posture (#496, kept).

### User Story 2 - init --upgrade removes what the schema no longer reads (Priority: P1)

The owner runs `bin/wuwei init --upgrade` after the plugin update. It removes each key or
table the schema does not read, prints one line per key, and the rest of `config.toml` parses
to the same values as before.

**Independent Test**: a previous workspace with `mystery = 1` under `[owner]`; run
`init --upgrade --dry-run`, then `init --upgrade`.

**Acceptance Scenarios**:

1. **Given** a `strict` workspace with `owner.mystery`, **When** `init --upgrade` runs,
   **Then** it exits 0, prints `Upgraded config.toml: remove owner.mystery (no longer read)`,
   and the parsed config has no `owner.mystery` while every other owner value is unchanged.
2. **Given** the same workspace, **When** `init --upgrade --dry-run` runs, **Then** it prints
   `Would upgrade config.toml: remove owner.mystery (no longer read)` and no file changes.
3. **Given** an unknown table with a subtable (`[gone]` and `[gone.sub]`), a dotted key
   (`foo.bar = 1`), a key whose value spans lines, or a key inside the second `[[repos]]`
   entry, **When** the removal runs, **Then** the parsed result equals the old parse minus
   exactly the removed keys.
4. **Given** a layout the line removal cannot handle (an unknown key inside an inline table,
   `owner = { name = "a", mystery = 1 }`), **When** `init --upgrade` runs, **Then** it exits 2, names the
   key and the hand fix, and writes nothing.
5. **Given** `template_version` newer than the running plugin, **When** `init --upgrade` runs,
   **Then** no key is removed and no `remove` line is printed.
6. **Given** a likely typo (`host.seatz`, whose warning says `did you mean host.seats?`),
   **When** `init --upgrade` runs, **Then** the key stays in `config.toml`, its warning still
   prints, and one line says `config.toml: kept host.seatz, maybe a typo of host.seats; fix it
   by hand`.

### Edge Cases

- A typo (`host.seatz`) is not read either, but it may be the owner's intended setting, so it
  is never deleted silently: a key whose warning has a `did you mean` near match stays, keeps
  its warning, and the upgrade prints one `kept` line naming it and the suggested key. Only a
  key with no near match is removed.
- Unknown keys that make another validation fail (a misspelt required field) still raise with
  the typo's text, as before #353; that is an error message, not a posture rule.
- `guards.mode` is still in the schema, so `_retired_mode` keeps handling it; the new removal
  never sees it.
- `doctor` needs no change: its template row runs `init --upgrade --dry-run`, so a `Would
  upgrade config.toml: remove ...` line becomes a template-drift warning with the
  `init-upgrade` fix.

## Requirements

### Functional Requirements

- **FR-001**: `load_config` MUST never raise over an unknown key because of the posture; the
  key goes to `warnings` under every posture.
- **FR-002**: The `outbound.tiers` unknown-key refusal (#496) MUST stay in every posture.
- **FR-003**: `init --upgrade` MUST remove every key or table that `load_config` reports as
  unknown with no `did you mean` near match, print `<prefix> config.toml: remove <key> (no
  longer read)` per key, with `<prefix>` `Upgraded`, or `Would upgrade` under `--dry-run`. A
  key with a near match MUST stay in the file, and the upgrade prints `config.toml: kept <key>,
  maybe a typo of <near>; fix it by hand`.
- **FR-004**: The parsed result after removal MUST equal the parsed input minus exactly the
  removed keys; otherwise `init --upgrade` exits 2, names the keys and the hand fix, and
  writes nothing.
- **FR-005**: `--dry-run` MUST write nothing.
- **FR-006**: When `integrity.newer_template(config)` is set, `init --upgrade` MUST remove no
  key.
- **FR-007**: A removal counts as a change: `No workspace changes needed` MUST NOT print when
  a key was removed.
- **FR-008**: A key in `workspace.RETIRED` (empty here; each #789 deletion part adds what it retires) MUST always be removed, near match or not.
- **FR-009** (review fix): dropping an unread section keeps its trailing comment and blank lines (they belong to the next header); `[repos.merge]` after `[[repos]]` maps to that entry; a removal that leaves invalid TOML refuses like FR-004.
- **FR-010** (review fix): `merge.check` refuses, naming the unknown key and its near key, when `merge.*` or the merged repository's `repos.<n>.merge*` holds an unknown key; nothing else refuses. The SessionStart hook prints no config notes today, so it is unchanged. The template's first line states the new rule.

### Key Entities

- **Unknown key**: a dotted path (`owner.mystery`, `repos.1.pth`, `gone`) that `_validate`
  reports as `unknown key <path>`; list indexes are integers.

## Success Criteria

- **SC-001**: A `strict` workspace with an unknown key loads with one warning naming the key.
- **SC-002**: `init --upgrade` on that workspace removes the key when it has no near match,
  prints the line, and the parsed remainder equals the old config minus the removed keys; a
  likely typo stays and is named.
- **SC-003**: `--dry-run` prints the same lines with `Would` and changes nothing.

## Assumptions

Clarify pass, answered with the recommendation (non-interactive):

1. **Likely typos are kept (lead decision, changed from the first draft).** A key with a
   `did you mean` near match may be the owner's intended setting, so deleting it would lose
   that intent silently. It stays, keeps its warning, and the upgrade names it with the
   suggested key. Only a key with no near match is removed. No per-PR list of retired keys.
2. **An unsafe layout fails the upgrade (exit 2, no writes)**, the same contract as
   `_retired_mode` today. A key left in place only warns, so nothing breaks while the owner
   edits it by hand.
3. **Comments above a removed key stay.** The check compares parsed values; orphan comments
   are cosmetic and the template rewrite in #789 PR 24 refreshes the file.
4. **The unknown paths come from the warning texts** that `load_config` already returns
   (`config.toml: unknown key <path>[ at line n]; ...`), walked against the parsed TOML so list
   indexes become integers. `_validate` stays the one place that decides what is unknown
   (Principle III). A quoted key holding a dot does not walk and fails safely under FR-004.
5. **Removal runs first**, on the text after `_without_empty_repos` and before the template
   migration, so `[[repos]]` indexes and line positions match the warnings.
6. **Docs**: one sentence in `docs/site/configuration.md` says unknown keys are errors under
   `strict`; it is false after this change and is corrected in place (no test forces it, but a
   false statement is worse). The site rewrite stays in #789 PR 24.
7. **No invariant row.** #789 PR 1 deletes the constitution bullet that asks for one, and this
   is config loading, not a guard; `tests/test_invariants.py` has no row on unknown keys.
8. **Constitution VII ("Under `strict`, refusals stay")** governs guard refusals. The removed
   raise is a config-load error over a key nothing reads; no guard and no guard area changes.

## Deferred

None.
