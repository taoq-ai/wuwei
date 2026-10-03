# Feature Specification: wuwei setup, one command with one confirmation

**Feature Branch**: `327-setup`
**Created**: 2026-10-03
**Status**: Draft
**Input**: Issue #327, feat(setup): wuwei setup: discover the repositories and the host, write
the configuration, calibrate and interview, promote once, and check, in one command. Design
spec 3.1 (layout), 3.5 (ports and adapters), 5.2 (flow), 9.1 (threat model, guard scope);
builds on #278 (calibrate), #279 (owner interview), #227 (host terminal digest), #222
(owner-action table), #243 (config check), #308 (shadow mode), #313 (profiles), #326 (config
failure mode, merged). Evidence: the owner's first-run trial of v0.11.0 (2026-10-03),
finding B5.

## Root cause (reproduced read-only on main)

Reproduced from the worktree with `bin/wuwei` and an in-process probe of
`cli/wuwei/calibrate.py`, outside any workspace:

- There is no owner-confirmed way to change one config value. `bin/wuwei config set
  owner.verbosity.default '"full"'` exits 2 with `argument action: invalid choice: 'set'
  (choose from 'check', 'promote')`: `cli/wuwei/commands/config.py:16-24` `register` only
  defines `check` and `promote`. `bin/wuwei setup --shadow` exits 2 with `invalid choice:
  'setup'`: no such command module under `cli/wuwei/commands/`.
- The only confirmed config writer is `config promote` (`cli/wuwei/commands/config.py:114-171`).
  Its digest path (print the summary, `sha256(summary)[:12]`, `integrity._host_confirm`,
  re-read the file, `atomic_write`, lines 152-165) is inlined in `promote`, so nothing else
  can reuse it.
- `promote` refuses a config without repositories (`config.py:127-128`, `calibrate.NO_REPOS`),
  and `calibrate.apply` (`cli/wuwei/calibrate.py:493-535`) cannot create a `[[repos]]` table:
  probing `apply(template, [(('repos', 0), 'name', 'acme/widget')])` raises
  `ValueError: cannot place calibration keys in this config.toml layout; edit by hand`
  (line 508). So the owner must hand-write every `[[repos]]` table before calibration can run.
  That is the six round trips of B5: the planner measured every value and could only hand it
  over as text to paste.
- `calibrate.settle` plus `calibrate.apply` already place and validate one owner value:
  probing `settle(template, [(('owner', 'verbosity'), 'default', 'full')])` then `apply`
  returns valid text with `default = "full"`, and `settle` reports a present key that is not
  a one-line assignment (`owner.verbosity`, a table) as a hand edit instead of writing it.
  `config set` reuses them.
- Discovery facts have no ports: the code_host port (`cli/wuwei/registry.py:32-38`) has no
  default-branch read, and the git adapter allowlist (`adapters/vcs/git.py:52-144`) has no
  remote URL read. `vcs.identity` (`adapters/vcs/git.py:232`) and `host.free_memory`
  (`adapters/host/local.py:11`) exist.
- The owner-action table (`cli/wuwei/guards/protect_state.py:44-61`) lists `config promote`
  only; a seat calling the new commands would not be refused by the hook.

## User Scenarios & Testing

### User Story 1 - Set one config value with one confirmation (Priority: P1)

The planner knows a value. It gives the owner one command; the owner runs it in a host
terminal, reads the diff, types the digest, and the file is changed and still parses.

**Independent Test**: call `config set` in process with an injected `confirm` in a workspace
built from the shipped template.

**Acceptance Scenarios**:

1. Given a workspace from the template, when the owner runs `config set
   owner.verbosity.default '"standard"'` and types the digest, then a unified diff of
   `config.toml` is printed, the digest is the first 12 hex characters of the SHA-256 of the
   printed text, the file afterwards has `default = "standard"` under `[owner.verbosity]`,
   `load_config` accepts it, and the exit is 0.
