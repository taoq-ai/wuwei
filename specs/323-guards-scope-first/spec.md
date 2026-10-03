# Feature Specification: Outside a WUWEI workspace every hook does nothing

**Feature Branch**: `323-guards-scope-first`
**Created**: 2026-10-03
**Status**: Ready
**Input**: GitHub issue #323, "fix(guards): outside a WUWEI workspace every hook does nothing, including when a command cannot be parsed"; design 9.1 (guard scope) and 4.5; follows #205, #222, #226.

## Problem (reproduced)

With v0.11.0 (main at 69453ed) installed for the whole machine, a Claude Code session whose
cwd has no `.wuwei/` above it is refused on ordinary Bash calls. Reproduced on `main` by
piping PreToolUse payloads through `bin/wuwei hook PreToolUse` with `WUWEI_WORKSPACE` unset
and the cwd a fresh temporary directory:

- `set -e; P=/tmp/x; cd $P && python3 - <<'PYEOF'` followed by a Python body that mentions
  `gh` and `git` in strings: exit 2, "commit/push guard could not run: unaccounted git/gh
  mention; run git or gh as a plain command" and "PR guard could not run: unaccounted
  git/gh mention".
- `ls ~/.claude/plugins/cache/wuwei/wuwei/`: exit 2, "use a literal path instead of tilde
  expansion".
- `ls -la`: exit 0.

Root cause. The dispatcher `run` in `cli/wuwei/commands/hook.py` (lines 35 to 50) already
computes the workspace root for the call, but then discovers and runs every guard whether
or not a root was found. Each guard does its own scope check, and three of them reach a
fail-closed path first:

- commit/push (`cli/wuwei/guards/commit_push.py` lines 280 to 298): when `shell.normalize`
  raises and the cwd has no session root, any `cd`, `-C`, `pushd`, `GIT_DIR` or similar
  word in the raw text re-raises ("parsing may have stopped before a target"), which
  becomes exit 2 at lines 426 to 430.
- PR (`cli/wuwei/guards/pr.py` lines 355 to 360): on a parse error outside a workspace,
  `possible_workspace_change` (lines 53 to 65) answers True for any `cd` whose target is
  not literal (`cd $P`), so the error re-raises and exits 2 at lines 399 to 400.
- protect_state (`cli/wuwei/guards/protect_state.py`): `check_bash` computes `root` (line
  388) but does not stop on `None`; `_write_targets` (lines 340 to 341) passes `ls`
  operands to `_protected`, whose `_path` (lines 164 to 167) raises on a leading `~`,
  which exits 2 at line 485.

Patching each guard leaves every other pre-scope path in place. The fix is one scope gate
in the dispatcher, before env loading, guard discovery or any parsing.

## User Scenarios & Testing

### User Story 1 - Unrelated sessions are never touched (Priority: P1)

The owner installs WUWEI for the whole machine and works in other projects. No hook
refuses, warns or prints anything there, whatever the command or tool call looks like.

**Independent Test**: run every guard table row, every bypass row, every "could not run"
shape and the two trial commands through `wuwei.commands.hook.run` in process, with a cwd
that has no workspace above it, and assert exit 0 with empty stdout and stderr.

**Acceptance Scenarios**:

1. Given the two trial commands and every guard table row with a cwd that has no workspace above it, when each hook event runs, then every hook exits 0 with no output.
2. Given the same outside cwd, when a parse error, a tilde path, a command substitution, shell control flow, a heredoc mentioning git and gh, or an unknown git or gh alias is submitted, then the hook exits 0 with no output and guard discovery is never called.
3. Given the same outside cwd, when any recorded payload for any of the six events is replayed, then the hook exits 0 with no output and writes no file.

### User Story 2 - Inside a workspace nothing changes (Priority: P1)

Seats, the planner and the owner inside a workspace, a configured repository or a managed
worktree keep every current verdict.

**Independent Test**: the existing guard suites pass unchanged; the trial commands run
from inside a workspace through the hook keep their current refusals.

**Acceptance Scenarios**:

1. Given the same rows inside a workspace, when the hook runs, then verdicts are unchanged.
2. Given a cwd outside any workspace and a command whose literal path targets a workspace, a configured repository under it or a managed worktree (`git -C <repo> push --force`, `rm -rf <workspace>/.wuwei/days`), when the hook runs, then the guards run exactly as today (design 9.1: "or a path it targets").
3. Given `WUWEI_WORKSPACE` is set, when the hook runs from any cwd, then the guards run exactly as today.

