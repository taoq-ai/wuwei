# Feature Specification: Opaque commands warn, and a branch push, a PR raise and a local merge are never owner-only

**Feature Branch**: `530-opaque-pr-raise`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #530 part P (owner comments 4 and 6) and all of #534: under observe
and guarded an opaque Bash command is a warning, not a refusal, unless its literal text names
a publish target; a branch push and a PR raise are gated by evidence, never by the owner; a
local git merge is never refused below strict; `gh pr create` and `bin/wuwei pr raise` work
from any directory when they name a recorded item branch or worktree; the generated guide
names `pr state` and `pr ping-check`.

## Root cause

- `cli/wuwei/guards/__init__.py:46`: `OWNER_ONLY` holds the whole `pr` module, so
  `guards.level` (`:56-69`) blocks every `pr` guard refusal in every posture. That includes
  the PR raise refusals of `pr.create_check` (`cli/wuwei/guards/pr.py:191-212`): missing gate
  verdicts, the missing `--reviewer`, `--repo` and `--head`. Raising a PR is therefore
  owner-only in practice, which the owner reported as "can't create PRs".
- `cli/wuwei/commands/hook.py:268-273` (`posture`) levels by reason only `UNPARSED`,
  `WORKSPACE_ROOT` and the deploy guard's unknown git subcommand. A Bash call the guards
  cannot read reaches them as a different exit 2: `PR guard could not run: opaque script
  command` (`pr.py:390-391`), `opaque command` (`pr.py:397-398`), a re-raised `ParseError`
  when a publisher word appears (`pr.py:388`, `shell.unread` returns None for any `gh`
  word), `deploy: could not inspect: opaque ...` (`deploy.py:303-304`, `:322-323`), and
  `commit/push guard could not run: opaque ...` (`commit_push.py:362-363`, `:379-383`). Those
  are levelled by area: `pr` and `deploy` are owner-only (block everywhere), `commit_push`
  is `publish` (block under guarded). A per-PR loop that reads review comments with a
  script, a `$(...)` or `python -c` is refused in every posture.
- `cli/wuwei/guards/pr.py:197-200` refuses `--repo` and `--head` outright, and
  `pr.py:313-314` refuses any compound call (`isolated` is false), so `cd <worktree> && gh
  pr create` fails. The guard resolves the repository and HEAD from the hook's cwd only.
- `cli/wuwei/guards/deploy.py:133-135`: `git merge` raises `current branch cannot be
  established by the vcs port`, exit 2, owner-only, so a local merge (main into an item
  branch) is refused in every posture.
- `cli/wuwei/guards/commit_push.py:137-151`: the fast-check evidence check sits inside
  `push_check`, which the native pre-push hook also runs (`cli/wuwei/commands/git_hook.py:94`)
  and which refuses in every posture. Under observe the tool hook warns about a push without
  evidence and then git's own pre-push hook refuses it.
- `cli/wuwei/shepherd.py:306-309`: `pr raise` prints a gate miss and exits 1 in every
  posture; no card is offered and observe does not warn.
- `cli/wuwei/guide.py:58-66`: the generated guide does not name the commands that read
  review comments and the reviewer list.

## User Scenarios and Testing

### User Story 1: an opaque read is a warning (Priority: P1)

The planner runs a loop that reads new review comments and the reviewer list. The guards
cannot read it; under observe and guarded it runs and leaves one warning.

**Independent Test**: the hook in process (`tests/test_parser_warns.py` harness) on a neutral
workspace, one call per form and posture.

**Acceptance Scenarios**:

1. **Given** observe or guarded, **When** the planner runs `bash loop.sh` (a script that runs
   `gh api repos/o/r/pulls/7/comments`), a `$(...)` read (`gh pr view $(git rev-parse
   --abbrev-ref HEAD)`), or a `python3 -c` that prints `gh pr view 7` output, **Then** the
   hook exits 0 and exactly one `guard.would_refuse` event is written whose reason starts
   with `opaque:` and names what could not be read (the script name, the construct the parser
   stopped at, or the interpreter).
