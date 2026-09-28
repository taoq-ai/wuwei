# Feature Specification: Code host and VCS ports

**Feature Branch**: `087-code-host-vcs-ports`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: GitHub issue #87, M1 Guards; depends on #5.

## User Scenarios & Testing

### User Story 1 - Reliable repository evidence (Priority: P1)

Guards receive repository and pull request evidence without understanding external tool output.

**Independent Test**: Replay recorded successful and failed reads through each adapter.

**Acceptance Scenarios**:

1. Given an error JSON body on stdout with exit 0, when read, then return exit 2 with no data and print a reason.
2. Given a nonzero exit, timeout, unavailable tool, malformed or incomplete response, then return exit 2 with no data.
3. Given repository state, then return normalized identity, head, merge base, status, diff statistics and commit history.
4. Given PR evidence, then return normalized PR, checks at the requested SHA, reviews, comments, thread resolution and protection requirements.

### User Story 2 - Constrained repository actions (Priority: P1)

Callers can create PRs, request reviewers, comment, merge at an expected head, create revert PRs and add worktrees.

**Independent Test**: Replay writes and assert exact arguments and returned plain data.

**Acceptance Scenarios**:

1. Given a merge request and expected head, then squash merge must match that head.
2. Given adapter functions, then none approves reviews, overrides protection or merges as admin.
3. Given write failures, then return exit 2 without reporting success.

### User Story 3 - Replaceable integrations (Priority: P2)

Core tests can use recording fakes and configuration can select installed adapters.

**Independent Test**: Extend existing adapter contracts, config tests and core boundary checks.

**Acceptance Scenarios**:

1. Every public adapter module implements its port's declared functions and parameters.
2. No core module imports process launchers or references os process-launch APIs, enforced by an AST scan test.
3. Default selection is github for code_host and git for vcs; code_host none records unavailable operations.
4. A recording fake per port returns fixture-backed plain results and records calls without external execution.

### Edge Cases

Empty collections are valid; malformed collections are not. Pagination must not silently omit evidence. Missing identity, binary diffs, renamed paths and paths with whitespace need explicit handling. Inputs cannot inject command options. A missing protection response is unavailable, not unprotected.

## Requirements

- **FR-001**: Extend the existing registry, shared result and configuration table with the issue's ten code_host and seven vcs operations.
- **FR-002**: Confine external calls and vendor parsing to adapters, with bounded subprocess timeouts and three-state results.
- **FR-003**: Normalize all evidence to plain dictionaries and lists, including empty results.
- **FR-004**: Provide only the constrained write operations above; merge must check the expected head.
- **FR-005**: Supply offline fixture replay tests, port fakes, contract coverage and a core subprocess boundary check.

### Key Entities

- Pull request: repository, number, author, branch/head, merge state and change size.
- Evidence: checks, reviews, discussion threads and protection requirements.
- Repository: configured identity, commit heads, changed paths and commit history.
- Result: exit, data and diagnostic reason, using the existing shared type.

## Success Criteria

- **SC-001**: Every specified operation passes its contract and offline replay test.
- **SC-002**: All tested external failures return exit 2 with no data.
- **SC-003**: Every merge invocation contains the requested head constraint, with no approval or override operation exposed.
- **SC-004**: The full test suite passes using the supplied interpreter without network or an installed gh; the repository-isolation regression uses local git.

## Assumptions

- Code host references are explicit `owner/repo#number` or `https://github.com/owner/repo/pull/number`, avoiding ambient repository selection. Enterprise host support is deferred.
- `root` retains the existing optional workspace context convention; vcs receives its repository explicitly.
- Identity includes configured user.name/user.email plus effective author and committer identities, retaining GIT_AUTHOR_* and GIT_COMMITTER_* overrides. Repository-selecting variables and GIT_CONFIG* are removed before git runs.
- The vcs port must answer and uses a fake, without a none implementation, as allowed by design 3.5.
- A fixed 30-second timeout is sufficient per subprocess; no timeout configuration is added.
- Large nested review conversations may fail closed on truncation rather than be accepted as complete.
- Replay fixtures are sanitized representative tool output based on the supplied harness query formats, not newly captured live account data.

## Deferred

Merge policy and action guards belong to their own issues. This feature supplies evidence and constrained mechanics only. No deployment, approval or protection-write capability is added.