2. Given the same command, when the owner types something else, then nothing is written and
   the exit is 1 with `declined; nothing written`.
3. Given an invalid value, then it is refused before the confirmation (the confirm callback is
   never called, the file is byte-identical, exit 1) with the reason: `config set
   owner.verbosity '"brief"'` (a table set to a string; the reason names
   `owner.verbosity.default`), `config set owner.verbosity.default '"loud"'` (not a level),
   `config set cap 'many'` (not TOML), `config set cap '2\nprofile = "standard"'` (more than
   one value), `config set nonsense 1` (unknown key).
4. Given a value equal to the current one, then `No config.toml changes` is printed, no
   confirmation is asked, and the exit is 0.
5. Given no host terminal (`/dev/tty` unavailable), then nothing is written and the exit is
   2 with `this is an owner action: run it in a host terminal`.
6. Given `config set repos.0.merge_deploys false` with one configured repository, then the
   value lands in that repository's table.

### User Story 2 - Add one repository with one confirmation (Priority: P1)

**Independent Test**: call `config add-repo` in process with an injected `confirm`.

**Acceptance Scenarios**:

1. Given a template workspace, when the owner runs `config add-repo --name acme/widget --path
   widget --branch main --identity "Pat Example <pat@example.test>"` and types the digest,
   then a `[[repos]]` table with those four values is appended, the diff was shown, and
   `load_config` returns one repository with that identity.
2. Given a repository already configured with the same name or the same resolved path, then
   it is refused before the confirmation with the existing duplicate reason, exit 1.
3. Given `--identity` not of the form `Name <email>`, or a `--name` that is not
   `owner/repo`, then it is refused before the confirmation, exit 1.

### User Story 3 - A seat cannot run them (Priority: P1)

**Acceptance Scenarios**:

1. Given a Bash call `bin/wuwei config set owner.name '"Pat"'` from a seat inside a
   workspace, when it goes through the PreToolUse hook, then it is refused as an owner action
   (protect_state exit 1, reason contains `owner`); the indirect forms of #222
   (`X=config; bin/wuwei $X set`, `echo set | xargs bin/wuwei config`,
   `bin/wuwei config -- set`) are refused too.
2. The same holds for `config add-repo` and for `bin/wuwei setup` with any flags
   (`--shadow`, `--repos <dir>`, `--posture <name>`).
3. Outside a workspace each of these returns 0 (spec 9.1 scope).
4. `bin/wuwei config check` and `bin/wuwei calibrate` still pass.

### User Story 4 - One command sets up the workspace (Priority: P1)

The owner installs the plugin, runs `bin/wuwei setup --shadow` in the project directory,
answers the interview, reads one proposal, types one digest, and is told what is still owed.

**Independent Test**: a temporary directory with three git repositories (each with an
`origin` remote on github.com and a local `user.name` and `user.email`), a fake code host,
a stubbed PATH, a scripted interview and an injected `confirm`; `setup` runs in process.

**Acceptance Scenarios**:

