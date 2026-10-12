# Feature Specification: parallel Codex seats start one at a time, a failed job frees its seat, and a Codex seat carries the retro contract

**Feature Branch**: `871-codex-parallel`
**Created**: 2026-10-12
**Status**: Draft
**Input**: GitHub issue #871: "fix(runtime): parallel Codex seats fail on ~/.codex sqlite init, hide the error and keep holding the seat", with its field comment (a successful Codex opinion refused for a missing `Gap:` and `Change:` line).

## Root cause

- `adapters/runtime/codex.py:52-53` (`dispatch`) and `:186-187` (`continue_job`): each call
  runs `codex-companion.mjs task --background`, which returns at once and starts
  `codex app-server` in a detached worker. Two `wuwei dispatch opinion` runs 0.3 s apart start
  two app-servers at the same moment, and both fail to open the shared state database under
  `~/.codex`. Nothing in WUWEI orders the starts.
- `adapters/runtime/codex.py:97-108` (`status`): the companion's job record carries
  `errorMessage` on a failed job, but `status` returns only `status` and `model`, so
  `cli/wuwei/commands/build.py:592-593` (`wait`) can only say `runtime seat failed`.
- `cli/wuwei/dispatch.py:1319-1356` (`opinion`): the seat is written `running` with its job
  before the wait. When the wait raises, the seat stays `running`, so it holds a host seat, and
  a rerun skips the launch branch (`seat['status'] == 'running'`) and waits on the same failed
  job again. After `seat stop --unmeasured` the seat is `unmeasured`, which the launch branch
  (`seat is None or seat['status'] == 'stopped'`) still skips, so the rerun re-reports the old
  failure (the field comment).
- `cli/wuwei/commands/build.py:620-645` (`run_loop`): the same shape for a Codex builder: the
  build record stays `running` with the failed job, and a rerun polls that job again.
- `adapters/runtime/codex.py:42-46` (`dispatch`): the Codex prompt names the charter, the brief
  and the mandate. `result` (`codex.py:128-131`) runs `guards.verdict.check_retro` on the
  seat's last message, which needs one `Blocked:`, `Gap:` and `Change:` line. A Claude seat
  learns that from its charter and gets the stop hook's refusal to fix it; a Codex seat gets no
  second chance, so a final message without the lines discards a good verdict.

## User Scenarios & Testing

### User Story 1 - Two second opinions in one round both start (Priority: P1)

`wuwei next` returns two `wuwei dispatch opinion` runs; the planner launches both in the
background at once. Both Codex jobs start and finish.

**Independent Test**: two threads call `codex.dispatch` against a fake companion whose job
gets its thread only after a few status polls; the second `task` call happens only after the
first job reports a thread.

**Acceptance Scenarios**:

1. **Given** two Codex dispatches at the same time, **When** the first job has not started its
   thread, **Then** the second `task` call waits; **When** the first reports `threadId` (or
   ends), **Then** the second starts.

### User Story 2 - A failed job frees its seat, names the error and relaunches (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a second-opinion job that fails with `errorMessage`, **When** `dispatch opinion`
   waits on it, **Then** the refusal names the companion's error, and the seat is no longer
   `running`.
2. **Given** that failed seat, **When** the planner reruns `dispatch opinion`, **Then** a new
   job is dispatched (not a continuation, not a poll of the old job).
3. **Given** a seat the planner stopped with `seat stop --unmeasured`, **When** the planner
   reruns `dispatch opinion`, **Then** a new job is dispatched.
4. **Given** a Codex builder whose job fails, **When** `wuwei build <item> <brief> <worktree>`
   waits on it, **Then** it exits 2 naming the error, the build record is `ready` again, and
   the rerun dispatches a new job.

### User Story 3 - A Codex seat ends with the retro note (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a Codex dispatch, **Then** its prompt asks for the `Blocked:`, `Gap:` and
   `Change:` lines in the forms the verdict format defines, rendered from the one table the
   lint and the charters use.

### User Story 4 - A sandboxed Codex seat's work arrives (Priority: P1, live smoke L1 and L2)

