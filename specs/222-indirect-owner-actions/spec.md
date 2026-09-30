# Feature Specification: Owner-only actions are refused in indirect forms too

**Feature Branch**: `222-indirect-owner-actions`
**Created**: 2026-09-30
**Status**: Ready
**Input**: GitHub issue #222, "fix(guards): owner-only actions are refused in indirect forms too"

## Problem (reproduced)

Reproduced on `main` in a scratch workspace (`.wuwei/config.toml`, seeded integrity,
`WUWEI_WORKSPACE` unset), both through `bin/wuwei hook PreToolUse` and by calling
`protect_state.check_bash` in process. The table shows the guard exit inside the workspace
today (0 means allowed); the literal form (`bin/wuwei watch uninstall`) is denied as
expected.

| Owner action | `$VAR` subcommand | `echo <verb> \| xargs bin/wuwei <group>` | `bin/wuwei <group> -- <verb>` | `./wrap.sh` or `sh wrap.sh` |
|---|---|---|---|---|
| `decision outcome` | 0 | 2 | 0 | 0 |
| `drafts approve`, `drafts drop` | 0 | 0 | 2 | 0 |
| `mcp decide` | 0 | 2 | 2 | 0 |
| `integrity reconfirm` | 1 | 1 | 1 | 0 |
| `state recover` | 1 | 1 | 1 | 0 |
| `watch uninstall` | 0 | 0 | 1 | 0 |
| `goals edit`, `voice edit` | 0 | 0 | 0 | 0 |

Root cause. `check_bash` in `cli/wuwei/guards/protect_state.py` (line 261) holds six
separate owner-action rules, each with its own relevance test and its own argv walk:

- `decision outcome` (relevance lines 271 to 273, walk lines 311 to 321) compares
  `action[:2] == ['decision', 'outcome']`, so `decision -- outcome` and `$D outcome` fall
  through to exit 0. It refuses any non-CLI command in a relevant script, which is why
  the `xargs` form happens to exit 2.
- goals and voice edit (relevance lines 274 to 278, walk lines 322 to 337) compare
  `action[:2]` the same way.
- `integrity reconfirm` (lines 279 to 283) and `state recover` (lines 285 to 287) are
  text-only rules that exit 1 before parsing; they never see a script file.
- `mcp`, `drafts` and `watch` (relevance lines 288 to 297, walk lines 338 to 367) look up
  the literal group word in argv (`'watch' in argv`, `'drafts' in argv`, `'mcp' in argv`),
  so `$W uninstall`, `$D approve` and `$M decide` never match.