### User Story 3 - The gate cannot be silently removed (Priority: P2)

**Independent Test**: the guard mutation harness disables the gate and expects the
outside probe to go red.

**Acceptance Scenarios**:

1. Given a guard modified to skip the scope check (the dispatcher gate replaced by one that always answers "in scope"), when the meta-test's outside probe runs, then it fails.
2. Given a guard that refuses every call, when the hook runs outside any workspace, then the hook exits 0 and guard discovery is never called.

### Edge Cases

- A literal target given as `--git-dir=<path>`, `GIT_DIR=<path>`, `-C<path>`, a quoted path inside `sh -c '...'` or `eval "..."`, a relative path with a slash, or a bare directory name in the cwd is still a target.
- A nonliteral target (`cd $P`, `cd "$(...)"`) is not resolvable; outside a workspace it passes.
- A word naming the directory that directly contains a workspace (`rm -rf <parent>`) counts as a target, keeping protect_state's one-level container check.
- An inherited `GIT_DIR` or `GIT_WORK_TREE` pointing into a workspace keeps the guards on.
- A word that cannot be expanded or resolved (`~nosuchuser/x`, a path loop) is not a target and is skipped.
- A malformed hook payload (not JSON, missing `cwd`) is still refused as today: scope cannot be decided without a valid `cwd`.
- A workspace marker that raises while scoping (a symlinked `.wuwei`, an invalid worktree anchor, an unreadable config) counts as in scope, so the guards report it as today.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei hook <event>` decides scope before env loading, guard discovery, normalisation or any relevance scan. Out of scope, it returns 0 and prints nothing, for every event.
- **FR-002**: A call is in scope when its cwd or a file target is in a workspace, configured repository or managed worktree (the root the dispatcher already computes), when `WUWEI_WORKSPACE` is set, or when a literal path word of the call (a Bash command word, `notebook_path`, inherited `GIT_DIR` or `GIT_WORK_TREE`) lies in, is, or directly contains a workspace or managed worktree.
- **FR-003**: Scope is decided with the existing helpers (`workspace.scope`, `workspace.guard_scope`, `workspace.find_workspace`); the container check moves from `protect_state` into `workspace` and both callers use it.
- **FR-004**: No guard module changes its verdicts when called directly; the gate lives only in the dispatcher.
- **FR-005**: The hook budget under `WUWEI_BENCH=1` does not grow: in-scope calls pay one extra test of the root already computed; out-of-scope calls skip discovery.
- **FR-006**: A meta-test covers every guard table row, bypass row and "could not run" shape outside a workspace, and the mutation harness fails when the gate is disabled.

### Key Entities

- **Scope gate**: one function in `cli/wuwei/commands/hook.py` answering whether a hook payload can reach a workspace.

## Success Criteria

- **SC-001**: Every harvested guard table row, both trial commands and every recorded payload exit 0 with empty output outside a workspace.
- **SC-002**: The full existing suite passes with no existing test edited.
- **SC-003**: Replacing the gate with an always-in-scope stub makes the mutation harness red.

## Assumptions

- Design 9.1 ("a guard acts only when the session cwd or a path it targets ... is inside a WUWEI workspace") wins over the issue's literal "whatever the command": a Bash command run from an outside cwd that names a workspace path literally is in scope, so #164's outside-cwd target rows keep their refusals through the hook. The issue's acceptance is read as "a cwd with no workspace above it and no workspace among the call's literal targets". This conflict is raised here, not resolved silently (constitution).
- "Every guard table row" is harvested from the parametrize tables of the guard test modules (the `command`, `script`, `form`, `wrapper` and `operation` arguments), placeholders filled with paths under the outside directory, plus the mutation harness PROBES and the recorded payloads; rows added to those tables later are covered automatically.
- A nonliteral directory change from an outside cwd (`cd $P`, bare `cd` to HOME, `cd -`, CDPATH) is accepted as unguarded; the code host and the worktree pre-push hook are the anchors (design 4.5, 9.1).
- A `WUWEI_SEAT_ROLE=shepherd` process outside any workspace is no longer refused by the PR guard's shepherd rule; shepherd seats run in managed worktrees, which are in scope.
- The release smoke's outside-workspace probe with a heredoc mentioning gh is run by the orchestrator, not in this change.
- The trial's other defects (integrity `.in_use` markers, MCP registry, config parsing, B4 to B9) are separate issues.
- Extension hooks are skipped.