The companion runs Codex sandboxed to the worktree (`workspace-write`). The live smoke
showed two results lost to it: a second opinion that reviewed correctly but could not write
`.wuwei/days/<date>/decisions/...`, so WUWEI linted its prose and rejected it; and a Codex
builder whose files stayed uncommitted (the worktree's git metadata lives in the main
repository's `.git/worktrees/<name>`), after which WUWEI marked the build done and sent the
unchanged head to the gates.

**Acceptance Scenarios**:

1. **Given** a Codex gate seat, **Then** its prompt says to write no file outside the
   worktree, that its final message is its whole verdict, and carries the verdict format
   rendered from `verdict.FORMAT` (`verdict.section()`); its brief's `Verdict file:` line says
   WUWEI writes the final message there.
2. **Given** a second opinion the lint rejected, **When** the rerun continues it, **Then** the
   feedback asks for the whole verdict as the final message and WUWEI rewrites the file.
3. **Given** a Codex builder job that completes with changes in the worktree, **Then** WUWEI
   commits them with the repository's configured identity before the fast checks.
4. **Given** a build of any runtime that ends with uncommitted changes, or with HEAD still at
   the head it started from, **Then** the build is not done: the builder gets the reason as
   check feedback and runs again, the item stays out of the gates, and a repeat parks it.

### Edge Cases

- A job that ends while the start lock is held (failed or completed before a thread shows)
  releases the lock at once.
- A companion that never reports `threadId` holds the lock for at most the start bound; the
  next start then goes ahead.
- A timeout (`poll_timeout_seconds`) is not a failure: the job may still run, so the seat
  stays `running` and a rerun keeps polling it, as today.
- A failed delta continuation continues again in the delta round (the initial thread is the
  one to resume); only the initial round dispatches fresh.

## Requirements

### Functional Requirements

- **FR-001**: Every Codex `task` start (dispatch and continuation) holds an exclusive host
  lock (`wuwei-start.lock` in the Codex home: `CODEX_HOME`, else `~/.codex`, the resource
  the starts contend on) from the `task` call until the job reports a thread, ends, or a 60 s
  start bound passes. The wait reuses the status snapshot `_started` already takes, so a job
  that is up or ended costs no extra call.
- **FR-002**: `codex.status` returns the companion's reason as `error`: its `errorMessage`
  (the run threw, as the app-server start did), else a failed job's `summary` (a turn that
  failed inside Codex). `build.wait` puts it in the failure message.
- **FR-003**: When `dispatch opinion` sees its job fail or cancel, the seat becomes `stopped`
  with `failed: <reason>`, and the failure is raised. A rerun in the initial round dispatches a
  fresh job when the seat failed or is `unmeasured`; before relaunching an `unmeasured` seat,
  its old job is read and cancelled when it is still `queued` or `running` (review F3: the
  owner may stop a slow seat, and two jobs must not write one verdict file). The runtime port
  gains `cancel(job)`; Codex wraps the companion's `cancel`, Claude and none refuse.
- **FR-004**: When `wuwei build` sees its Codex job fail or cancel, the build record goes back
  to `ready` with its action, a `build.failed` event records the reason, and the failure is
  raised.
- **FR-005**: The Codex prompt carries the retro-note contract rendered from
  `verdict.FORMAT` for `verdict.RETRO_KEYS`, before the mandate.
- **FR-006** (L1): The Codex prompt says to write no file outside the worktree (temporary
  files under `$TMPDIR` excepted). A gate seat (`sentinel-*`) is told its final message is its
  whole verdict and gets `verdict.section()`, the format the lint reads; a builder gets the
  retro contract. A second-opinion brief's `Verdict file:` line says WUWEI writes the final
  message there. `opinion` already writes the decision file from the job's final message when
  the seat wrote none; the lint-rejection continuation asks for the whole verdict as the final
  message.
- **FR-007** (L2a): After a completed Codex builder job, `build.run_loop` commits every
  worktree change with the configured `repos[].identity` through a new vcs port operation
  `commit_all(repo, item, name, email)` (`git add --all`, then `git commit --quiet -m
  "chore(<item>): Codex builder changes"`, both with `-c user.name` and `-c user.email`). The
  builder prompt says WUWEI commits (role `builder` only; review B6). An unset identity refuses
  with the doctor's fix line; the build stays `running` on its completed job, so the rerun
  commits after the owner sets it. Review B1: a changed or untracked path that matches the
  credential-location rule of the #870 trace check (`scanner._credential_path`: `.ssh`, `.netrc`, `.npmrc`, `.pypirc`, `.git-credentials`, `.gnupg`, `.aws/credentials`, `gh/hosts.yml`, `*.pem`, `*.key`, `.wuwei/env`, `.env` or `.env.*` other than `.example`, `.sample` and `.template`)
  is never committed; redaction keeps its own, broader rule. Review B2: that (a `private`
  failure), or a failed `commit_all` (a rejecting hook, a timeout; a `commit` failure), goes
  back to the builder like a failed check. Review B3: the identity is also passed as `GIT_AUTHOR_*` and
  `GIT_COMMITTER_*`, which outrank `-c user.*`.
