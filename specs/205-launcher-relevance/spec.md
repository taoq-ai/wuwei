# Feature Specification: The launcher and irrelevant scripts are never refused as opaque

**Feature Branch**: `205-launcher-relevance`
**Created**: 2026-09-30
**Status**: Ready
**Input**: GitHub issue #205, "fix(guards): the plugin's own launcher and irrelevant scripts are never refused as opaque"

## Problem (reproduced)

In the v0.5.0 operator dry run, every Bash call to the plugin's own launcher inside a
workspace was denied by three guards at once, from the workspace root and from an item
worktree (`<plugin>/bin/wuwei state get`, `<recorded executable> build check DIVIDE-1`,
`sh <plugin>/bin/wuwei state get`, a relative path to the launcher). Reproduced on `main`
by calling the guards in process against the dry-run workspace:

- commit/push: exit 2, "command substitution is unsupported"
- deploy: exit 2, "opaque script deployment command"
- PR: exit 2, "opaque script command"

A two-line script containing only `x=$(pwd)` is denied with the same three reasons.

Root cause. Issue #18 added `script_path` and `script_text` in `cli/wuwei/shell.py`
(lines 109 to 141), which read a script named as `argv[0]` (or as `sh <file>`). The three
Bash guards decide whether that script text concerns them with `shell.mentions`
(`cli/wuwei/guards/commit_push.py` line 251, `cli/wuwei/guards/deploy.py` line 263,
`cli/wuwei/guards/pr.py` lines 339 to 340). `mentions` (`cli/wuwei/shell.py` lines 85 to
106) is the conservative relevance check for command text: it answers True for any text
that still holds a command substitution after flattening (line 99, true for the launcher's
nested `$(... "$(dirname ...)" ...)`) and for any non-literal command word (line 105, true
for `x=$(pwd)`). Every script with a substitution is therefore "relevant" to every guard,
then fails to parse or is refused as opaque. Relevance is never actually decided for
script text, and the launcher is not recognised as the wuwei CLI.

Owner-only actions through the launcher path are already refused by
`cli/wuwei/guards/protect_state.py` (`_wuwei_action` line 33 and the mcp/drafts check at
line 335 match any `argv[0]` named `wuwei`); this must stay so.

## User Scenarios & Testing

### User Story 1 - Seats call the WUWEI CLI by its launcher path (Priority: P1)

A seat or the owner runs the plugin's launcher by absolute path, by the path recorded in
`.wuwei/executable`, or as `wuwei` on PATH, from the workspace root or an item worktree.
The call runs; no guard refuses it as an opaque script.

**Independent Test**: pipe PreToolUse Bash payloads through the hook command in process
from a seeded workspace and from `worktrees/ITEM-1` inside it; assert exit 0.

**Acceptance Scenarios**:

1. Given a session inside a workspace, when Bash runs `<plugin>/bin/wuwei state get`, then PreToolUse exits 0.
2. Given a session inside a workspace whose `.wuwei/executable` records another install's launcher, when Bash runs that recorded path with `build check <item>`, then PreToolUse exits 0.
3. Given a session inside a workspace, when Bash runs `wuwei state get` with a PATH `wuwei`, then PreToolUse exits 0.
4. Each of the above holds with the session cwd at the workspace root and at an item worktree.

### User Story 2 - Irrelevant scripts run, relevant ones stay refused (Priority: P1)

A script whose text has no token that concerns a guard passes that guard even when the
normaliser cannot parse it. A script that invokes a guarded action is still refused.

**Acceptance Scenarios**:

1. Given a script whose whole text is `x=$(pwd)`, when Bash runs it inside a workspace, then PreToolUse exits 0.
2. Given a script whose text runs `git push --force origin main`, when Bash runs it inside a workspace, then PreToolUse refuses it.
3. Given a strict-mode script (`set -euo pipefail`, `IFS=$'\n\t'`, `python3 -m pytest -q`) with no git, gh or deploy token, when Bash runs it inside a workspace, then PreToolUse exits 0.

