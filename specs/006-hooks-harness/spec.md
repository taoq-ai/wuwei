# Feature Specification: Hook shims and payload harness

**Feature Branch**: `006-hooks-harness`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #6, milestone M1 Guards, depends on #2 and #4.

## User Scenarios & Testing

### User Story 1 - Enforce hook decisions (Priority: P1)

As an operator, I need every supported lifecycle hook to run all applicable guards and
report their decisions in the format Claude Code understands.

**Independent Test**: Pipe each fixture through the configured executable, with fake
guards returning clean, findings, and could-not-run results.

**Acceptance Scenarios**:

1. Given each recorded or documented payload, when its shim runs, then it returns the
   expected allow or block and message.
2. Given multiple matching guards, when any refuse, then all refusing reasons appear.
3. Given clean guards, when SessionStart runs, then their context reaches Claude.
4. Given an event that must not block, when a guard refuses, then the reason is visible
   through that event's documented reporting channel.

### User Story 2 - Fail closed on unusable input (Priority: P1)

As an operator, I need malformed input and broken guards to be reported instead of
silently granting permission.

**Independent Test**: Pipe malformed JSON, missing or mistyped required fields, mismatched
events, and valid inputs with throwing guards through the shim.

**Acceptance Scenarios**:

1. Given a malformed payload, when the shim runs, then it exits 2 with a blocking reason.
2. Given a guard that cannot run, when the hook runs, then it reports the failure and still
   runs other matching guards.

### User Story 3 - Recognize wrapped shell commands (Priority: P1)

As a guard author, I need one shared normalizer so shell wrappers do not hide commands.

**Independent Test**: Table-test separators, recursive shell invocations, wrappers,
subshell scope, interpreter snippets, and malformed quotes without executing commands.

**Acceptance Scenarios**:

1. Given a wrapped command, when normalized, then guards see its component argument lists
   in order with their subshell status.
2. Given unbalanced quotes, when normalized, then a parse error is returned to the caller.
3. Given any git/gh mention not accounted for by an exposed literal git/gh command,
   then normalization raises ParseError and the guard blocks with exit 2.

### Edge Cases

Unknown tool names remain extensible. Empty registry allows valid input. Empty content
and replacement strings are valid. Stop's active flag is passed to guards without bypassing
them. All guards run even after a refusal. Quoted separators remain arguments.

## Requirements

### Functional Requirements

- FR-001: Configure exactly PreToolUse, PostToolUse, SubagentStop, SessionStart, PreCompact,
  and Stop, using the existing executable shim and plugin path substitution.
- FR-002: Validate only the common envelope (object, common nonempty string fields,
  matching event). Event and tool fields belong to consuming guards; a missing key
  inside a guard fails closed. Preserve extra fields for future guards.
- FR-003: Discover guard modules with the existing command-discovery pattern; each exposes
  a plain GUARDS list of event, tool matcher, and check records. Ship no policy guards.
- FR-004: Run all matching checks; join refusal reasons; map findings and errors to
  documented hook output, preserving fail-closed behavior.
- FR-005: Keep fixture provenance explicit; only SessionStart is a live recording.
- FR-006: Normalize shell separators (including background commands), nested shell -c,
  eval, and supported wrappers. Preserve prefix and nested env
  assignments on Command.env, subshell scope, and guarded argv. Reject unsupported
  syntax, dynamic guarded arguments, ANSI-C quoting, and shell mutation builtins.
- FR-007: Runtime remains Python 3.11+ stdlib only; tests need no network or external tools.
- FR-008: Drop static redirection targets and quoted-delimiter here-doc bodies only
  after checking them for unaccounted git/gh mentions. Here-doc bodies owned by a
  plain git or gh command are data and exempt from that check. A double-quoted substitution containing only cat with a quoted-delimiter
  here-doc becomes the literal output (trailing newlines removed); other substitutions
  fail closed.
