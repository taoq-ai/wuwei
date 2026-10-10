# Feature Specification: Two installs named, traces warns below strict, one credential reader, every backlog discovered

**Feature Branch**: `601-two-installs`
**Created**: 2026-10-09 (revised 2026-10-10 against main at 0.24.1)
**Status**: Draft
**Input**: GitHub issue #601: fix(doctor): two plugin installs are named with the fix, the
traces guard says what it could not read and never fails a tool call below strict,
heartbeat and doctor read credentials the same way, and discover reads every configured
backlog. Scope additions of 2026-10-09: one canonical `.wuwei/executable` that never flips
between installs, and a doctor hooks row that finds the registration from either launcher.

Binding principles: #530 (under observe and guarded a guard is a warning or a card, never a
refusal, except the records floor; strict keeps its refusals) and #551 (the next step is a
command the CLI returns, never a paragraph).

## Root cause

Reproduced read-only on a scratch workspace (`[security] required = true`,
`posture = "observe"`, `.wuwei/executable` naming another launcher), piping PostToolUse
payloads through `hook.run`: `ls -la`, a pipe into the other launcher and an unbalanced
quote all exit 0, but `cat credentials/backup.env "x` (a Bash call that names the
honeytoken file and that the shell reader cannot parse) exits 2 with the generic sentence
plus `posture: records = block (floor; no setting lowers it)`, and `events.jsonl` holds no
`traces.gap`. That is the owner's report: a failed tool call under observe that doctor's
`traces` row does not see.

1. **The traces guard fails a tool call with a sentence that names nothing and leaves no
   gap.** `cli/wuwei/guards/traces.py:121-122` returns `(2, 'wuwei traces: cannot inspect
   or record workspace security evidence; run bin/wuwei doctor, then retry')` straight from
   the inspect block (`security.load`, `security.trace_findings`, `security.record`,
   redaction at `:99-119`). The return skips the stderr line and the `traces.gap` append at
   `:128-137`, so doctor's `traces` row (`cli/wuwei/commands/doctor.py:620-622`, which
   counts `traces.gap` pages) says "no gaps today". The exit 2 is then levelled by
   `hook.posture` (`cli/wuwei/commands/hook.py:249`) under the guard's area `records`
   (`cli/wuwei/guards/__init__.py:39-43`), the floor in every posture
   (`cli/wuwei/workspace.py:46`), so it is a failed tool call under observe and guarded.
   Any read in the inspect block can trip it; the reproduced trigger is
   `security.reads_honeytoken` raising `ValueError` on an unparsable command that names the
   honeytoken file (`cli/wuwei/security.py:173-177`).
2. **`.wuwei/executable` flips between installs.** `init` writes the running launcher
   (`cli/wuwei/commands/init.py:82-83`) and `init --upgrade` rewrites it to whichever
   launcher ran the command (`:381`, `:393`, `:408`). With a release extraction and the
   marketplace cache on one machine, each run of the other launcher flips the record; the
   hooks run one install while the record names the other. Doctor's executable row fix
   (`doctor.py:259-271`, `wuwei init --upgrade`, which `_row` rewrites to the running
   launcher) flips it again.
3. **Doctor judges the install by its own launcher.** The hooks row (`doctor.py:138-160`)
   is ok only when a registered `installPath` equals the launcher doctor runs from, so
   doctor run from another install says "not listed" although the hooks are registered. The
   executable row compares the record with that same launcher. No row says two installs
   exist.
4. **The heartbeat reads a stale environment.** `heartbeat._config`
   (`cli/wuwei/heartbeat.py:80-86`) calls `config.missing`
   (`cli/wuwei/commands/config.py:198-210`), which reads `os.environ`. The watch is one
   long-lived process (`watch.serve`, `cli/wuwei/watch.py:581-614`, run by `watch.run` at `:618`): `.wuwei/env` is loaded once at its
   start (`cli/wuwei/__main__.py:66-73`) and never again. A credential added after the
   watch started reads "missing" on every beat, while doctor, a fresh process, loads the
   file and reads it set. Nothing compares the two readings.