### User Story 3 - Owner actions through the launcher stay refused (Priority: P1)

**Acceptance Scenarios**:

1. Given `<plugin>/bin/wuwei decision outcome D-1 A`, when Bash runs it inside a workspace, then PreToolUse refuses it as an owner action.
2. The same holds for `<plugin>/bin/wuwei drafts approve <id>`, `<plugin>/bin/wuwei mcp decide` and `<plugin>/bin/wuwei integrity reconfirm`.
3. Given an agent tool that writes `.wuwei/executable` (Write, or a Bash redirection), then it is refused, so the recorded launcher cannot be repointed at an arbitrary script.

## Edge Cases

- A copy of the launcher at a path that is neither the plugin's own `bin/wuwei` nor the recorded executable is inspected as an ordinary script (its text concerns no guard, so it passes).
- A missing, unreadable or invalid `.wuwei/executable` means only the plugin's own launcher is recognised; nothing fails open.
- `sh <launcher> ...` is recognised as the launcher, the same as calling it directly.
- Outside any workspace nothing changes: guards return 0 as before.
- Command text (not script text) keeps the conservative `mentions` check: `python3 -m pytest -q`, a `for` loop and `export X=1` pass as before; `x=$(pwd) && git push` is still relevant.

## Requirements

### Functional Requirements

- **FR-001**: A script named as a command is read only to decide relevance; its text concerns a guard only when it contains a literal token for that guard (after quote and backslash removal).
- **FR-002**: A script not relevant to a guard is allowed by that guard, whatever constructs it contains.
- **FR-003**: A relevant script that cannot be parsed or inspected still fails closed (exit 2), and a relevant script with a refused action is refused.
- **FR-004**: The plugin's own `bin/wuwei` and the path recorded in `.wuwei/executable` (resolved) are the wuwei CLI, never a script to inspect, for every guard that reads scripts.
- **FR-005**: `decision outcome`, `drafts approve`, `mcp decide` and `integrity reconfirm` through any launcher path stay refused.
- **FR-006**: `.wuwei/executable` is a protected workspace file: agent tools cannot write, move or delete it.

## Success Criteria

- The three acceptance commands exit 0 through PreToolUse from the workspace root and from an item worktree.
- A force-push script and the four owner actions through the launcher path are refused.
- No existing guard table test changes its expected exit code.
- Tests need no network and no real git or gh.

## Assumptions

- "Tokens that concern a guard" means the name sets each guard already passes to `mentions` for scripts (commit/push: git or gh plus its verbs; deploy: protected programs plus deploy actions; PR: gh plus its verbs). No new token lists are added.
- Script text is judged by literal tokens, not by the conservative command-text rules. A script that constructs a guarded name dynamically (for example `g=gi; ${g}t push`) is not relevant; this is the residual already accepted in `shell.is_opaque` and is covered for pushes by the worktree pre-push hook (spec 4.5) and for gh merges by server-side branch protection (spec 9.1). A name hidden in ANSI-C quoting (`$'\x67it' push`) is the same residual; treating `$'` as relevant would refuse every strict-mode script that sets `IFS=$'\n\t'`.
- "A `wuwei` on PATH resolving to either" needs no code: a bare command name is never read as a script (`script_path` requires a slash, `.sh` or a shell), and `protect_state` already treats any `argv[0]` named `wuwei` as the CLI. It gets a test row only.
- Protecting `.wuwei/executable` follows the no-forgeable-trust rule: guards now trust that file, and the git hooks already execute it. `wuwei init` writes it through the CLI, not through agent tools, so it is unaffected.
- An item worktree in tests is a directory inside the workspace (`worktrees/ITEM-1`), as in the dry run; external worktrees resolve the workspace through the existing worktree anchor.
- The acceptance "refused" for the force-push script is satisfied by any deny (exit 1 or 2); on main the commit/push guard answers exit 2 "opaque script command" and that stays.
