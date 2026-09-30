# Feature Specification: config check verifies the host protections and seat credential layout

**Feature Branch**: `243-config-check-host`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #243, feat(config). Design sections 4.5, 4.6 and 9.1 as amended by #237;
#170 (`.wuwei/env` and `config check`); #164 (push guard by target repo).

## Root cause (read on main, 158e367)

Design 4.5 and 9.1 now say, in the present tense, that the guarantee for publishing
actions comes from the code host and the credential layout, and that `wuwei config check`
verifies that layout for each configured repository. The code does not.

- `cli/wuwei/commands/config.py:19-60` (`run`) iterates only `config['adapters']` and
  reports credential variables per adapter. It never iterates `config['repos']`, never
  calls `code_host.protection`, and never looks at `GH_TOKEN` or `GITHUB_TOKEN`.
- Reproduced read-only in a scratch workspace: one `[[repos]]` entry
  (`acme/widget`, `default_branch = "main"`), `code_host = "github"`, a `gh` stub on
  `PATH` that logs its argv and exits 0, and `GH_TOKEN=<write token>` in `.wuwei/env`.
  `bin/wuwei config check` printed only the credentials section and exited 0. The stub
  log holds exactly one call, `gh auth status --hostname github.com`: no protection read,
  no token scope read.
- The protection read already exists on the port (`registry.PARAMETERS['code_host']
  ['protection']`, `adapters/code_host/github.py:249-302`) and is used by the merge policy
  and the shepherd, but it does not report force pushes or deletions.
- `adapters/code_host/github.py:86-89` turns any HTTP 404 on the protection endpoint into
  `branch protection absent`. GitHub answers 404 both for an unprotected branch (message
  "Branch not protected") and for a repository the token cannot see ("Not Found"). The
  second is "no permission to read", which this issue requires to be unmeasured, not
  missing.
- There is no port operation that measures a token's scopes, and the core may not run
  `gh` itself (design 3.5).
- `wuwei init` (`cli/wuwei/commands/init.py:83-86`) prints nothing about the publishing
  layout. `docs/site/adapters.md:56` still invites supplying `GH_TOKEN` or
  `GITHUB_TOKEN` with no warning that seats can read it.

## User Scenarios & Testing

### User Story 1 - Host protections are verified per repository (Priority: P1)

The owner runs `wuwei config check` and learns, for each repository in `config.toml`,
whether its base branch has the protections the merge guarantee depends on, and exactly
what to change when one is missing.

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k protection`.

**Acceptance Scenarios**:

1. Given a repository whose base branch is unprotected (simulated code_host), then
   `config check` exits 1 naming the branch and the missing protection.
2. Given no permission to read protections, then the line says unmeasured and the exit
   is 2.
3. Given a protected branch that lacks required checks, lacks required reviews, allows
   force pushes or allows deletions, then each gap is its own `missing` line with the
   setting to change, and the exit is 1.
4. Given a branch with required checks (including every name in the repository's
   `review_required_checks`), at least one required approval, and force pushes and
   deletions blocked, then every line says ok and the exit is 0.
5. Given no required approvals and `shepherd.min_reviewers = 0`, then the reviews line
   says ok with the solo owner exemption named, and the exit is 0.

### User Story 2 - Publishing tokens are kept out of seat environments (Priority: P1)

The owner learns whether a token that seats can read (from `.wuwei/env` or the process
environment the host session and its seats inherit) can approve, release or deploy.

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k token`.

**Acceptance Scenarios**:

1. Given a seat environment carrying a token with write scopes, then `config check`
   exits 1 naming the variable and where it is set, and never prints its value.
2. Given a token whose scopes are all read-only (`read:*`), then the line says ok.
3. Given a token whose scopes cannot be measured (fine-grained or app token, `gh`
   missing, API error, code_host `none`), then the line says unmeasured and the exit is 2.
4. Given neither `GH_TOKEN` nor `GITHUB_TOKEN` set, then no scope read happens and the
   lines say not set.

### User Story 3 - The port reads what the check needs, and nothing more (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_code_host.py tests/test_merge_ports.py tests/test_adapters.py tests/test_shepherd.py`.

**Acceptance Scenarios**:

1. Given a recorded protection response, then the result also carries
   `allow_force_pushes` and `allow_deletions`, and a ruleset `non_fast_forward` or
   `deletion` rule turns the matching one off.
2. Given `gh` reporting "Branch not protected (HTTP 404)", then the reason still names
   `branch protection absent` (merge and shepherd behaviour unchanged); given any other
   404, then the result is exit 2 without that phrase.
3. Given a `token_scopes` read, then the adapter runs only
   `gh api --include user --hostname github.com` with exactly the measured token in the
   child environment, returns the `X-OAuth-Scopes` list, and fails closed (exit 2) when
   the header is absent or empty, on a non-zero exit, or for any variable other than
   `GH_TOKEN` and `GITHUB_TOKEN`.
4. Given the port contract tests, then `token_scopes(variable)` is declared in the
   registry, implemented by `github` and `none`, and the fake host has it.

### User Story 4 - Init states the layout and docs explain the check (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k init tests/test_docs.py -k config_check`.

**Acceptance Scenarios**:

1. Given a fresh `wuwei init`, then the output states the recommended layout once
   (protected base branch with required checks and reviews, no force pushes or
   deletions, no write-scoped token in `.wuwei/env` or the seat environment) and points
   to `wuwei config check`. `init --upgrade` does not repeat it.
2. Given the docs, then an operator can read what the check verifies and why:
   `docs/site/configuration.md` lists each check, the ok, missing and unmeasured
   states, the exit codes 0, 1 and 2, and cites design 4.5 and 9.1.

