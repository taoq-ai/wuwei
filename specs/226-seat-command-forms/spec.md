# Feature Specification: Ordinary seat command forms pass the commit, deploy and PR guards

**Feature Branch**: `226-seat-command-forms`
**Created**: 2026-09-30
**Status**: Ready
**Input**: GitHub issue #226, "fix(guards): ordinary seat command forms pass the commit, deploy and PR guards"

## Problem (reproduced)

The v0.6.0 operator dry run ran a developer-command matrix through `bin/wuwei hook
PreToolUse` from the workspace root and from the item worktree. Reproduced on `main`
(v0.6.0 plus #224) against the dry-run workspace, both through the hook and by calling each
Bash guard in process to attribute every refusal:

| Command | Where | Refused by (today) |
|---|---|---|
| `git commit -qm "wip"`, `git commit -sm "wip"` | worktree | commit/push: exit 2, "unsupported commit option" |
| `git commit -m "wip"` (any form) | workspace root | commit/push: exit 2, "git.commit_context: could not run: git exited 128" |
| `x=$(pwd); echo $x` | both | commit/push, deploy and PR: exit 2, "command substitution is unsupported" |
| `python3 -m pytest -q && git status` | both | deploy: exit 2, "opaque deployment command" |
| `cd $(git rev-parse --show-toplevel) && ls` | both | protect_state (cd containment) only: exit 2, "command substitution is unsupported; run git or gh as a plain command" |
| `git push $(cat remote) main` | both | commit/push, deploy and PR: exit 2 (must stay refused) |

Root causes, with file and line on `main`:

1. Combined short options. `commit_options` in `cli/wuwei/guards/commit_push.py` (lines 205
   to 207) splits a short-option bundle only when it starts with `-a`. `-qm`, `-sm`, `-vm`
   fall through to line 237 and raise "unsupported commit option". `-am` works only because
   of that special case.
2. Assignment words counted as command names. `mentions` in `cli/wuwei/shell.py` (lines 113
   to 114) ends with a scan that answers True for any non-literal word at a command position.
   The first word of `x=$(pwd)` (flattened to `x=$substitution`) is an assignment, not a
   command name, but the scan treats it as one. So `x=$(pwd); echo $x` is "relevant" to
   every guard that asks (commit/push line 279, deploy lines 265 and 270, PR line 335), and
   each then fails on `shell.normalize`, which rejects any substitution (shell.py line 238).
   The existing test `tests/test_shell.py::test_command_mentions_still_counts_substitutions`
   (added by #205) pins exactly this over-report: `mentions('x=$(pwd)', {'git', 'gh'}) is True`.
3. Whole-list relevance for opaque interpreters. `cli/wuwei/guards/deploy.py` line 277
   refuses any command in the list where `is_opaque(argv)` holds and the whole raw text
   mentions git or gh. `is_opaque` (`cli/wuwei/shell.py` line 567) flags every interpreter
   that has neither a snippet nor a leading path, including `python3 -m pytest -q`, because
   such an interpreter might read its program from standard input. In `python3 -m pytest -q
   && git status` the git mention belongs to another command and nothing feeds python's
   standard input, yet the list is refused. `cli/wuwei/guards/pr.py` line 376 has the same
   shape (`python3 -m pytest -q && gh pr view 1` is refused). The refusal text does not name
   the command it objects to.
4. Git's reason is dropped. `_run` in `adapters/vcs/git.py` (lines 176 to 177) turns every
   failing read into "git exited <code>". From the workspace root, which is not a Git
   repository, `commit_context` fails with 128 and the seat never learns why. Git's stderr
   is deliberately not copied into the reason (`tests/test_vcs.py::test_git_exit_is_explained`
   keeps private stderr text out), so the fix maps the one known condition to a fixed message.

Correction to the issue. The issue attributes the `cd $(git rev-parse --show-toplevel) &&
ls` refusal to the commit, deploy and PR guards. On `main` those three guards already return
0 for it (the substitution body is a read-only git query, and none of them treats it as
relevant). The only refusal comes from the top-level cd containment rule of spec 4.1 ("top-level
`cd` out of the workspace: always"), in `cli/wuwei/guards/protect_state.py` line 308: inside a
workspace, a `cd` whose target cannot be resolved statically is refused. That refusal is
correct and stays: from the workspace root, which is not a repository, the substitution is
empty and the bare `cd` goes to HOME, which moves the persistent session cwd out of the
workspace and silently takes every later call out of guard scope (spec 9.1). What is wrong is
its message, which tells the seat to "run git or gh as a plain command" and names no guard.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ordinary commit forms pass (Priority: P1)

A builder seat commits with the short forms it uses every day: `git commit -qm "wip"`,
`git commit -sm "wip"`, `git commit -qam "wip"`. The commit/push guard reads the bundle as
its separate options and applies the same identity and hook policy as for the spelled-out
form.

**Why this priority**: the dry run refused the builder's first commit attempt; every
refused ordinary form costs a seat turn and teaches seats to route around the guard.

**Independent Test**: in-process commit/push table with the fake VCS port.

**Acceptance Scenarios**:

1. Given a session in a configured repository inside a workspace, when Bash runs `git commit -qm "wip"`, `git commit -sm "wip"`, `git commit -qam "wip"` or `git commit -vqm "wip"`, then the commit/push guard returns 0.
2. Given the same session, when Bash runs `git commit -qn -m x` or `git commit -nm x`, then the guard returns 1, "disabling commit hooks is refused" (a bundle cannot hide `-n`).
3. Given the same session, when Bash runs `git commit -qC HEAD`, then the guard returns 2 (reused authors still need `--reset-author`); an unknown letter in a bundle (`git commit -qZ`) still returns 2, "unsupported commit option".

### User Story 2 - A list is judged per command (Priority: P1)

A seat runs `python3 -m pytest -q && git status`. The deploy guard (and the PR guard for
the gh equivalent) decides relevance per command: an interpreter whose own words name no git
or gh and whose standard input is not fed by another command in the list is not a hidden
deployment. A refusal names the guard and the command it objects to.

**Why this priority**: running tests and then looking at the tree is the most common seat
list; the dry run refused it from both locations.

**Independent Test**: in-process deploy and PR tables.

**Acceptance Scenarios**:

1. Given a session inside a workspace, when Bash runs `python3 -m pytest -q && git status` or `python3 -m pytest -q; git status`, then the deploy guard returns 0.
2. Given a session inside a workspace, when Bash runs `python3 -m pytest -q && gh pr view 1`, then the PR guard returns 0.
3. Given a session inside a workspace, when Bash runs `git status | python3`, then the deploy guard returns 2 and the message contains `deploy` and `python3`.
4. Given a session inside a workspace, when Bash runs `gh pr view 1 | python3`, then the PR guard returns 2 and the message contains `PR guard` and `python3`.
5. Given a session in a configured repository, when Bash runs `python3 -m pytest -q && git commit -m x`, then the commit/push guard still returns 2 and the message now contains `python3 -m pytest -q`.

### User Story 3 - Substitution is refused only where it matters (Priority: P1)

A seat uses `x=$(pwd); echo $x`. No guard refuses it: an assignment is not a command name
and nothing in the text concerns git, gh or a deploy tool. A substitution that feeds or
surrounds a guarded command still fails closed.

**Why this priority**: shell variables from substitutions are ordinary; the dry run refused
the form three times over.

**Independent Test**: `shell.mentions` table plus rows in each guard table.

**Acceptance Scenarios**:

1. Given a session inside a workspace, when Bash runs `x=$(pwd); echo $x` or `x="$(pwd)"; echo "$x"`, then the commit/push, deploy and PR guards each return 0.
2. Given a session inside a workspace, when Bash runs `cd $(git rev-parse --show-toplevel) && ls`, then the commit/push, deploy and PR guards each return 0.
3. Given a session inside a workspace, when Bash runs `git push $(cat remote) main`, then the commit/push and deploy guards return 2, each message naming its guard.
4. Given a session inside a workspace, when Bash runs `echo $(git push origin main)`, `x=$(pwd); $x push` or `a=gi; x=$(pwd) ${a}t push`, then the commit/push and deploy guards return 2.
5. Given a session inside a workspace, when Bash runs `gh pr create $(echo x)`, then the PR guard returns 2.

### User Story 4 - A commit outside a repository says why (Priority: P2)

A seat runs `git commit -m "wip"` from the workspace root, which is not a Git repository.
The commit/push guard still fails closed, and the reason says "not a git repository".

**Independent Test**: the VCS adapter with a replayed git failure.

**Acceptance Scenarios**:

1. Given git fails with exit 128 and stderr "fatal: not a git repository (or any of the parent directories): .git", when the VCS adapter runs a read, then the result is exit 2 with a reason containing "not a git repository" and not "git exited 128".
2. Given any other git failure, then the reason stays "git exited <code>" and never contains git's stderr text.
3. Given a session at a workspace root that is not a repository, when Bash runs `git commit -m "wip"` through PreToolUse, then the hook denies it (exit 2) with a reason containing "commit/push guard" and "not a git repository".

### User Story 5 - Acceptance through PreToolUse (Priority: P1)

Each form above, through the hook command in process, from the workspace root and from an
item worktree inside it, gets the stated exit, and every refusal names the guard and the
offending command.

**Acceptance Scenarios**:

1. Given a workspace, when PreToolUse runs `x=$(pwd); echo $x` or `python3 -m pytest -q && git status` from the root or from `worktrees/ITEM-1`, then it exits 0.
2. Given a workspace, when PreToolUse runs `git push $(cat remote) main`, then it exits 2 and the deny reason contains `commit/push guard` and `deploy`.
3. Given a workspace, when PreToolUse runs `git status | python3`, then it exits 2 and the reason contains `deploy` and `python3`.
4. Given a workspace, when PreToolUse runs `cd $(git rev-parse --show-toplevel) && ls`, then it exits 2 with a reason from the workspace cd guard that names the top-level `cd` and does not say "run git or gh" (see the correction above).
5. Given the spec 4.5 bypass forms, then every existing refusal in the guard table tests is unchanged and the #18 mutation tests (`tests/test_guard_mutation.py`) still go red.

### Edge Cases

- An assignment followed by a non-literal command word (`x=$(pwd) $cmd`, `x=1; $x push`) stays relevant; only the assignment word itself stops counting as a command name.
- A substitution body is still checked on its own: `x=$(git rev-parse HEAD)` mentions git, so guards that care about git still see it; `mentions(..., script=True)` is unchanged.
- Any git or gh mention together with any expansion (`git push "$REMOTE"`, `git push $(cat remote) main`) stays relevant (shell.py line 111); this is why the PR guard keeps refusing `git push $(cat remote) main`: a git argument list read at run time can define an alias that runs gh.
- An interpreter whose input comes from a pipe in the list (`git show HEAD:d.py | python3`) or from an input redirection (`python3 < d.py && git status`) is still refused by the deploy guard when the list mentions git or gh, and by the PR guard.
- An interpreter with a snippet or argv that names git or gh (`python3 -c "... git push ..."`, `xargs git push`) is refused exactly as before.
- Outside a workspace nothing changes: every guard returns 0.
- A bundle containing `-n` is refused as disabling hooks; a bundle ending in a value option (`-qm msg`, `-qmmsg`) reads the value like the spelled-out option.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The commit/push guard reads a short-option bundle whose leading letters are no-value commit flags (`a`, `e`, `n`, `q`, `s`, `v`) as those flags followed by the rest of the bundle, applying the existing policy to each.
- **FR-002**: `shell.mentions` (command text) does not treat a leading `NAME=value` assignment word as a command name; the first word after the assignments is the command word checked for literalness.
- **FR-003**: `shell.is_opaque` takes whether the command's standard input is fed by the list; when it is not, an interpreter without a snippet and without a leading path is not opaque. All other opaque cases are unchanged, and the default keeps today's behaviour for every other caller.
- **FR-004**: The deploy and PR guards pass that fact per command (fed when the previous command in the list ends with `|` or the command has an input redirection) and name the offending command in the refusal.
- **FR-005**: The commit/push guard's refusal of a non-git command in a commit or push list names that command; the decision itself is unchanged.
- **FR-006**: The VCS adapter reports "not a git repository" when git says so, and keeps "git exited <code>" without stderr text for every other failure.
- **FR-007**: The workspace cd containment refusal for a statically unresolvable top-level `cd`, `pushd` or `popd` names the guard and the directory change and gives the working alternative (a literal directory inside the workspace, or `git -C`); its decisions are unchanged.
- **FR-008**: The shell normaliser grammar is unchanged: substitutions still raise `ParseError`, so a relevant command with a substitution still fails closed.

### Key Entities

- **Command** (`cli/wuwei/shell.py`): normalised argv with `separator` (the operator after it) and `reads` (input redirections). Both already exist; they decide whether standard input is fed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The six dry-run rows above produce the stated exits through PreToolUse from the workspace root and from an item worktree.
- **SC-002**: No existing guard table row in `tests/test_commit_push.py`, `tests/test_deploy.py`, `tests/test_pr_guards.py`, `tests/test_protect_state.py` or `tests/test_shell.py` changes its expected exit code; the one intended reversal is `test_command_mentions_still_counts_substitutions` (`x=$(pwd)` is no longer relevant).
- **SC-003**: `tests/test_guard_mutation.py` passes unchanged.
- **SC-004**: The full suite passes with no network and no real git or gh.

## Assumptions

- The issue's `cd $(git rev-parse --show-toplevel) && ls` example is corrected as described under Problem: the three named guards pass it (tested), and the spec 4.1 cd containment rule keeps refusing it with a clearer message. Loosening cd containment would need a static model of `git rev-parse` (it fails outside a repository and the bare `cd` then leaves the workspace) and is not asked for by this issue.
- "Each guard decides relevance per command" applies to the opaque-interpreter check in the deploy and PR guards. The commit/push guard keeps refusing any non-git command in a list that commits or pushes: it measures identity and hook configuration before the list runs, and an earlier command in the same list could change them. Only its message changes.
- An interpreter fed by an input redirection or a pipe stays opaque, so nothing is loosened beyond the unfed interpreter case the issue names.
- Git's "not a git repository" text is matched in English. Under a translated Git locale the reason falls back to "git exited 128", which still fails closed.
- `for f in *.py; do ...; done && git status` stays refused by the commit/push, deploy and PR guards (a git mention plus an expansion); the issue does not list it.
- No new config keys, so the template and `docs/site/configuration.md` are unchanged.