2. **Given** strict, **When** the same commands run, **Then** each is refused as today and no
   `guard.would_refuse` event is written.
3. **Given** any posture, **When** an opaque command's literal text names a protected-branch
   push (`git push origin main` inside a script or a substitution), a force, tag or
   `--no-verify` push, a deploy (`kubectl apply` in a script, a workflow dispatch), a release
   (`gh release create`), a PR merge (`gh pr merge`), or an owner-only or outward `gh`
   action (an approval, `--admin`, a protection or alias change, a comment or a create),
   **Then** it is refused as today.
4. **Given** any posture, **When** an opaque command writes into `.wuwei/` (for example
   `python3 -c 'open(".wuwei/days/<d>/state.json","w")'`), **Then** it is refused (records
   floor). Not claimed for a script file: `bash s.sh`, where `s.sh` writes into `.wuwei/`,
   passes below strict on main as well; this predates #530 and is a follow-up.

### User Story 2: push and PR raise are gated by evidence, never by the owner (Priority: P1)

**Independent Test**: guard calls in process with the fakes of `tests/test_commit_push.py`,
`tests/test_pr_guards.py` and `tests/test_shepherd.py`; hook levelling with stub guards in
`tests/test_posture.py`.

**Acceptance Scenarios**:

1. **Given** observe or guarded and fast checks recorded at HEAD, **When** the builder runs
   `git push origin HEAD:refs/heads/<branch>` in its worktree, or the planner runs `git -C
   <recorded worktree> push origin HEAD:refs/heads/<branch>` from the workspace root,
   **Then** the push passes the hook and the native pre-push hook.
2. **Given** gate verdicts PASS at HEAD and a named reviewer, **When** the builder runs `gh
   pr create -r alice` in its worktree, or the planner runs `bin/wuwei pr raise`, **Then**
   it passes in observe and guarded.
3. **Given** observe and no fast-check evidence (or no gate verdicts), **When** the push or
   the PR raise runs, **Then** it proceeds; the tool hook records one `guard.would_refuse`
   naming the missing check, `pr raise` prints the same warning and records it, and the
   native pre-push hook prints a warning and exits 0.
4. **Given** guarded and missing evidence, **When** the push or the PR raise runs, **Then**
   it is refused with a reason that starts `publish:`, names the check to run (`bin/wuwei
   build check <item>` or the missing gates), points at a decision card, and never asks for
   a host terminal; the card offers `Defer until the check passes` (recommended), `Allow once` and
   `Allow today`, and no `Always allow`.
5. **Given** guarded and the owner answered that card `Allow once` or `Allow today`, **When**
   the same push or PR raise runs again, **Then** it passes and a `grant.used` event is
   written; a once grant is spent.
6. **Given** strict and missing evidence, **When** the push or the PR raise runs, **Then** it
   is refused with today's reason and a `posture: publish = block` line; no card is written.
7. **Given** any posture, **When** a seat raises a PR, **Then** the merge policy, approvals,
   admin merges and branch protection changes stay owner-only (unchanged).

### User Story 3: PR raise and push from any directory (#534) (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a recorded item branch with gate verdicts PASS at its worktree HEAD and the
   planner in the workspace root, **When** it runs `gh pr create -R <org>/<name> --head
   <branch> -r alice`, **Then** the PR guard passes; **When** it runs `cd <recorded
   worktree> && gh pr create -r alice`, **Then** the PR guard passes.
2. **Given** the same branch without gate verdicts, **When** either command runs, **Then**
   the reason names the branch and the missing gates, never a directory.
3. **Given** `--head` of a branch no item records, **When** `gh pr create -R <org>/<name>
   --head other -r alice` runs, **Then** it is refused with the reason `head other is not a
   recorded item branch of <org>/<name>`.
4. **Given** `-R` of a repository that is not configured, **Then** it is refused naming the
   repository.
5. **Given** `cd <unrecorded path> && gh pr create` or `cd <unrecorded path> && git push
   ...`, **Then** the guards return today's refusal.
