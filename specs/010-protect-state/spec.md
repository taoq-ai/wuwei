# Feature Specification: Protect state files and the workspace root

**Feature Branch**: `010-protect-state`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #10 and its amendment referencing design sections 4.1 and 4.5.

## User Scenarios & Testing

### User Story 1 - Preserve CLI ownership of state (Priority: P1)

As an owner, I need direct state edits refused so the CLI remains the only state writer.

**Why this priority**: Direct edits bypass validation and event recording.
**Independent Test**: Table tests submit tool payloads and check clean, refusal and error exits.

**Acceptance Scenarios**:

1. **Given** an Edit on `.wuwei/days/*/state.json`, **When** the guard runs, **Then** it refuses and directs the caller to the CLI.
2. **Given** Write or Edit on `events.jsonl` for any day, **When** the guard runs, **Then** it refuses.
3. **Given** a Bash write using redirection, tee, cp, mv, sed -i, dd or truncate, including supported wrappers, **When** its target is protected, **Then** it refuses.
4. **Given** a relevant opaque interpreter write or uninspectable command, **When** the guard runs, **Then** it blocks with an error reason.
5. **Given** an ordinary file write, state read or CLI state operation, **When** the guard runs, **Then** it allows the action.

### User Story 2 - Keep the persistent shell in the workspace (Priority: P1)

As an owner, I need persistent directory changes contained within the workspace.

**Why this priority**: Subsequent actions must retain the intended workspace context.
**Independent Test**: Table tests compare top-level and subshell directory changes.

**Acceptance Scenarios**:

1. **Given** `cd /other/repo && git status`, **When** the guard runs, **Then** it refuses with a `git -C` or subshell alternative.
2. **Given** `(cd /other/repo && git status)`, **When** the guard runs, **Then** it allows the action.
3. **Given** a top-level cd within the workspace, **When** the guard runs, **Then** it allows the action.
4. **Given** an unknown directory destination or malformed payload inside a workspace, **When** a directory check is needed, **Then** it returns an error and blocks.

### Edge Cases

- Relative paths, quoted paths, symlinks, dot segments and workspace prefix siblings.
- Output-only shell commands, redirections on wrappers and subshells, append and read/write redirections.
- Nested shell wrappers, environment assignments, input-driven commands and dynamic arguments.
- Chained directory changes, HOME, OLDPWD and CDPATH behavior.

## Requirements

### Functional Requirements

- **FR-001**: Refuse Write/Edit/MultiEdit/NotebookEdit targets resolving to `.wuwei/days/*/state.json`, `.wuwei/days/*/events.jsonl`, or `.wuwei/archive/` contents, including case variants and hard-link aliases.
- **FR-002**: Refuse commands with protected path arguments unless they are known readers (cat, head, tail, less, jq, grep, wc, sed without -i, and source-only cp/dd/rsync). Refuse protected output redirections; subshells do not exempt state writes.
- **FR-003**: Refuse persistent cd/pushd/popd outside the root containing `.wuwei`, respecting the existing trusted workspace override.
- **FR-004**: Preserve shell parsing hints on exit 2 for relevant input regardless of workspace. Unrelated parse failures return exit 0. Known violations return exit 1.
- **FR-005**: Register through the existing guard discovery and hook translation contract.
- **FR-006**: Perform no state writes or external tool calls during guard evaluation.
- **FR-007**: Refuse rm and mv sources naming `.wuwei`, day containers, workspace roots or their ancestors. Check chmod/chown operands in directories mode. Refuse git apply with effective cwd (including git -C) at or inside a workspace.
- **FR-008**: The CLI leaves state.json and events.jsonl at mode 0444 after each write. Set the state temporary file mode before rename; open events with O_APPEND after temporary chmod under the existing lock and restore 0444 before appending.

## Success Criteria

- **SC-001**: Every acceptance and supported bypass case is refused or allowed as specified by in-process tests.
- **SC-002**: All malformed or unsupported relevant inputs block with a nonempty reason.
- **SC-003**: The full existing test suite passes with the new guards installed.

## Assumptions

- Ordinary state.json and events.jsonl files outside the protected resolved path patterns are allowed, including not-yet-created paths.
- Workspace means the root containing `.wuwei`, not the `.wuwei` directory itself.
- The hook process environment is trusted; command-local WUWEI_WORKSPACE cannot redefine the boundary.
- Resolve filesystem symlinks and casefold path names regardless of cwd or WUWEI_WORKSPACE. Scan hard-link aliases only when a workspace root is known. Only directory containment requires cwd inside the workspace.
- Parse failures block when raw text mentions state.json, events.jsonl, .wuwei or matches `\.w[\w*?\[]`; inside a workspace, cd/pushd/popd also remain relevant. Nonliteral paths and dynamic writes also block when cwd is a protected state container with a discoverable workspace. Interpreter snippets or arguments mentioning protected names remain opaque for this guard.
- F11's explicit ordinary-command allow examples take precedence over interpreting workspace discovery alone as sufficient to block dynamic writes. At the workspace root and ordinary subdirectories, opaque commands without state mentions pass. Hidden dynamic destinations remain a static-analysis residual bounded by the independent 0444 anchor.
- Preserve glob-only writer operands in the parser. Expand ln, install, rsync, rm, cp, mv, tee, truncate, sed and dd output globs relative to each possible cwd. Normalized argv loses quote metadata, so quoted glob strings are conservatively checked too.
- The final pipeline stage can change the persistent cwd under zsh; earlier stages and explicit subshells cannot.
- Conditional cd chains retain every possible prior directory for conservative checks because normalized commands omit control-flow operators.

## Deferred

- General script analysis remains outside scope. The shared parser is static, not an operating-system sandbox. Unknown inherited directory stacks fail closed for persistent popd.
- git apply outside a workspace can carry protected destinations in patch contents and remains a residual. Mode 0444 prevents ordinary overwrites by non-root users, but owners can chmod or replace files; it is an independent guardrail, not a sandbox.