5. **Discovery reads one repository's backlog.** The GitHub tracker's `_repo`
   (`adapters/tracker/github.py:87-92`) returns `tracker.project` or the first configured
   repository, and `backlog` (`:99-114`) reads only that one. `discovery.discover`
   (`cli/wuwei/discovery.py:67-211`) calls it once, and `wuwei discover`
   (`cli/wuwei/commands/discover.py`) has no `--repo`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A traces failure is a named warning, never a failed tool call below strict (Priority: P1)

A seat's tool call completes; the PostToolUse traces guard cannot inspect or record it.
Under observe and guarded the call is not failed: the hook exits 0, stderr names what the
guard could not read, and a `traces.gap` that doctor counts is recorded. Under strict the
refusal stands, with the same specific reason.

**Why this priority**: seats lost tool calls to a hook error that nothing explained.

**Independent Test**: a security-enabled fixture workspace, one PostToolUse payload through
`bin/wuwei hook PostToolUse` (in process, `hook.run`) per posture, with one read failing.

**Acceptance Scenarios**:

1. **Given** posture observe or guarded and a traces inspection or recording failure,
   **When** the PostToolUse hook runs, **Then** it exits 0, stderr carries a reason naming
   the step it could not read (the security material `.wuwei/security.json`, the tool call
   for canary and honeytoken findings, the events log `events.jsonl`, the tool payload for
   redaction, or the traces file `traces.jsonl`), and a `traces.gap` event with that reason
   is recorded when the events log is writable.
2. **Given** posture strict and the same failure, **When** the hook runs, **Then** it exits
   2 with that specific reason.
3. **Given** `.wuwei/executable` names a launcher other than the one the hook runs from,
   **When** the traces guard fails, **Then** its reason also names both launchers and ends
   with `run bin/wuwei doctor, which names the fix`.
4. **Given** a traces failure recorded today, **When** doctor runs, **Then** its `traces`
   row is a warning that counts the gap.
5. **Given** an exception whose message carries private text, **When** the reason is
   built, **Then** it holds the step and the exception type, never the message.

---

### User Story 2 - Doctor names two installs and the fix; the executable record never flips (Priority: P1)

The owner has the marketplace cache and a release extraction on one machine. Doctor names
both, which one Claude Code registered (the hooks run it) and which one
`.wuwei/executable` names, and gives the exact command that points the workspace at the
registered one. `init` and `init --upgrade` write the registered install whichever launcher
ran them, so the record stops flipping. Doctor's hooks row reads the registration the same
way from either launcher.

**Why this priority**: the flip is what put the hooks and the record on different installs.

**Independent Test**: a fixture `installed_plugins.json` registering install A, a second
release-shaped install B with its own `bin/wuwei`; `integrity.PLUGIN` set to B; run
doctor and `init` / `init --upgrade` in process.

**Acceptance Scenarios**:

1. **Given** install A registered and doctor running from install B, **When** doctor runs,
   **Then** an `installs` row warns, names A (registered in Claude Code; its hooks run) and
   B (this launcher; named by `.wuwei/executable` when it is), and its fix is
   `<A>/bin/wuwei init --upgrade, then remove <B> if you do not use it`.
2. **Given** only one install is visible, **When** doctor runs, **Then** no `installs` row
   is added (healthy row lists stay as they are).
3. **Given** install A registered, **When** `init` or `init --upgrade` runs from release
   launcher B, **Then** `.wuwei/executable` names `<A>/bin/wuwei`; a second
   `init --upgrade --dry-run` prints no `executable pointer` line.
4. **Given** no plugins file, an unreadable one, or no `wuwei@` entry whose install has
   `bin/wuwei`, **When** `init` runs, **Then** it writes the running launcher, as today.
5. **Given** the running plugin is a development checkout (`.git` and no
   `MANIFEST.sha256.sig`), **When** `init` runs, **Then** it writes the checkout's launcher
   (a checkout is loaded per session with `--plugin-dir`, as doctor's hooks row already
   says).
6. **Given** install A registered and doctor running from B, **When** doctor runs, **Then**
   the hooks row is ok ("registered in Claude Code"), and the executable row is ok when the
   record names `<A>/bin/wuwei`.

---

### User Story 3 - Heartbeat and doctor read credentials the same way (Priority: P2)

The heartbeat's config probe reads `.wuwei/env` through the same loader at every beat, so
a credential the owner adds after the watch started is seen on the next beat. When the
watch's last saved beat and doctor's own reading still differ, doctor reports it.