Underneath, `shell.normalize` keeps `$W` as a plain argv word for any program that is not
`git` or `gh` (`cli/wuwei/shell.py` lines 467 to 473), and unwraps `xargs` into the inner
argv with no trace that stdin supplies more arguments (lines 519 to 528): `echo approve |
xargs bin/wuwei drafts` reaches the guard as `bin/wuwei drafts`, a harmless listing. No
owner rule reads a script file: `./wrap.sh` normalises to `['./wrap.sh']`, whose text
names neither the CLI nor an owner verb. The script inspection that commit/push, deploy
and PR use (`shell.script_text`, issues #18 and #205) is not used by `protect_state`.

## User Scenarios & Testing

### User Story 1 - Indirect owner actions are refused inside a workspace (Priority: P1)

A seat (or a prompt injection driving one) tries an owner-only action through an indirect
form: a variable in place of the subcommand, arguments fed through `xargs`, a `--` before
the verb, or a script file that contains the command. PreToolUse refuses it with exit 1
when the owner action is recognised, and exit 2 when it is not literal.

**Why this priority**: owner-only actions (decisions, outward sends, integrity trust, state
restore, watch removal, owner memory) must never be taken by an agent tool; today four
indirect forms bypass the guard.

**Independent Test**: table test over every owner action and every indirect form, calling
`check_bash` in process inside a seeded workspace and in a directory outside any workspace;
the script-file form also runs through `wuwei.commands.hook.run` with event PreToolUse.

**Acceptance Scenarios**:

1. Given a session inside a workspace, when Bash runs `W=watch; bin/wuwei $W uninstall`
   (and the same variable form for `decision outcome`, `drafts approve`, `drafts drop`,
   `mcp decide`, `integrity reconfirm`, `state recover`, `goals edit`, `voice edit`), then
   PreToolUse refuses it with exit 2 (not a literal action; use the host terminal).
2. Given a session inside a workspace, when Bash runs `echo approve | xargs bin/wuwei drafts`
   (and the same `xargs` form for every owner action), then PreToolUse refuses it with exit 2.
3. Given a session inside a workspace, when Bash runs `bin/wuwei decision -- outcome x`
   (and the same `--` form for every owner action), then PreToolUse refuses it with exit 1.
4. Given a script file `wrap.sh` whose text is `bin/wuwei <group> <verb>` for an owner
   action, when Bash runs `./wrap.sh` or `sh wrap.sh` inside a workspace, then PreToolUse
   refuses it with exit 1.
5. Given each command in scenarios 1 to 4, when the session cwd is outside any workspace,
   then PreToolUse returns 0.

### User Story 2 - Ordinary work is not blocked (Priority: P1)

**Why this priority**: a guard that blocks ordinary commands gets switched off.

**Independent Test**: the allow rows of the same table.

**Acceptance Scenarios**:

1. Given a session inside a workspace, when Bash runs `python3 -m pytest -q`, a `for` loop,
   `export X=1`, `bin/wuwei state get` or `grep -rn uninstall docs/`, then PreToolUse
   returns 0.

### User Story 3 - The shared rule has a mutation test (Priority: P2)

**Acceptance Scenarios**:

1. Given `tests/test_guard_mutation.py`, when the shared owner-action rule is replaced by a
   function that finds nothing, then its probe goes red.

## Edge Cases

- `bin/wuwei drafts approve "$ID"`: the verb is literal, so this is a recognised owner
  action (exit 1), as today.
- `bin/wuwei mcp $ACTION`: an owner group with a non-literal verb is exit 2, as today.
- `bin/wuwei state transition "$i" review`, `bin/wuwei note "$MSG"`: literal non-owner
  subcommands pass.
- `for x in a; do bin/wuwei drafts approve "$x"; done`: relevant and unparseable, exit 2
  inside a workspace and 0 outside, as today.
- `rg 'wuwei mcp decide' cli` and `grep -rn "wuwei watch uninstall" docs/` pass: a text
  search is not an invocation.
- `expect -c "spawn bin/wuwei decision outcome D-3 A"`, `script -q /dev/null wuwei ...`,
  `unbuffer wuwei ...` and `find . -exec bin/wuwei drafts approve {} \;`: a non-CLI command
  whose arguments name the CLI, in a relevant command, is exit 2.
- `python3 -c 'integrity.reconfirm()'` and other interpreter snippets in a relevant command
  are exit 2, as today.
- A script file that forwards its arguments (`bin/wuwei "$@"`) has a non-literal
  subcommand: exit 2.
- Outside a workspace no script file is read.

## Requirements

### Functional Requirements

- **FR-001**: One table in `protect_state` lists every owner-only action as a (group, verb)
  pair with its refusal reason: `decision outcome`, `drafts approve`, `drafts drop`,
  `mcp decide`, `integrity reconfirm`, `state recover`, `watch uninstall`, `goals edit`,
  `voice edit`. One relevance function and one argv walk serve every row; no per-action
  rule remains.
- **FR-002**: Relevance is decided from the raw text before parsing, with no file read or
  subprocess: the text names the wuwei CLI (or a literal owner pair such as
  `integrity.reconfirm`) and an owner verb is reachable (a literal verb token, or the
  shared `shell.mentions` conservative check). The workspace scope is checked only when
  the rule would refuse.
- **FR-003**: A wuwei CLI invocation whose subcommand and verb, ignoring options and `--`,
  form an owner pair is exit 1 with that pair's reason.
- **FR-004**: In any parsed command, a wuwei CLI invocation whose subcommand is not literal,
  or whose owner group has a non-literal verb, is exit 2 ("Not a literal owner action; use
  the host terminal.").
- **FR-005**: In a relevant command, `xargs` anywhere, an opaque command or interpreter, or
  a non-CLI command (other than `grep` or `rg`) whose arguments name the CLI is exit 2;
  a parse failure of a relevant command is exit 2.
- **FR-006**: A local script file the command runs (found by the existing
  `shell.script_text`) is judged by the same rule, with script-mode relevance
  (`mentions(..., script=True)`) over the command plus the script text; a relevant script
  that cannot be parsed is exit 2. It is read only when the session is in a workspace.
- **FR-007**: Outside a workspace every form returns 0.
- **FR-008**: Every CLI host-terminal confirmation (`integrity._host_confirm` and its
  callers) stays unchanged as the last line of defence.
- **FR-009**: The #18 mutation test disables the shared rule and asserts its probe fails.

## Success Criteria

- Every cell of the reproduction table is refused inside a workspace (exit 1 for the `--`
  and script-file forms, exit 2 for the variable and `xargs` forms) and is 0 outside.
- The allow rows of User Story 2 return 0 inside a workspace.
- Existing guard tables keep their expected exits, except one row named in the plan
  (`python3 -mwuwei decision outcome D-3 A` goes from 2 to 1; still refused).
- No new subprocess, and no new file read for a command that does not run a local script.

## Assumptions

- goals and voice edit are owner-only actions (spec of #169, refusal "Owner memory edits are
  an owner action on the host") and get the same rule. They have no host-terminal
  confirmation, so the guard is their only local refusal; that makes the indirect forms
  more urgent there, not less.
- "Recognised owner action" (exit 1) means the subcommand and verb are both literal words
  in the invocation (the `--` and script-file forms). The variable form has a non-literal
  subcommand and the `xargs` form takes its verb from stdin, so both are exit 2.
- Any `python -m wuwei` or `python -mwuwei` form (with or without `-P`) is the CLI for this
  rule, as the mcp, drafts and watch rules already treat it. The decision rule treated
  `python3 -mwuwei` as opaque (exit 2); it becomes a recognised action (exit 1). Both are
  refusals.
- A text search (`grep`, `rg`) naming the CLI is not an invocation. Other non-CLI commands
  naming the CLI in a relevant command are refused (exit 2), which keeps the existing
  `expect`, `script` and `unbuffer` rows refused and adds `find -exec` and similar. An
  `echo` that prints a wuwei command line next to an owner verb is refused too; seats
  report through their reply, not through `echo`.
- A verb constructed at run time (`A=unin; bin/wuwei watch ${A}stall`,
  `bin/wuwei state $(printf rec)over`) is not seen before parsing; the host-terminal
  confirmation is the anchor (FR-008). This is the residual already accepted for
  constructed names in `shell.mentions` and `shell.is_opaque`. goals and voice edit have
  no such anchor; the residual is recorded under Deferred in the plan.
- One script level: a script that runs another script, and a command that writes a script
  and runs it in the same call, are not read. The next call that runs the saved script is.
- Loosening that follows from one shared rule and is intended: `bin/wuwei mcp` with no
  action, `bin/wuwei watch --foo` and `bin/wuwei drafts foo` are no longer refused
  (argparse rejects them; none is an owner action).