1. Given that directory without `.wuwei/`, when the owner runs `setup --shadow`, then `init`
   creates the workspace in shadow mode, and one printed proposal holds: three `[[repos]]`
   tables with `name` (`owner/repo` from the remote), `path` (relative to the workspace),
   `default_branch` (from the fake host) and `identity` (from each repository's git config),
   the calibration additions, and the interview answers. The confirm callback is called
   exactly once; after it, `config.toml` has the three repositories with those values,
   `.wuwei/calibration.json` names all three, today's `calibration.md` exists, `config check`
   exits 0 with no further edit, and setup exits 0.
2. Given the owner declines, then `config.toml` is byte-identical to the one `init` wrote,
   `calibration.json` does not exist, and the exit is 1.
3. The output lists the host facts: platform, whether `claude`, `gh` and `ziran` are on PATH,
   `gh` authentication, and free memory (or `unmeasured`). When `ziran` is on PATH and
   `adapters.scanner` is `none`, the proposal sets `adapters.scanner = "ziran"`.
4. A child directory whose `.git` is a file (a linked worktree) is listed as a worktree and
   not proposed as a repository.
5. A repository whose remote is not on github.com, or whose default branch cannot be read
   (no `gh` authentication, or the host read fails), is not proposed; the closing list names
   it with the exact `bin/wuwei config add-repo --name ... --path ... --branch ...` command.
6. Repository text is data (#278): an identity that `calibrate.instruction_like` flags is not
   written, and the output says it was flagged.
7. `--posture cli-tool` adds the starter profile's keys to the same proposal; a URL is
   refused (no network beyond `gh` reads).
8. After the confirmation, setup runs `config check` and `mcp check` and prints what is
   still owed, each with its exact command (repositories not proposed, missing credential
   variables, `owner.name`, charter proposals to land with `bin/wuwei promote`, MCP servers to
   decide), then `Next: /wuwei plan`.
9. Without a terminal on stdin, setup exits 2 with the host-terminal reason before writing
   anything.

### User Story 5 - Setup is idempotent (Priority: P1)

**Acceptance Scenarios**:

1. Given the workspace after User Story 4, when `setup` runs again, then it prints `Nothing
   to propose`, asks no interview question, never calls the confirm callback, leaves
   `config.toml`, `calibration.json` and today's proposal files unchanged, runs the checks,
   and exits 0.
2. Given a workspace whose repositories were configured by hand and never calibrated (no
   `calibration.json`), when `setup` runs, then it proposes the calibration and the interview
   for them and adds no `[[repos]]` table.

### User Story 6 - The docs say one command (Priority: P2)

**Acceptance Scenarios**:

1. README `## Quick start` and `docs/site/index.md` `## Start here` read: install,
   `bin/wuwei setup --shadow`, `/wuwei plan`, in that order.
2. `docs/site/daily.md` first-day section uses `setup`; `docs/site/reference.md` lists
   `setup`, `config set` and `config add-repo` in Commands and in Host terminal actions (and
   `docs/site/concepts.md` in its host terminal list); `docs/site/configuration.md` explains
   `config set` and `config add-repo` under Calibration.

### Edge Cases

- A `config.toml` that does not load: `config set`, `add-repo` and `setup` exit 1 with the
  `load_config` reason (including the #326 hint) and write nothing.
- `config.toml` changed between the proposal and the digest: nothing written, exit 2
  (the existing promote rule).
- A symlinked `config.toml` or `calibration.json`: exit 2, nothing written (existing rule).
- `config set` on a deploy list only adds items, as `settle` does for interview answers; it
  never removes a deploy-ban pattern.
- No repository configured and none discovered: setup prints the owed `config add-repo` line
  and exits 1 without a confirmation.
- `setup --shadow` on an existing enforce workspace proposes `guards.mode = "shadow"` and
  `guards.shadow_since` in the same proposal.

## Requirements

### Functional Requirements

- **FR-001**: `config set <dotted.key> <toml-value>` parses the value as one TOML value,
  places it with `calibrate.settle` and `calibrate.apply`, validates the result with
  `load_config(root, raw=text)`, and refuses (exit 1, before any confirmation) anything that
  does not parse, is not one value, names an unknown key, needs a hand edit, or fails
  validation.
- **FR-002**: `config add-repo --name --path --branch [--identity "Name <email>"]` appends one
  `[[repos]]` table and validates it the same way.
- **FR-003**: `config set`, `config add-repo`, `config promote` and `setup` share one digest
  path: print the summary, ask for `sha256(summary)[:12]` on `/dev/tty`, re-read
  `config.toml`, write atomically. Declined is exit 1; no terminal is exit 2.
- **FR-004**: The owner-action table refuses `config set`, `config add-repo` and `setup`
  (any flags) from agent tools inside a workspace, with the #222 indirect forms.
- **FR-005**: The code_host port gains `default_branch(repo)`; the vcs port gains
  `remote_url(repo)`. Both have contract rows and fakes; code_host `none` reports unmeasured.
- **FR-006**: `setup` discovers repositories (the workspace root when it is a git repository,
  plus each git repository directly under the `--repos` directories, default the workspace
  root), their GitHub name from the `origin` remote, default branch through the code_host
  port when `gh` is authenticated, identity through `vcs.identity`, and linked worktrees; and
  the host (platform, `claude`, `gh`, `ziran` on PATH, free memory).
- **FR-007**: `setup` runs `init` when no workspace exists (shadow when asked), then builds one
  proposal (new `[[repos]]` tables, adapter and shadow settings, `--posture` profile,
  interview answers, calibration) and applies it after one confirmation through FR-003.
- **FR-008**: After applying, `setup` runs `config check` and `mcp check` and prints what is
  still owed with the exact command for each. Its exit is the larger of the two checks.
- **FR-009**: A second `setup` with nothing new proposes nothing and asks nothing.
- **FR-010**: No network beyond `gh` reads during discovery; discovered text is written only
  as escaped TOML strings after validation, and instruction-like identity text is dropped.

## Success Criteria

- **SC-001**: From a fresh project with three repositories, the owner reaches a passing
  `config check` with one command, one interview and one digest; no hand edit of
  `config.toml`.
- **SC-002**: Every value the planner can measure can be handed to the owner as one
  `config set` or `config add-repo` command; no parse failure reaches the file.
- **SC-003**: The full suite passes; every hook stays within its `WUWEI_BENCH=1` budget.

## Assumptions

- The issue's example `config set owner.verbosity '"brief"'` names a table in the schema
  (`default` plus one key per surface), so setting it to a string is invalid. The valid
  scenario uses `owner.verbosity.default '"standard"'` (a visible change from the template's
  `"brief"`); `owner.verbosity '"brief"'` is the refused-before-confirmation case.
- `init` runs before the confirmation when there is no workspace, as `wuwei init` does today.
  "Nothing is applied without the confirmation" covers `config.toml` and `calibration.json`.
  The interview answers (`interview.json` and its proposals) and an imported posture
  (`profile.json` and its proposals) are recorded before the confirmation, as
  `calibrate --interview` and `calibrate import` do today; they are proposals, not applied.
  Calibration charter proposals and `calibration.md` are written only after the confirmation,
  so a second run never re-proposes a landed charter block (`promotion` rejects a duplicate
  add).
- The interview is asked only when the proposal adds a repository or `calibration.json` is
  absent. `bin/wuwei calibrate --interview` re-asks it.
- Without `gh` authentication (or with `adapters.code_host = "none"`), a repository's default
  branch is not guessed from local refs; the repository is listed as owed with the exact
  `config add-repo` command.
- A repository's `name` is `owner/repo` parsed from an `origin` URL on github.com (https,
  `git@github.com:` or `ssh://git@github.com/`) and checked with `references.repository`.
  Other remotes are owed.
- The identity proposed is what `git config --get user.name/user.email` returns in that
  repository (local over global), as the trial planner did.
- Adapter choices are limited to what discovery can see without credentials:
  `scanner = "ziran"` when `ziran` is on PATH. Other adapters stay at their defaults; their
  credential variables are reported by `config check` as today.
- `--posture` takes a starter name or a local file; an `https://` profile stays with
  `calibrate import`, so setup makes no network call beyond `gh` reads. The closing
  `mcp check` is the existing gate, unchanged.
- `config set` addresses repositories by index (`repos.0.merge_deploys`); keys with dots
  inside a register name are a hand edit.
- `config set` keeps the `settle` rule that a deploy list only grows; removing a deploy-ban
  pattern stays a hand edit.
- `setup` is an owner action as a whole (it writes `config.toml`); its table entry matches the
  group with any following words, because its flags take values.
- Updating `skills/wuwei-plan/SKILL.md` to hand the owner `config set` commands is out of
  scope (the issue names the docs only).