### Edge Cases

- A repository protected only by rulesets: the classic endpoint answers "Branch not
  protected", so it reads as missing (the merge policy already treats it as
  unmeasured). Out of scope; see Assumptions.
- A repository with a bad `name` (not `owner/repo`): the adapter rejects it before any
  subprocess; the line says unmeasured with the reason on stderr.
- Several repositories with mixed results: the exit is the highest of all lines
  (unmeasured beats missing beats ok), matching the existing credential section.
- `code_host = "none"` with repositories configured: every protection line and every set
  token is unmeasured (exit 2). Unmeasured is never ok.
- Both `GH_TOKEN` and `GITHUB_TOKEN` set: each is measured on its own, with only that
  value in the child environment.
- Token values never reach stdout, stderr, events or the repository; the existing
  redactor already covers `.wuwei/env` values and the two names are in
  `env.CREDENTIALS`.

## Requirements

- **FR-001**: `wuwei config check` prints a `Host protections:` section. For each entry
  in `config['repos']` it calls `code_host.protection(repo['name'],
  repo['default_branch'])` once and reports five lines, each `ok`, `missing` or
  `unmeasured`: protected ref, required checks, required reviews, force pushes,
  deletions.
- **FR-002**: Required checks are ok when the branch requires at least one status check
  and every name in the repository's `review_required_checks` is among them; otherwise
  missing, naming the absent check names.
- **FR-003**: Required reviews are ok when `approvals >= 1`, or when
  `shepherd.min_reviewers == 0` (the existing explicit solo-owner setting), which the
  line names as the exemption.
- **FR-004**: A protection result of exit 2 whose reason contains
  `branch protection absent` is one `missing` line for the protected ref naming the
  branch and what to enable (exit 1). Any other non-zero result is one `unmeasured` line
  with the reason on stderr (exit 2).
- **FR-005**: Every `missing` line names the exact setting to change on the named branch.
- **FR-006**: `config check` prints a `Seat credentials:` section with one line each for
  `GH_TOKEN` and `GITHUB_TOKEN`: `not set` (ok); `read-only` (ok) when every scope
  starts with `read:`; `write scopes <list>` (exit 1) naming the source (`.wuwei/env`
  or the environment) and telling the owner to remove it; `unmeasured` (exit 2) when the
  scope read fails.
- **FR-007**: The code_host port gains one read, `token_scopes(variable)`, declared in
  `registry.PARAMETERS`, implemented in `adapters/code_host/github.py` and
  `adapters/code_host/none.py` (unmeasured), and in `tests/fakes/code_host.py`.
- **FR-008**: The GitHub `protection` read adds `allow_force_pushes` and
  `allow_deletions` (booleans, strict: a missing field is exit 2), and treats a 404 as
  absent only when `gh` reports "Branch not protected".
- **FR-009**: The exit of `config check` is the maximum over the credentials, host
  protections and seat credentials sections.
- **FR-010**: A fresh `wuwei init` prints the recommended layout and points to
  `wuwei config check`; `--upgrade` and `--dry-run` do not.
- **FR-011**: `docs/site/configuration.md` documents the checks, their states, exit codes
  and the reason (design 4.5, 9.1). `docs/site/adapters.md` stops presenting a
  write-scoped `GH_TOKEN` as a neutral choice and points to the check.
- **FR-012**: Tests run with no network and no real `gh`; the test session scrubs
  `GH_TOKEN` and `GITHUB_TOKEN` so a developer's shell cannot change results.

## Success Criteria

- SC-001: The four acceptance scenarios of issue #243 pass as tests against the fake
  code_host.
- SC-002: The scratch reproduction above exits non-zero and names `GH_TOKEN`.
- SC-003: The full suite passes; merge and shepherd tests are unchanged except the one
  shepherd test whose simulated stderr moves to gh's real "Branch not protected" text,
  and the one workspace test whose `[[repos]]` entries now make `config check` exit 2.

## Assumptions

- "The explicit solo-owner exemption" is the existing `shepherd.min_reviewers = 0`
  (documented in `docs/site/configuration.md` as the solo owner setting). No new config
  key.
- "The test job names" are the repository's `review_required_checks` entries when set;
  when empty, at least one required status check is enough.
- A successful protection read proves the ref is protected. `enforce_admins`, stale review
  dismissal and code owner review are not required by the issue and are not checked.
- The seat environment is the union of `.wuwei/env` (readable by any seat running as the
  owner, 9.1) and the process environment `config check` inherits, which is the
  environment the host session and Claude seats inherit. Codex children already get
  `env.child_environment()`, which drops both names; the file is still readable to them,
  so the finding stands for every runtime.
- Read-only means every classic OAuth scope starts with `read:`. Scopes are measured from
  the `X-OAuth-Scopes` header of `GET /user`; fine-grained and app tokens do not report
  it, so they are unmeasured (exit 2), never ok.
- `gh` prints API errors as `gh: <message> (HTTP <status>)` on stderr, so an unprotected
  branch reads `gh: Branch not protected (HTTP 404)`.
- The credential `gh auth login` stores is shared by the host session and Claude seats
  (same OS user). The issue scopes the check to environment variables; separating the
  stored credential needs a separate OS user for seats, which 9.1 lists as a later option.
- Ruleset-only protection (no classic protection) reads as missing. Supporting it would
  change the merge policy's input and belongs to a separate issue.
- "Prints the recommended layout once" means on fresh `wuwei init` only, not on upgrade.
- `config check` calls the port with `root=None`, like the existing `auth_status` call;
  the `none` adapter may append its usual `adapter: none` event.