6. **Given** a recorded item worktree, **When** the planner runs `cd <worktree> && git push
   origin HEAD:refs/heads/<branch>` or `git -C <worktree> push origin
   HEAD:refs/heads/<branch>` with evidence, **Then** the push guards pass.

### User Story 4: a local merge is never owner-only (Priority: P2)

**Acceptance Scenarios**:

1. **Given** observe, guarded or strict, **When** the builder runs `git merge main` (or
   `git merge origin/main`) in its item worktree, **Then** the deploy guard returns 0 and the
   hook does not refuse it.
2. **Given** a later `git push origin main`, **Then** the push is refused as today (the
   protected-branch rules are unchanged).

### User Story 5: the guide names the PR read commands (Priority: P3)

**Acceptance Scenarios**:

1. **Given** `wuwei guide`, **Then** it has a line naming `wuwei pr state <ref>` and `wuwei
   pr ping-check <ref>` as the way to read review comments, threads and the reviewer list,
   before writing a loop; `docs/site/agent.md` carries the same text.

### Edge Cases

- A call with a real finding (exit 1) and an opaque could-not-run (exit 2): the finding is
  enforced as today; the opaque part is still recorded once.
- An opaque call whose `UNPARSED` reason already warns keeps that behaviour and reason
  (#347); the new rule covers the other exit 2 reasons of the publish-area guards. When one
  guard returns `UNPARSED` and another an opaque could-not-run for the same call, one event
  is written in total (whichever comes first).
- Computing what is opaque fails (an unexpected error): nothing is relaxed; the refusal is
  enforced as today.
- `--repo` without `--head`, or `--head` without `--repo`: refused, naming both options.
- The shepherd seat's own rule (a shepherd never runs a command that mentions `merge`) is
  unchanged; a shepherd uses `pr act --run` for a rebase.
- `pr raise` under observe with no gate verdicts raises the PR and records the warning; the
  merge policy still needs PASS verdicts at the head later.

## Requirements

### Functional Requirements

- **FR-001**: Under observe and guarded, the hook MUST let through a Bash call refused only
  with exit 2 by a `publish`-area guard (`commit_push`, `deploy`, `pr`) when the call is
  opaque (a script file, a construct the parser rejects, or interpreter code given inline or
  on stdin) and its literal text, with the script's text, names no publish target. It MUST
  record exactly one `guard.would_refuse` event for the call, reason `opaque: <what>`, level
  `warn`, area `publish`.
- **FR-002**: The literal text (the command plus a script's text) names a publish target or
  an owner-only action when it names: a deploy program, `deploy`, `deployments` or a
  `deploy.deny` program; `release` or `releases`; `gh` together with one of `merge`,
  `approve`, `APPROVE`, `admin`, `review`, `protection`, `rulesets`, `alias`, `secret`,
  `workflow`, `dispatches`, `rerun`, `environments`, `refs`, `comment`, `create`, `edit`;
  `push` together with a force, mirror, tag or `--no-verify` form, a version-like word, or a
  word naming `main`, `master`, a configured default branch or a branch matching
  `environments`; `hooksPath` (any case) or `wuwei-workspace`. Such a call keeps today's
  levelling, so it is refused where today it is.
- **FR-003**: Under strict, and for every records-area refusal in every posture, the hook
  MUST enforce as today.
- **FR-004**: The `pr` guard's PR create refusals and the missing-reviewer refusal MUST be
  levelled as the `publish` area, not as owner-only; every other `pr` refusal (merge policy,
  approvals, admin merge, protection and alias changes, API pushes to protected branches,
  the shepherd rule) stays owner-only.
- **FR-005**: A push whose fast checks have not passed at HEAD, and a PR raise (`gh pr
  create`, `bin/wuwei pr raise`) whose gate verdicts have not passed at HEAD, MUST: under a
  posture where `publish` warns, proceed with the warning; under guarded (publish blocks,
  not strict), refuse once with the owner's card naming the check, and pass on an active
  `once` or `today` answer; under strict, refuse with the reason.
- **FR-006**: The evidence card MUST reuse the #478 grant card and rows with the action class
  `evidence`, options `keep` (titled `Defer until the check passes`, recommended), `once`, `today`,
  no `always`; no text on that path names a host terminal.
- **FR-007**: The native pre-push hook MUST refuse a fast-check evidence miss only under
  strict; below strict it prints the reason as a warning and exits 0. Identity, force,
  default-branch, environment-branch and non-fast-forward refusals are unchanged.
- **FR-008**: `gh pr create` MUST accept `-R/--repo <org>/<name>` with `-H/--head <branch>`
  from any cwd in the workspace when the repository is configured and the branch is the
  branch of a recorded item worktree in that repository; evidence is read at that worktree's
  HEAD for that item. `cd <recorded item worktree> && gh pr create ...` (exactly two
  commands joined by `&&`) MUST be checked as `gh pr create` run in that worktree.
- **FR-009**: The deploy guard MUST return 0 for a local `git merge`.
- **FR-010**: The generated guide MUST name `pr state` and `pr ping-check` for reading
  review comments and the reviewer list.
- **FR-011**: No new refusal under observe or guarded beyond FR-002's publish targets, which
  are already refused today.

## Success Criteria

- **SC-001**: each acceptance scenario above is a test on neutral fixtures and passes.
- **SC-002**: the full suite passes; existing tests change expectations only where this spec
  changes behaviour (listed in the plan).

## Assumptions

- "A card under guarded" is the #478 grant card (the notes say reuse the card and grant flow
  of #478/#506). A new action class `evidence` keeps an evidence answer from ever lifting a
  deploy, release or `deploy.deny` publish on the same repository. No `Always allow`: the
  standing-grant schema stays deploy, release and publish only; an owner who never wants the
  check picks observe.
- The card's `keep` answer means "run the check first"; the refusal then names the check.
- `main` and `master` count as protected branch names in opaque text even when no repository
  is configured, so an unconfigured workspace does not relax an opaque push to them.
- A PR merge (`gh` with `merge`) counts as a publish target in opaque text: it lands on the
  protected base branch. A local `git merge` does not.
- The owner-only floors (approvals, admin merges, protection and alias changes) and the
  outward floor (canary and honeytoken egress through a `gh` text write) are refused today
  for opaque `gh` text only because the `pr` guard is owner-only; FR-002's `gh` words keep
  them refused, so relaxing opaque reads never relaxes a floor. Likewise a `--no-verify`
  push, a `hooksPath` change and a removed `wuwei-workspace` pointer would disable the
  pre-push anchor that makes relaxing opaque feature pushes safe, so they stay refused.
- Below strict, a seat can reach a feature-branch push or a PR raise without the evidence
  card by wrapping it in a script (an opaque call warns). That is the owner's rule (opaque is
  a warning unless it names a publish target); the guards are cooperative (spec 9.1), the
  warning is recorded, protected branches stay anchored by the pre-push hook and the code
  host, and strict refuses both.
- `--repo` and `--head` go together; one without the other is refused (exit 2) naming both.
- A recorded item branch is the branch the vcs port reads in a worktree recorded in
  `items.<item>.worktree`; no new state is added.
- `cd <worktree> && git push` and `git -C <worktree> push` already pass the push guards on
  main; this feature pins them with tests and changes code only if a test is red.
- `pr raise` already resolves the workspace and the recorded worktree from any cwd inside the
  workspace; only its evidence handling changes.
- Inline interpreter code that names a deploy program without `git` or `gh` is not seen by
  the deploy guard today; that stays (spec 4.5: `permissions.deny` and credentials are the
  anchors). Adding it would add refusals under observe.
- The missing-reviewer refusal is levelled as `publish` (warn under observe, block under
  guarded and strict) and still names its own ways out; turning it into a card is part B's
  sweep.
- `tests/test_invariants.py` is not on this branch's base; part B adds the invariants "a
  branch push and a PR raise with recorded evidence succeed below strict" and "under observe
  and guarded no opaque read-only command is refused" to the design table and that test.
- Design spec 4.1, 4.5 and 9.1 get the minimal amendments that keep them true; part B
  rewrites the posture table.