**Why this priority**: two surfaces disagreeing on one fact makes both untrustworthy.

**Independent Test**: `GITHUB_TRACKER_TOKEN` absent from the process environment, written
to `.wuwei/env`, then `heartbeat.measure`; separately a saved beat whose config probe says
missing, and doctor.

**Acceptance Scenarios**:

1. **Given** a credential set in `.wuwei/env` and absent from the process environment,
   **When** the heartbeat measures, **Then** the config probe is ok, as doctor's reading is.
2. **Given** the watch's last saved beat says `missing GITHUB_TRACKER_TOKEN` and doctor
   reads it set, **When** doctor runs, **Then** a `credentials` row warns with both
   readings and names the fix command.
3. **Given** the two readings agree, or no beat is saved, **When** doctor runs, **Then** no
   `credentials` row is added.

---

### User Story 4 - Discover reads every configured repository's backlog (Priority: P2)

With two configured repositories and the GitHub tracker, `wuwei discover` lists open
issues from both, each candidate naming its repository as `repo`. `--repo <org>/<name>`
narrows the candidates to one. The lead charter tells the lead to run it and keep `repo`.

**Why this priority**: discovery missed the code repository's backlog.

**Independent Test**: the GitHub adapter with a replayed GraphQL response per repository
and a two-repository config; `wuwei discover` through `main` with a fake tracker port.

**Acceptance Scenarios**:

1. **Given** two configured repositories, **When** the GitHub adapter reads the backlog,
   **Then** it queries both, once each, and every id names its repository
   (`<org>/<name>#<n>`).
2. **Given** `tracker.project` set to a repository that is also configured, **When** the
   backlog is read, **Then** that repository is read once.
3. **Given** two configured repositories, **When** `wuwei discover` runs, **Then** the
   candidates come from both, each with `source` and `repo`.
4. **Given** `--repo` naming one configured repository, **When** `wuwei discover` runs,
   **Then** only candidates whose `repo` is that repository, or that name no configured
   repository (Linear and Jira tickets), remain.
5. **Given** `--repo` naming no configured repository, **When** `wuwei discover` runs,
   **Then** it exits 2 with a reason naming the configured repositories.
6. **Given** one repository's read fails, **When** the backlog is read, **Then** the
   tracker source is unmeasured (exit 2 through the adapter), never a partial list.

### Edge Cases

- The plugins file lists `wuwei@` entries in more than one scope: the first entry whose
  `installPath` has `bin/wuwei` is the registered install.
- `.wuwei/executable` names a path that no longer exists: the executable row fails as
  today and it is not counted as an install.
- The config cannot be read when the traces guard decides its posture: the refusal stays
  (fail closed, as strict).
- A credential removed from `.wuwei/env` stays in a running watch (the loader never
  unsets); the doctor `credentials` row reports the disagreement.
- Two configured repositories where one name is a prefix of the other (`acme/app`,
  `acme/app-docs`): a candidate's `repo` is matched on `<name>#` or `<name>:`, never on a
  bare prefix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The traces guard MUST build its failure reason from the step it was on
  (security material, finding inspection, events log, payload redaction, traces file) and
  the exception type, never the exception message.
- **FR-002**: Every traces failure MUST go through the guard's existing tail: stderr line,
  `traces.gap` event, then the return.
- **FR-003**: Under observe and guarded the traces guard MUST return exit 0 after FR-002;
  under strict it MUST return exit 2 in the cases that refuse today. An unreadable config
  MUST keep the refusal.
- **FR-004**: When `.wuwei/executable` does not name this launcher, the traces reason MUST
  name both and point at `bin/wuwei doctor`.
- **FR-005**: One helper MUST return the registered install (the first `wuwei@*` entry in
  the plugins file whose `installPath` has `bin/wuwei`), and one MUST return the canonical
  launcher (the running launcher for a development checkout, else the registered one, else
  the running one). init, init --upgrade, doctor's hooks row and doctor's executable row
  MUST use them.
- **FR-006**: Doctor MUST add an `installs` warning row when it sees more than one install
  among this launcher, the registered install and the `.wuwei/executable` target, naming
  each with its role and the exact fix command.
- **FR-007**: The heartbeat config probe MUST load `.wuwei/env` with `env.load` before it
  checks credentials.
