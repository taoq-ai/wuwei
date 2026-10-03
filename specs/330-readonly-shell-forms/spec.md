# Feature Specification: read-only shell forms are not refused for being uninspectable, and shadow mode records them

**Feature Branch**: `330-readonly-shell-forms`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #330, "fix(guards): read-only shell forms are not refused for being
uninspectable, and shadow mode records them". Evidence: the owner's first-run trial of
v0.11.0 on Claude Code (2026-10-03), defect B9. Main is 4a384c5 (v0.11.0 plus #325).

## Root cause (read and reproduced on main)

Reproduction (read-only, in a throwaway workspace under the session scratchpad; the item
names no dry-run workspace): a workspace with seeded integrity evidence and an empty
`config.toml` (enforce), then the same with `[guards] mode = "shadow"`. Each form was piped
through `wuwei hook PreToolUse` in process and each Bash guard was also called directly.

| Form | Enforce | Refused by |
|---|---|---|
| `for r in a b; do git -C $r remote get-url origin; done` | 2 | commit_push, deploy, pr: "dynamic command or shell control flow is unsupported" |
| `git -C "$(cat repo.txt)" log -1 \| head -5` | 2 | commit_push, deploy, pr: "command substitution is unsupported" |
| `git -C repo symbolic-ref refs/remotes/origin/HEAD` | 2 | deploy: "unknown git command or alias" (also `describe`, `show-ref`) |
| `python3 -m pytest -q`, `export X=1`, `for f in *.py; do wc -l $f; done` | 0 | none |

In shadow mode the first form recorded one `guard.would_refuse` (commit_push) and still
exited 2, because deploy and pr refused too and both are in `guards.NEVER_SHADOWED`.

Four code facts produce this:

1. `cli/wuwei/shell.py:111-112`, inside the shared relevance helper `mentions`: when the
   text mentions `git` or `gh` and any word anywhere is nonliteral, the text is relevant
   for every name a guard asks about. In the loop, the only nonliteral word is `$r`, the
   value of `git -C`; in the second form it is the substitution (replaced by
   `$substitution` at `shell.py:106`), again the value of `-C`. Neither can be a git verb,
   yet every guard treats the call as one that may reach its effect.
2. Relevant calls are parsed, and `shell.normalize` rejects `for` (`shell.py:422-427`) and
   `$(...)` (`shell.py:239-240`). Each guard then fails closed on the parse error after
   asking `mentions` again, which answers yes for the same reason: deploy at
   `cli/wuwei/guards/deploy.py:269-272`, pr at `cli/wuwei/guards/pr.py:355-360` (the cwd is
   in a workspace), commit_push at `cli/wuwei/guards/commit_push.py:274` (pre-filter) and
   `:281-284` (raises inside a workspace session).
3. `cli/wuwei/guards/deploy.py:132-136`: the deploy guard's known git command set lacks
   `symbolic-ref`, `describe` and `show-ref`, so a parseable read is refused as an unknown
   alias. `rev-parse`, `ls-remote`, `remote` and `config` are already in the set.
4. `cli/wuwei/guards/__init__.py:37` and `cli/wuwei/commands/hook.py:109`: shadow mode
   (#308) records refusals only from modules outside `NEVER_SHADOWED`
   (`protect_state`, `integrity`, `deploy`, `outward`, `pr`). `commit_push` is shadowable.

The trial's second form read `.wuwei/executable` inside the substitution. That form is also
refused by the state guard, `cli/wuwei/guards/protect_state.py:421-426` (an unparseable
command naming `.wuwei`), which this issue leaves unchanged (Assumption A2).

## User Scenarios & Testing

### User Story 1 - Read-only loops and substitutions run in a workspace (Priority: P1)

A planner or seat inspects several repositories with a `for` loop over `git -C $r ...`,
passes a directory computed by `$(...)` to `git -C`, or reads the default branch with
`git symbolic-ref`. None of these can push, merge or deploy, so no guard refuses them.

**Why this priority**: the trial's day could not start without owner round trips for each
such read; it is the reported defect.

**Independent Test**: `python -m pytest -q tests/test_seat_command_forms.py -k issue_330`.

**Acceptance Scenarios**:

1. Given a workspace in enforce mode, when each of these goes through PreToolUse with the
   workspace as cwd, then the hook exits 0 and writes no `hook.refusal`:
   `for r in a b; do git -C $r remote get-url origin; done`,
   `git -C "$(cat repo.txt)" log -1 | head -5`,
   `git -C repo symbolic-ref refs/remotes/origin/HEAD`.
2. Given the deploy guard, when it checks `git symbolic-ref`, `git rev-parse`,
   `git config --get <key>`, `git ls-remote`, `git remote get-url`, `git describe` and
   `git show-ref`, then each returns 0.
3. Given the PR guard, when it checks `for r in a b; do gh -R $r issue list; done`, then it
   returns 0 (no `gh pr`, `gh api` or `gh alias` token).

---

### User Story 2 - Uninspectable forms that can reach a guarded effect still refuse (Priority: P1)

The same shell forms around a push or a merge stay refused, with the reason, and in shadow
mode the shadowable guard records what it would have refused.

**Why this priority**: the relief in US1 must not open a path around the commit and push
policy, the merge policy or the deployment ban.

**Independent Test**: `python -m pytest -q tests/test_seat_command_forms.py -k issue_330`.

**Acceptance Scenarios**:

1. Given enforce mode, when `for r in a b; do git -C $r push origin main; done` or
   `x=$(cat f); gh pr merge $x` goes through PreToolUse, then the hook exits 2 with a deny
   decision.
2. Given shadow mode, when the same two forms go through PreToolUse, then a
   `guard.would_refuse` event with guard `commit_push` is recorded and the hook still exits
   2 with a deny reason from the never-shadowed guards only (`deploy` for the push loop;
   `deploy` and `PR guard` for the merge), with no `commit/push guard` text in the deny
   reason (Assumption A1).
3. Given shadow mode, when `for r in a b; do git -C $r commit -m wip; done` goes through
   PreToolUse (only the shadowable commit/push guard refuses it), then a
   `guard.would_refuse` event with guard `commit_push` is recorded and the hook exits 0.
4. Given the PR guard, when it checks `for r in a b; do gh -R $r pr list; done`,
   `for r in a b; do gh api -X POST repos/$r/x; done` or
   `for a in x; do gh alias set $a "pr merge"; done`, then it returns 2.

---

### User Story 3 - The bypass table and the mutation tests are unchanged (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_shell.py tests/test_deploy.py
tests/test_commit_push.py tests/test_pr_guards.py tests/test_guard_mutation.py
tests/test_seat_command_forms.py`.

**Acceptance Scenarios**:

1. Given every existing row of the spec 4.5 bypass tables (`tests/test_shell.py`,
   `tests/test_deploy.py`, `tests/test_commit_push.py`, `tests/test_pr_guards.py`,
   `tests/test_seat_command_forms.py`) and the #18 mutation tests
   (`tests/test_guard_mutation.py`), then all pass without editing any existing row.
2. Given `mentions` with names `{'push', 'commit'}`, then a git or gh text whose only
   nonliteral words are values of `-C`, `-R`, `--repo`, `--git-dir` or `--work-tree` is not
   relevant, and each of these stays relevant: `git "$VERB" origin main`,
   `git -C $r $VERB`, `git -C "a b" "$VERB" origin main`,
   `git -c "x.y=a;b" "$VERB" origin main`, `git -c $cfg status`, `git log $ref`,
   `git p* -f origin main`, `sh -c 'git $VERB origin main'`, `git status; sh -c "$CMD"`,
   `for r in */; do git -C $r status; done`.

### Edge Cases

- A nonliteral option value that word-splits into a verb at run time
  (`r='. push'; git -C $r origin main`) is not seen. It is the same residual as a name
  built at run time; the pre-push hook in WUWEI worktrees and the protected base branch are
  the anchors (spec 4.5). The code carries a `ponytail:` comment naming it.
- `-c` values are not exempt: `git -c $cfg ...` can inject an identity and `sh -c "$CMD"`
  runs a built script.
- A nonliteral command name (`$x push`, `${TOOL} ${VERB} -f`, `"$(cat bin.txt)" status`)
  stays relevant: the bypass table pins it, and the program cannot be known.
- A loop whose word list is a glob (`for r in */`) stays relevant: the glob is not an
  option value. Literal lists pass.
- Outside a workspace nothing changes: every guard already returns 0 (spec 9.1).
- A `gh api` GET, `gh run list` or `gh release view` inside a loop is still refused by the
  deploy guard, whose effect tokens include `api`, `run` and `release` (Assumption A3).

## Requirements

### Functional Requirements

- **FR-001**: In `shell.mentions`, the constructed-name rule (today: the text mentions git
  or gh and is nonliteral anywhere) ignores a nonliteral word that is the value of `-C`,
  `-R`, `--repo`, `--git-dir` or `--work-tree`: the next word after the flag, or the
  attached forms `-C<value>`, `-R<value>`, `--repo=<value>`, `--git-dir=<value>`,
  `--work-tree=<value>`. Any other nonliteral word in a text that mentions git or gh keeps
  the text relevant for every name, as today. Every other rule of `mentions` is unchanged.
- **FR-002**: `deploy.git` adds `symbolic-ref`, `describe` and `show-ref` to its known git
  command set. Unknown commands and aliases are still refused.
- **FR-003**: The PR guard, on a parse error, returns 0 unless the call runs an opaque
  relevant script (`script_relevant`) or the raw text mentions `pr`, `api` or `alias`
  (through `shell.mentions`); otherwise it keeps today's scope check and fails closed.
- **FR-004**: The commit/push and deploy guards need no change beyond FR-002: with FR-001
  their existing relevance names are the effect tokens (commit/push: the commit verbs,
  `push`, `config`, identity keys and hook pointers; deploy: `DEPLOY_ACTIONS` and the
  `[deploy].deny` programs).
- **FR-005**: `guards.NEVER_SHADOWED`, `hook.shadow` and every `protect_state` rule are
  unchanged.
- **FR-006**: Every hook stays within its `WUWEI_BENCH=1` budget.

### Key Entities

None new. `guard.would_refuse` (#308) is reused as is.

## Success Criteria

- **SC-001**: The issue's acceptance criteria pass as tests: US1-1, US2-1, US2-2 (with the
  A1 reading) and US3-1.
- **SC-002**: The full suite passes: `python -m pytest -q`.

## Assumptions

- A1. Conflict raised: the issue asks for exit 0 in shadow mode for the push loop and the
  merge. Both reach the deploy guard (`push`, `merge`) and the merge reaches the PR guard,
  and both guards are in `NEVER_SHADOWED` by design: constitution VII ("a merge happens
  only through the merge policy; nothing ever deploys"), design spec 4.4 and 4.7, and
  #308 Assumptions A3 and A4. The constitution says the design spec wins and the conflict
  is raised. So the shadow path covers these forms for the shadowable guard (commit_push
  records `guard.would_refuse`) and the hook still exits 2 on the never-shadowed reasons. A
  form only the commit/push guard refuses (a commit loop) records and exits 0. Making
  uninspectable deploy or PR refusals shadowable would shadow the deployment ban and the
  merge policy; that is the owner's call, not this fix.
- A2. The trial's literal second form, `$(cat .wuwei/executable)`, stays refused: the state
  guard refuses any unparseable command naming `.wuwei` (#222, #225, out of scope by the
  issue), and when the substitution is the command name, the nonliteral-command rule that
  the bypass table pins (`$x push`, `${TOOL} ${VERB} -f`, `$DEPLOY apply`) applies. The
  acceptance test therefore uses the substitution as a `-C` value with a neutral file,
  `git -C "$(cat repo.txt)" log -1 | head -5`. Agents run the CLI by its literal launcher
  path.
- A3. Each guard's effect tokens are its existing relevance names (FR-004). The deploy list
  is broader than the issue's list (`api` and `run` of any kind, `release`, `merge`, the
  deploy tool names): it is the never-shadowed deployment ban, so it stays conservative.
- A4. Unknown git commands and aliases stay refused by the deploy guard even without an
  effect token: an alias carries its effect in git config, not in the command text. The
  issue's read-only set (FR-002) covers the trial form.
- A5. `config --get`, `remote get-url`, `rev-parse` and `ls-remote` already pass the deploy
  guard; tests pin them alongside the three additions.
- A6. Test names and fixtures use neutral names (`a`, `b`, `repo`, `repo.txt`, `f`); no
  client, repository or local path from the trial report.