- FR-009: Every `(?<![.\w])(?:git|gh)\b` mention, including spellings decoded or
  stripped of quotes and backslashes, must
  belong to an exposed Command with program basename git or gh and fully literal
  argument words. Reject unquoted `$`, backticks, brace expansion (`,` or `..`
  inside braces), `*`, `?`, and `[` in those
  words (and expansions inside double quotes). Reject mentions in discarded text,
  environment assignments, interpreter code, unknown launchers, xargs, parallel, and
  find execution actions. Known wrappers may expose literal commands recursively.
  The literal body of `git commit -m "$(cat <<'EOF' ... EOF)"` is an accounted argument.
  ParseError tells the agent to run git or gh as a plain command; guards translate it
  to exit 2. Keep is_opaque as a backstop, including interpreters reading stdin or
  lacking a snippet and a script path.
- FR-010: Import all command modules for top-level `--help`/`-h` so their help strings
  show; every other invocation imports only the invoked command module. Measure Bash hook
  latency over 60 subprocess runs; enforce the owner's p95 below 50 ms requirement
  outside CI on child CPU time (user plus system, per-run RUSAGE_CHILDREN deltas).
  Wall-clock time depends on host load, so report both CPU and wall-clock p95 on
  every run. CI only prints the measurement because of runner noise; the p95 assertion
  runs locally. Keep the full suite below 10 seconds on this host.

### Key Entities

- Hook payload: common envelope, event-specific data, and unchanged extra fields.
- Guard record: event, tool-name matcher, and callable returning status and message.
- Normalized command: argument list, explicit environment assignments, and whether
  execution changes only a subshell's cwd.

## Success Criteria

- SC-001: All six shims pass fixture replay for clean, finding, and error outcomes.
- SC-002: Every malformed-input case returns exit 2 with a reason.
- SC-003: Every specified shell bypass form has a passing table test.
- SC-004: The full existing suite passes with the required interpreter.

## Assumptions

- The supplied hook reference is authoritative for field names and output channels.
- Ordinary PreCompact findings must not block, per binding notes and design section 4.1.
  The supplied newer reference does allow PreCompact blocking: malformed input still
  exits 2 as explicitly required and may therefore block compaction. Ordinary findings
  use a non-blocking error status with stderr. This conflict is surfaced, not hidden.
- Common required strings are session_id, transcript_path, cwd, and hook_event_name.
  permission_mode, prompt_id, model, and other documented optional metadata are optional.
- Matchers are regular expressions over the complete tool name; None matches any tool
  and lifecycle events. A plain list of small immutable records is sufficient.
- Shell parsing is static analysis, never execution or variable expansion. Unsupported
  shell constructs fail with a parse error rather than being silently treated as safe.
- Fake guards are installed on temporary package paths for in-process tables. Full
  subprocess fixture replays use temporary plugin copies.

## Deferred

Real policy guards, memory injection, tracing, state flushes, and stop obligations belong
to later issues. Registry enumeration belongs to #18. Git/gh flag and API semantics belong
to #8/#9/#10. Replace documented fixtures with live recordings when capture is available.

## Review assumptions and residuals

- The owner supplied the adversarial cases and explicitly approved the latency budget.
  The supported grammar exposes guarded argv or fails closed; it does not execute shell
  code or resolve variables. Dynamic environment assignments are rejected too.
- String concatenation in interpreter code (for example "gi" + "t") remains a documented
  detection residual. The repository pre-push hook is the enforcement anchor; implementing
  that hook belongs to the policy guard issue, not this harness.
- F11 remains deferred: headless Claude cannot authenticate on this host.
- R1 deliberately accepts false positives: `echo "git push"`, comments, filenames,
  environment values, and ordinary here-doc bodies mentioning git/gh fail closed.
  Dot-prefixed names such as `.git` and here-doc data owned by plain git/gh are exempt.
  Quote-fragment concatenation and line continuations that could erase a mention in
  a nested script also fail closed. Earlier allow rows for these cases now assert
  ParseError; the cases remain covered. Interpreters with options before a potential
  script path are conservatively opaque because option operands can resemble paths.
