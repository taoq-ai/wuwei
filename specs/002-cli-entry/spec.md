# Feature Specification: CLI entry point

**Feature Branch**: `002-cli-entry`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #2, feat(cli): wuwei entry point with the three-state exit contract

## User Scenarios & Testing

### User Story 1 - Trust command outcomes (Priority: P1)

Callers can distinguish clean execution, findings, and inability to run.

**Why this priority**: Automation must never mistake a failed command for success.
**Independent Test**: Run test-only commands and inspect process status and stderr.

**Acceptance Scenarios**:

1. **Given** a command that raises, **When** invoked, **Then** the process exits 2 and prints the command and reason to stderr.
2. **Given** a command returning 0, 1, or 2, **When** invoked, **Then** that status reaches the caller unchanged.
3. **Given** an invalid return value, **When** invoked, **Then** the process exits 2 with the command and reason.
4. **Given** a newly supplied subcommand, **When** invoked with arguments, **Then** it is available without changes to a shared command list.

### User Story 2 - Invoke the installed CLI (Priority: P2)

Users can inspect the installed plugin version from any working directory.

**Why this priority**: A stable entry point lets hooks and users call the same CLI.
**Independent Test**: Run both entry points from an unrelated directory.

**Acceptance Scenarios**:

1. **Given** the installed plugin, **When** `wuwei --version` runs, **Then** it prints the plugin version and exits 0.
2. **Given** either supported entry point, **When** help is requested, **Then** help is printed with exit 0.
3. **Given** missing or unknown commands or malformed arguments, **When** invoked, **Then** usage and the reason are printed with exit 2.

### User Story 3 - Run without third-party packages (Priority: P2)

The CLI works with the Python standard library alone.

**Why this priority**: Plugin installation must not require runtime package installation.
**Independent Test**: Statically inspect all runtime imports and run CLI subprocesses without site packages.

**Acceptance Scenarios**:

1. **Given** runtime sources, **When** imports are audited, **Then** every top-level imported module belongs to the standard library or WUWEI.

### Edge Cases

- Reject non-integer results, booleans, and integers outside 0, 1, 2.
- Command-initiated SystemExit and KeyboardInterrupt fail closed; argparse's own help and usage exits remain unchanged.
- Missing or malformed version metadata and command registration errors report exit 2.
- The shell entry point handles installation paths with spaces and preserves arguments.

## Requirements

### Functional Requirements

- **FR-001**: Provide module and shell entry points without third-party runtime imports.
- **FR-002**: Share one definition of the three exit statuses across commands.
- **FR-003**: Discover independently registered subcommands and forward parsed arguments.
- **FR-004**: Convert command exceptions and invalid results to exit 2 with command and reason on stderr.
- **FR-005**: Read version from the installed plugin manifest and print it with exit 0.
- **FR-006**: Support standard help and usage errors.
- **FR-007**: Enforce the runtime dependency rule with a static import test.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All three valid outcomes are preserved and every tested command failure exits 2.
- **SC-002**: Both entry points report the installed version from unrelated directories.
- **SC-003**: The runtime import audit finds zero third-party imports.

## Assumptions

- Binding orchestrator invocation `PYTHONPATH=<plugin root>/cli python3 -m wuwei` supersedes the issue's directory-before-`-m` spelling.
- Version output is the manifest version alone, followed by a newline.
- The shim requires POSIX sh and Python 3.11+ on PATH; symlink installations are outside this issue.
- Commands return integer statuses; booleans are rejected despite being integer subclasses.
- A command returning 2 supplies its own reason; the dispatcher explains failures it catches.
- No production subcommand is needed for this foundation issue.

## Deferred

Business commands, guards, sweeps, adapters, and workspace state belong to later issues.
