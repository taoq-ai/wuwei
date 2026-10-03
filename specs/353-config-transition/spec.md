# Feature Specification: Keys from a newer template warn instead of refusing, and setup and doctor say when to restart Claude Code

**Feature Branch**: `353-config-transition`
**Created**: 2026-10-03
**Status**: Ready for implementation
**Input**: Issue #353, fix(config). Builds on #243 (`config check`), #324 (`.in_use`
markers), #326 (config failure mode), #327 (setup), #331 (posture), #339 (doctor).
Evidence: the owner's second first-day trial, 2026-10-03, between the plugin upgrade and
the restart.

## Root cause (reproduced read-only)

After the upgrade, one Claude Code process still had the previous version loaded: the
plugin cache held two version directories, each with its own `.in_use/<pid>` marker, and
both processes were alive. The old version's hooks read the upgraded `config.toml`.

Reproduced in a scratch workspace outside the repository against this branch: the shipped
template plus one key this version does not know (`blok = ["high"]` under
`[scanner.mcp]`), a Bash `ls` PreToolUse payload piped to
`python3 -P -m wuwei hook PreToolUse`:

```text
guarded: exit 2, permissionDecision deny,
  "config.toml: unknown key scanner.mcp.blok at line 110; remove it or use a documented key"
strict:  the same
config check (both postures): exit 1, the same text
```

- `cli/wuwei/workspace.py:416-424`, `_validate`: any key not in `SCHEMA` raises
  `ConfigError` on the spot, whatever the posture.
- `cli/wuwei/workspace.py:466`, `load_config`: that error escapes before the posture is
  known, so no posture can soften it.