- **FR-008** (L2b): Every build record carries `start`, the worktree HEAD when the build (or
  fix round) began. `complete_checks`, the one place a build becomes done for every runtime,
  adds a `dirty` failure when the tree is dirty, a `private` failure when any commit in
  `start..HEAD` touched a path that matches the same credential rule (vcs port `touched`:
  `git log --format= --name-only -z --no-renames <start>..HEAD --`), so a file the builder
  committed itself, or committed and deleted again, is caught too; the push would send those
  commits, so the builder rewrites them locally (`git reset --soft <start>`, remove the file,
  add it to `.gitignore`, commit again), and a `change` failure
  when HEAD equals `start`. A park names its cause: `no change over the start head` (first
  repeat), `private files repeated`, `commit refused repeated`, `uncommitted changes
  repeated`. A failure is check
  feedback: the builder continues with the reason, `stuck_after` repeats park the item, and
  the item never moves to `gate` or `delta` on an unchanged head. Review B5: the unchanged
  head is its own failure (`change`) and parks on its first repeat with the reason `no change
  over the start head`. Review B4: the feedback words fit both runtimes. Review B7: the gate
  prompt and the lint-rejection continuation say the verdict is plain lines, not a code block
  (the lint drops fenced text).

## Success Criteria

- **SC-001**: Two second-opinion gates in one `next` round both start.
- **SC-002**: A forced job failure frees the seat and prints the companion's error.
- **SC-003**: A Codex result whose final message follows the prompt passes `check_retro`.
- **SC-004**: A Codex second opinion's verdict reaches the lint as a verdict, not prose about
  a refused write.
- **SC-005**: A Codex build reaches the gates on a new commit made with the repository
  identity, and no build reaches them on its start head or a dirty tree.

## Assumptions

- The companion runs task workers through an app-server broker per workspace root; two
  workers starting at once both try to start it. Once one start has its thread, the next
  worker finds the broker running.
- The app-server failure is a start race on the shared state database: a single start right
  after succeeded on the same host. Ordering the starts is enough; no retry.
- A thread id in the companion's job index means the app-server initialized (the companion
  patches `threadId` into the index on `turn/started`). This is no documented contract; with
  no thread id the 60 s bound releases the lock.
- The lock lives in the Codex home (review F2), the shared resource, so two workspaces on
  one host serialize too. WUWEI creates that one file (`wuwei-start.lock`) and the directory
  when missing; it is the CLI process's own write, not a seat's, so no guard is involved.
  `flock` is released when a holder dies.
- A failed seat stays a seat record (`stopped`, with `failed`) rather than being removed:
  seat records are never deleted elsewhere, and the next launch replaces the record.
- The retro line is added to the Codex prompt only. Claude seats already get it from the
  charter and the stop hook, and their launch prompt is matched by digest.

- L1: the companion (1.0.6) has no option for extra writable roots: `task` maps `--write`
  to the `workspace-write` sandbox and passes nothing else. Writing the verdict from the final
  message needs no host configuration and was already half there (`opinion` writes the file
  when the seat wrote none), so it is the smaller safe option. Codex's own
  `sandbox_workspace_write.writable_roots` in `CODEX_HOME/config.toml` would also work, but it
  is host-wide configuration WUWEI would have to own, and it would open the whole day
  directory (or the main repository's `.git`) to the seat.
- L2: the same holds for the git metadata. WUWEI commits with the identity the push guard
  later checks, so the commit passes the same identity check a builder's own commit does.
  `git add --all` takes everything the job left in the worktree; the prompt tells the job to
  write nothing else there. The repository's own git hooks run on the commit.
- L2: the start head comes from `derive.head` (the worktree's git files), which
  `complete_checks` and `open_fix` already use; a record without `start` (written before this
  change) or a worktree without a readable HEAD skips the head rule and keeps the dirty rule.
- L2: a fix round that changes nothing is refused too: its delta gates would recheck the head
  they already saw.
- L3: after a forced failure with an empty `CODEX_HOME`, the relaunch reused the
  per-worktree app-server broker started under that home and failed again. The companion has
  no broker stop command (its `SessionEnd` hook stops it); the quickstart says to stop it that
  way or use a fresh worktree. No code change.

## Deferred

- A second-opinion brief keeps the `Model:` line it was first written with; a relaunch after
  the owner changes `gates.second_opinion` still runs the old model. Pre-existing; a follow-up
  issue.