- **FR-008**: Doctor MUST add a `credentials` warning row when the watch's last saved
  heartbeat config probe differs from doctor's own config probe.
- **FR-009**: The GitHub tracker backlog MUST read `tracker.project` (when set) and every
  configured repository, once each.
- **FR-010**: `discovery.discover` MUST set `repo` on each candidate whose id names a
  configured repository and MUST take `repo` to narrow; `wuwei discover` MUST take
  `--repo`.
- **FR-011**: The lead charter MUST tell the lead to run `wuwei discover` (every configured
  repository by default, `--repo` to narrow) and keep each candidate's `repo`; the
  generated agents MUST be rebuilt with `bin/wuwei agents build`.
- **FR-012**: Design spec 9.2 MUST gain an invariant row for FR-003 (I37; I25 to I28 belong
  to #603 to #606, I29 and I30 to #599, I36 to #636), checked in `tests/test_invariants.py`.

### Key Entities

- **Registered install**: the `installPath` Claude Code lists for `wuwei@*` in
  `scanner.mcp.plugins_file` (default `~/.claude/plugins/installed_plugins.json`).
- **Canonical launcher**: the running launcher for a development checkout, else
  `<registered install>/bin/wuwei`, else the running launcher.
- **Candidate `repo`**: the configured repository name a discovery candidate's id begins
  with (`<name>#` or `<name>:`); the same key `plan propose` reads (#603).

## Success Criteria *(mandatory)*

- **SC-001**: Under observe and guarded no traces failure makes `bin/wuwei hook
  PostToolUse` exit non-zero (I37).
- **SC-002**: Every traces failure leaves a `traces.gap` when the events log is writable,
  and doctor's `traces` row counts it.
- **SC-003**: `init --upgrade` from two release installs leaves the same
  `.wuwei/executable`.
- **SC-004**: For the same `.wuwei/env`, the heartbeat config probe and doctor agree.
- **SC-005**: `wuwei discover` with two configured repositories lists candidates from both.

## Assumptions

- The hooks run the registered install (Claude Code runs a registered plugin's hooks). A
  session started with `--plugin-dir` on an unregistered copy is visible to doctor only
  when doctor runs from it or the record names it; the traces reason (FR-004) names it from
  the hook side.
- A development checkout keeps itself as the canonical launcher, so the dry-run workspaces
  built from a checkout keep pointing at it. The marketplace directory and a release
  extraction carry no `.git` at the plugin root (doctor's report of "not listed" from the
  marketplace launcher shows that), so they resolve to the registered install.
- "A hook failure" in the issue means the traces guard (the PostToolUse recorder). The
  hook-level could-not-run paths (malformed payload, guard discovery, no workspace scope)
  keep their exits; `tests/test_traces.py` and `tests/test_guard_mutation.py` pin them.
- The guard decides its own posture, like the MCP gate and spec mode; `AREAS['traces']`
  stays `records`, so under strict the hook still prints the records floor line.
- With security off (`security_data is None`) a recording failure keeps today's exit 0 in
  every posture.
- The "integrity record" the issue lists is not read on the traces path; the steps in
  FR-001 are the ones the guard reads.
- The loader only adds names (`setdefault`); reloading at each beat covers the reported
  case, and FR-008 covers removals.
- Candidate ids already name their repository (`<org>/<name>#<n>` for GitHub tickets and
  PR rows, `<name>:scanner:...` for scanner rows), so `repo` is derived in discovery and
  the tracker port's row shape stays unchanged. Linear and Jira tickets name no repository,
  carry no `repo` and are kept by `--repo`.
- `--repo` narrows the candidates; the `sources` lines still report what was read.
- A configured repository name that is not `<owner>/<repo>` fails the GitHub backlog read
  with a reason naming it, as `_repo` does for one today (fail closed).
- `github.create` keeps writing to `tracker.project` or the first repository.
- No doctor `--fix` apply is added for the installs row; the fix is the printed command.
- Fixtures use neutral names (`acme/widget`, `acme/gadget`, `tmp_path` installs); no owner
  path or repository appears in the repository.
- The worktree branch was 16 commits behind `main`; it was fast-forwarded (no commit) so
  file and line references here are main's at 0.24.1.