- `cli/wuwei/commands/hook.py:51-56` loads the config on every PreToolUse and Stop;
  `hook.py:63-64` routes the `ConfigError` to `config_failure` (`hook.py:107-118`, #326),
  which refuses every tool call except the repair reads. Every guard's `workspace.scope`
  (`workspace.py:271`) hits the same raise.
- Nothing compares the plugin version to the version that wrote the file, and nothing
  reads the other version's `.in_use` marker, so neither the hook nor `setup`, `init
  --upgrade`, `doctor` or the status line says a restart is needed.

## User Scenarios & Testing

### User Story 1 - A typo key warns, it does not stop the session (Priority: P1)

The owner mistypes a key. Under `observe` and `guarded` every tool call still passes;
`config check` and `doctor` name the key, its line and the nearest documented key. Under
`strict` the key refuses as today.

**Independent Test**: in process, `workspace.load_config(root, warnings=found)` and the
PreToolUse hook replayed with `hook.run`, one config per posture.

**Acceptance Scenarios**:

1. Given `[scanner.mcp]` with `blok = ["high"]` under `guarded`, when `config check`
   runs, then it prints a warning naming `scanner.mcp.blok`, its line and
   `did you mean scanner.mcp.block?`, and a PreToolUse Bash `ls` exits 0 with no deny.
2. Given the same key under `strict`, then `load_config` raises `ConfigError` with that
   text and the PreToolUse hook denies it as today (#326 failure mode).
3. Given an unknown key with no close documented key (`nonsense = 1`), then the text
   ends `remove it or use a documented key` as today.
4. Given the typo under `guarded`, when `doctor` runs, then the Workspace `config` row is
   `warn` with the warning as its detail.

### User Story 2 - An old hook against a newer template keeps working and says restart (Priority: P1)

`config.toml` carries `template_version`. A hook whose plugin is older than it never
refuses for a key it does not know, in any posture, logs one `config.newer_template`
event per session, and `doctor` and the status line name the restart.

**Independent Test**: a fake plugin directory whose `.claude-plugin/plugin.json` says
`0.12.0`, monkeypatched as `integrity.PLUGIN`; a workspace config with
`template_version = "0.13.0"` and a key `0.12.0` does not know.

**Acceptance Scenarios**:

1. Given plugin `0.12.0`, `template_version = "0.13.0"`, an unknown key and
   `security.posture = "strict"`, when two PreToolUse Bash `ls` calls of one session run,
   then both exit 0 and today's events hold exactly one `config.newer_template` with
   `{plugin: "0.12.0", template: "0.13.0", session}`.
2. Given the same workspace, when `doctor` runs, then the Install `in_use` row is `warn`
   with value `plugin 0.12.0 running against template 0.13.0: restart Claude Code`, and
   `status --line` contains that text.
3. Given `template_version` equal to or older than the plugin, or empty, or unparseable,
   then nothing is logged and the strict rule of US1 applies.
4. `bin/wuwei event config.newer_template` is refused as reserved.

### User Story 3 - Setup and upgrade write the version and say restart when another version runs (Priority: P1)

`init`, `setup` and `init --upgrade` write `template_version` as this plugin's version
(never lowering it). `setup`, `init --upgrade` and the release notes end with
`Restart Claude Code so only this version's hooks run` when another version's `.in_use`
marker is present.

**Independent Test**: plugin directories `cache/0.12.0` and `cache/0.13.0` under
`tmp_path`, each with `.in_use/<pid>`; `integrity.PLUGIN` monkeypatched to the newer one.

**Acceptance Scenarios**:

1. Given `setup` on a host where another plugin version's marker exists, then the last
   line of its stdout is the restart instruction; without that marker it is not printed.
2. Given `init --upgrade` on a workspace with no `template_version` and another
   version's marker, then the config gains `template_version = "<this version>"` and the
   last stdout line is the restart instruction; `--dry-run` shows the change and writes
   nothing.
3. Given `template_version` newer than this plugin, then `init --upgrade` and `setup`
   leave it unchanged.
4. Given a new workspace, `init` writes `template_version = "<this version>"`; a
   following `init --upgrade` reports no changes.
5. The release workflow appends the restart line to every release's notes.

### User Story 4 - The marker exclusion holds across an upgrade (Priority: P2)

**Independent Test**: `tests/test_integrity.py`, two signed cache directories with
markers in both.

**Acceptance Scenarios**:

1. Given `cache/0.12.0` and `cache/0.13.0`, each signed and each holding `.in_use/<pid>`,
   when `measure` runs on either, then it exits 0 with the fingerprint measured without
   markers, and `other_versions` on each names only the other.

### Edge Cases

- A typo in the posture key itself (`postur = "strict"`) leaves the posture at its
  default, so the key is a warning. The warning names it; that is the only signal.
- `guards.mode = "shadow"` is observe, so unknown keys warn.
- An unknown key inside a `*` table (`boundary`, `environments`, `voice.sources`,
  `outward.max_length`, `shepherd.authors`, `decisions.cruise.levels`) is a name, not a
  key; unchanged.
- A newer template that changes a value's allowed set (a new enum value) still fails as
  today; only unknown keys are tolerated.
- The plugin version is unreadable: no newer-template comparison, no event, no stamp.
- A development checkout's siblings have no `.in_use`; nothing is reported.
- The first upgrade that ships this change cannot help hooks already running the version
  before it: those hooks do not know `template_version` and will refuse under it until
  the restart. The restart line from `setup` and `init --upgrade` is the mitigation.

## Requirements

- **FR-001**: `_validate` collects unknown keys instead of raising when the caller passes
  a list; each entry is the existing text with the nearest documented key at the same
  table level (`difflib.get_close_matches`, n=1, default cutoff):
  `unknown key <key> at line <n>; did you mean <nearest key>?`, else the existing
  `; remove it or use a documented key`. Without a list it raises as today.
- **FR-002**: `load_config` raises the first unknown-key text as `ConfigError` only when
  the posture is `strict` and the template is not newer than the plugin. Otherwise the
  config loads and the texts are returned to callers that pass `warnings=<list>`.
- **FR-003**: `template_version` is a top-level string key, default `""`, in `SCHEMA` and
  in the template with a comment.
- **FR-004**: The PreToolUse hook appends one `config.newer_template` event per session
  per day when the plugin is older than `template_version`; recording failures print to
  stderr and never refuse. The kind is reserved in `EVENT_PRODUCERS`.
- **FR-005**: `config check`, `doctor` (Workspace `config` row, `warn`) and `init
  --upgrade` print the warnings; `config check`'s exit code is unchanged by them.
- **FR-006**: `doctor`'s Install `in_use` row and `status --line` show
  `plugin <old> running against template <new>: restart Claude Code` when another plugin
  version's `.in_use` directory holds a marker, or this plugin is older than
  `template_version`.
- **FR-007**: `init`, `setup` and `init --upgrade` set `template_version` to this
  plugin's version when it is empty, unparseable or older; never lower it.
- **FR-008**: `setup` and `init --upgrade` (not its dry run) print
  `Restart Claude Code so only this version's hooks run` as their last stdout line when
  another version's marker is present; the release workflow appends it to the notes.
- **FR-009**: Docs: `configuration.md` (unknown keys, `template_version`) and
  `reference.md` (doctor `in_use` row, status line, the event) say the above.

### Key Entities

- `template_version`: the plugin version that last wrote `config.toml`.
- Other version marker: a non-empty `.in_use/` directory in a sibling of this plugin's
  install directory (Claude Code's cache keeps one directory per version).
- `config.newer_template` event: `{plugin, template, session}`, written only by the hook.

## Success Criteria

- SC-001: After an upgrade, no tool call is refused because the old hooks meet a key from
  the new template, in any posture.
- SC-002: The owner is told to restart by `setup` or `init --upgrade`, and again by
  `doctor` and the status line until no other version is loaded.
- SC-003: A typo key is named with its line and nearest key in `config check` and
  `doctor` in every posture.

## Assumptions

- `config check` keeps its exit code when the only issue is an unknown key: the issue
  calls it a warning, and `doctor`'s `warn` row already makes `doctor` exit 1.
- Owner edit commands that validate the proposed text through `calibrate.apply`
  (`config set`, `config add-repo`, `config promote`, `setup`) keep refusing a config
  with an unknown key: they write the file, so the owner fixes the key first. Hooks,
  guards, `config check`, `doctor`, `status` and `init --upgrade` warn.
- "Another version's marker is present" means a sibling directory of the install
  directory with a non-empty `.in_use/`, as on the owner's host (one directory per
  version under the plugin cache). Marker liveness is not checked: Claude Code removes
  them, and the host showed only live ones.
- "One event per session" is per session per day, deduplicated from today's
  `events.jsonl`; this read happens only while the plugin is older than the template.
- Only PreToolUse records the event; Stop and SessionStart do not.
- The release notes line is unconditional: the workflow cannot see the owner's host.
- Versions compare as dotted integers; anything else is "not comparable" and never newer.
- The owner's separate note in this run (`--shadow` should mean posture observe) is
  issue #355 and is not part of this feature.

## Deferred

- None.
