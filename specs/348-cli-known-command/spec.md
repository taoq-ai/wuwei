# Feature Specification: the plugin's own CLI is a known command

**Feature Branch**: `348-cli-known-command`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #348, "fix(guards): the plugin's own CLI is a known command: absolute
path, recorded executable or wuwei on PATH, with read-only subcommands and --help passing in
every posture". Evidence: the owner's second first-day trial (2026-10-03, development build
of 0.12.0, posture observe): three refusals of the plugin's own CLI. Builds on #347
(`shell.classify` and `shell.unread`, merged as cc9ccbf).

## Root cause (read and reproduced on main)

Reproduction (read-only): the trial workspace's day events were read for the three
refusals, then each shape was piped through `wuwei hook PreToolUse` in process in a
throwaway workspace (seeded integrity evidence, `.wuwei/executable` recording first the
repository launcher and then a copy under another plugin-cache version directory) under
`observe`, `guarded` and `strict`. Neutral forms:

| Trial event | Exit (observe / guarded / strict) | Refused by |
|---|---|---|
| T1 `<exe> config show \| grep -n -A3 -i 'repos\|\[repo\|tracker' \| head -40` | 0 with a `guard.would_refuse` / 2 / 2 | commit/push guard: "opaque interpreter command: `<exe>` config show" |
| T2 `<exe> mcp decide --help` | 2 / 2 / 2 | state guard: "MCP decisions require the owner terminal", records floor |
| T3 `W=$(cat .wuwei/executable); $W plan session <id> --take-over; $W mcp check` | 0 with an `unparsed` warning / same / 2 | every Bash guard: command substitution (#347 made it `unparsed`) |

The issue text guessed that T1 came from the launcher script's own `$(dirname ...)`. It did
not: the launcher is exempt from script reading (`cli/wuwei/shell.py:150-170`), and the
refusal is the same whether or not the path is recognised. The real chain, with file and
line:

1. Relevance is a false positive. `shell.mentions` strips quotes and backslashes before it
   looks for command words (`cli/wuwei/shell.py:97`, `:126-128`). The grep pattern
   `'repos\|\[repo\|tracker'` becomes `repos|[repo|tracker`, so `[repo` reads as a
   nonliteral command name and the text "mentions" git, gh and rm. `config` is one of the
   commit/push guard's relevance words (`cli/wuwei/guards/commit_push.py:269`), so the call
   is relevant (`:274`).
2. The #347 escape hatch does not know the CLI. `shell.unread` passes a call whose words
   are all read-only (`cli/wuwei/guards/commit_push.py:348`), but `shell._classify` marks a
   word safe only when it is in the program set `shell.READ_ONLY` (`cli/wuwei/shell.py:848`);
   `wuwei` is never there, whatever its subcommand.
3. The commit/push guard then refuses every non-git command in a relevant call whose
   program contains a `/` (`cli/wuwei/guards/commit_push.py:366-371`, the `'/' in
   command.argv[0]` test at `:368`). Bare `wuwei` passes this test; the recorded absolute
   path does not. Reproduced on a single command too:
   `<exe> note add --body "rm the stale config"` exits 2 under strict with "opaque
   interpreter command", while `wuwei note add --body "rm the stale config"` exits 0.
4. `--help` is refused for owner actions. `_owner_action` returns the owner reason for any
   `(group, verb)` in `_OWNER_ACTIONS` (`cli/wuwei/guards/protect_state.py:173-185`) without
   looking at `--help`, so `mcp decide --help`, which only prints usage, hits the records
   floor in every posture.
5. The skills teach the substitution. `skills/wuwei-plan/SKILL.md:8` (and the same line in
   `wuwei-report`, `wuwei-retro`, `wuwei-consolidate`) says "Use the executable recorded in
   `.wuwei/executable`", and the planner turned that into `W=$(cat .wuwei/executable)` (T3).
   The guard side of T3 is correct and stays (#347 `unparsed`); the instruction changes.

`shell._launcher` (`cli/wuwei/shell.py:131-147`) already answers "is this path the plugin's
launcher": the running plugin's `bin/wuwei` by realpath, or the path recorded in the
workspace's `.wuwei/executable`. It is used for script reading and owner actions, not by
`classify` or the commit/push guard.

The doctor reports a stale pointer only indirectly: the `template` row counts "Would upgrade
executable pointer" among the `init --upgrade --dry-run` changes
(`cli/wuwei/commands/doctor.py:227-238`) without naming the recorded path or saying it is
missing.

## User Scenarios & Testing

### User Story 1 - The planner reads through the recorded executable in every posture (Priority: P1)

A planner or seat calls the plugin CLI by the absolute path recorded in `.wuwei/executable`
(or the running plugin's `bin/wuwei`, or `wuwei` on PATH) with a read-only subcommand, alone
or piped into read-only programs. No guard refuses it or records a would-refuse, in any
posture.

**Why this priority**: it is the reported defect; the planner's first reads of the day were
refused.

**Independent Test**: `python -m pytest -q tests/test_cli_known_command.py -k read`.

**Acceptance Scenarios**:

1. Given a workspace under `observe`, `guarded` and `strict` whose `.wuwei/executable`
   records a launcher, when `<recorded executable> mcp check` and
   `<recorded executable> config show` go through PreToolUse, then the hook exits 0 and the
   day has no `hook.refusal` and no `guard.would_refuse` event.
2. Given the same postures, when `<recorded executable> config check | grep -n -A3 -i
   'repos\|\[repo\|tracker' | head -40` (the trial shape with a registered verb) and the
   same pipeline with `mcp check` go through PreToolUse, then the hook exits 0 with no
   refusal and no would-refuse event; the same holds for the running plugin's own
   `bin/wuwei` path and for bare `wuwei`.
3. Given a launcher path whose subcommand writes (`<recorded executable> note add --body "rm
   the stale config"`), when it goes through PreToolUse under `strict`, then the commit/push
   guard does not call it an opaque interpreter command (the hook exits 0, as bare `wuwei`
   does today).

---

### User Story 2 - `--help` always passes; owner actions keep the host-terminal rule (Priority: P1)

A seat can read the usage of any command, owner actions included. Running an owner action
from agent tools is still refused with today's reason.

**Why this priority**: the trial's planner could not read `mcp decide --help` to tell the
owner the command.

**Independent Test**: `python -m pytest -q tests/test_cli_known_command.py -k help`.

**Acceptance Scenarios**:

1. Given any posture, when `<recorded executable> mcp decide --help` goes through
   PreToolUse, then the hook exits 0.
2. Given any posture, when `<recorded executable> mcp decide D-1 proceed` goes through
   PreToolUse from a seat, then it is refused with "MCP decisions require the owner
   terminal" as today.
3. Given `<recorded executable> mcp decide -- --help` (after `--` the word is data, not the
   help flag), then it is refused as today.

---

### User Story 3 - The skills name the accepted form (Priority: P1)

The four workflow skills tell the session to read `.wuwei/executable` once with the Read tool
and call that absolute path directly as the first word of a plain command, with one example,
instead of "use the executable recorded in".

**Why this priority**: the instruction produced T3.

**Independent Test**: `python -m pytest -q tests/test_docs.py -k recorded_executable`.

**Acceptance Scenarios**:

1. Given the plan skill text, then it contains no `$(` and names the Read-then-absolute-path
   form; the same holds for the report, retro and consolidate skills.

---

### User Story 4 - The doctor names a stale recorded executable (Priority: P2)

After an upgrade, `.wuwei/executable` can still point at a plugin version that was removed
from the cache. The doctor says so and prints the fix.

**Why this priority**: an old pointer makes every planner CLI call fail; it is rarer than the
guard refusals.

**Independent Test**: `python -m pytest -q tests/test_doctor.py -k executable`.

**Acceptance Scenarios**:

1. Given a recorded executable that points at a removed plugin version, when the doctor
   runs, then an `executable` row fails, names the recorded path, and its fix is
   `wuwei init --upgrade` (applied by `doctor --fix` as `init-upgrade`).
2. Given a recorded executable that resolves to the installed plugin's `bin/wuwei`, then
   the row is ok.

---

### Edge Cases

- A copy of the launcher at some `.../bin/wuwei` that is neither the running plugin's
  launcher nor the recorded path is not the CLI: the trial pipeline through it is still
  refused under `strict` as an opaque interpreter command.
- `calibrate --questions` is read-only; `calibrate`, `calibrate export` and `calibrate
  import` are not, even with `--questions` added (argparse runs the action).
- `doctor` is read-only; `doctor --fix` is not.
- An unregistered verb (`config show`, `plan show`) is not in the read-only table: as a
  single command it passes as today (argparse rejects it with usage); in a pipeline the
  guards decide as today.
- `$W mcp check` (a launcher held in a variable) stays `unparsed` (#347); the skill text is
  the fix for that form.
- A read-only subcommand with a redirect that writes (`<exe> status --line > out.txt`) is
  not read-only; the guards decide as today.

## Requirements

### Functional Requirements

- **FR-001**: One table in `cli/wuwei/commands/__init__.py` lists the CLI's command paths in
  two sets, `READ_ONLY` and `WRITES`. `READ_ONLY` holds `status`, `why`, `doctor`, `config
  check`, `mcp check`, `integrity check`, `shadow report`, `board`, `sessions`,
  `heartbeat` and `calibrate --questions`. `WRITES` holds every other registered command
  path. A test proves every registered path is in exactly one set and every entry is
  registered.
- **FR-002**: `commands.read_only(args)` is true for `--help` or `-h` anywhere before `--`,
  for `--version` as the first word, and for a `READ_ONLY` path (the longest registered
  path the words start with) whose listed flag is present; it is false with `--fix` and
  for every `WRITES` path or unregistered verb.
- **FR-003**: `wuwei.shell` recognises the plugin CLI: bare `wuwei`, the path recorded in
  `.wuwei/executable`, and a path whose realpath is the running plugin's `bin/wuwei`
  (`_launcher`, reused). `classify` and `unread` take the caller's `cwd` for this; a
  recognised CLI word with literal arguments for which `read_only` is true counts as
  read-only, like `ls`.
- **FR-004**: Every Bash guard that calls `shell.unread` or `shell.classify` passes the
  payload's `cwd`.
- **FR-005**: The commit/push guard does not call a recognised CLI command an opaque
  interpreter command because its first word is a path; its other rules (interpreters,
  hidden git words, more than one command in a relevant call) stay.
- **FR-006**: The state guard's owner-action rule passes a call for which `read_only` is
  true (`--help`); every other owner action keeps today's reason and exit.
- **FR-007**: `wuwei-plan`, `wuwei-report`, `wuwei-retro` and `wuwei-consolidate` replace
  "use the executable recorded in `.wuwei/executable`" with: read `.wuwei/executable` once
  with the Read tool, then call that absolute path as the first word of a plain command (no
  variable, no command substitution), with one example. The session orientation line
  (`cli/wuwei/commands/next.py`) and `docs/site/agent.md` use the same form. No skill
  contains `$(`.
- **FR-008**: `doctor` adds a workspace `executable` row: ok when the first line of
  `.wuwei/executable` resolves to the installed plugin's `bin/wuwei`; otherwise fail, naming
  the recorded path (or the missing file), with fix `wuwei init --upgrade` and apply
  `init-upgrade`.
- **FR-009**: `docs/site/security.md` adds the plugin's read-only subcommands and `--help`
  to the read-only sentence of the `unparsed` paragraph.
- **FR-010**: Unchanged: `_OWNER_ACTIONS`, the program set `shell.READ_ONLY`, the #347
  `unparsed` result for `$W` forms, `setup` and `init` writing `.wuwei/executable`, and the
  host-terminal check inside `doctor --fix`.

### Key Entities

- **Command path**: the words that name a CLI command (`config check`, `mcp decide`,
  `status`); a positional named `action` is part of the path.
- **Read-only table**: `READ_ONLY` and `WRITES` in `cli/wuwei/commands/__init__.py`.
- **Recorded executable**: the first line of `.wuwei/executable`, written by `init` and
  `setup`.

## Success Criteria

- **SC-001**: In all three postures, T2 and T1 with a registered verb give exit 0 and no
  event, and the skills no longer produce T3.
- **SC-002**: The full suite passes; the #347 tests for `$W` forms are unchanged.
- **SC-003**: Adding a CLI command without placing it in one of the two sets fails a test.

## Assumptions

- A1: The notes do not name a dry-run workspace. The trial workspace's day events were read
  (read-only) to get the exact refused commands; the reproduction ran in a throwaway
  workspace. No client name, repository name or local path from the trial is written
  anywhere.
- A2: "Two sets" in the notes are `READ_ONLY` and `WRITES`. Owner-only stays the state
  guard's `_OWNER_ACTIONS` table (tested to sit inside `WRITES`); this issue adds no new
  host-terminal rule. The issue's owner list names `promote`, `init --upgrade`, `doctor
  --fix` and `decide`; today `promote` and `init --upgrade` run from seats, `doctor --fix`
  checks for a host terminal itself, and `decide` is not a command. "Keep the host-terminal
  rule" is read as keep today's behaviour.
- A3: `config show` and `plan show` are not registered commands on main, so they are not in
  the table. The acceptance scenario for `<recorded executable> config show` is about the
  hook (exit 0, no refusal), which holds for the single command; the pipeline acceptance
  uses the registered `config check`. Treating unregistered verbs as read-only was rejected:
  a recorded executable from a newer plugin version can have writer commands this
  version's table does not know.
- A4: "Any path ending in `/bin/wuwei` whose resolved file is the current plugin's launcher"
  is the existing `_launcher` realpath check. A launcher of another installed version is
  recognised only when it is the recorded executable.
- A5: A positional argument named `action` (`mcp`, `integrity`, `shadow`, `signal`,
  `calibrate`) is a verb in the table; other positional choices (hook events, git-hook
  events, dispatch triggers, disposition kinds) are arguments.
- A6: The read-only list is the issue's list mapped to registered paths. Other reading
  commands (`next`, `state get`, `decision show`) are left out; adding one is a one-line
  data change.
- A7: The orientation line in `next.py` and `docs/site/agent.md` carry the same "executable
  recorded in" instruction as the skills, so they change with them; nothing else in the
  docs prescribes how to call the executable.
- A8: The skill example uses a placeholder absolute path (`/opt/wuwei/bin/wuwei`), not a
  local one.
- A9: The quote-stripping relevance false positive in `shell.mentions` (fact 1) is left
  alone: it is the conservative relevance rule other guards rely on, and once the CLI's
  read-only words are known the call passes through `unread` without changing it.
