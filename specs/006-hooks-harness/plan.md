# Implementation Plan: Hook shims and payload harness

**Branch**: `006-hooks-harness` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Reuse `bin/wuwei`, automatic command discovery, and exit constants. Add one hook command,
a small guard package, six hook mappings, a static shell normalizer, and replay tests.

## Technical Context

Python 3.11+ standard library at runtime; pytest only for development. No state writes,
network calls, dependencies, or policy guards. Validation and dispatch tables call the hook in-process with temporary guard modules,
patched stdin, and captured output. One subprocess replay per payload fixture plus three
malformed replays exercise the executable in a temporary path with spaces and shell
metacharacters. The requested venv interpreter runs the test suite.

## Constitution Check

PASS: stdlib runtime, existing CLI reuse, test-first tasks, fail-closed boundary validation,
no duplicated policy, no secrets logged from raw payloads, no speculative configuration.
No new workspace or commits. PreCompact's reference conflict is recorded in spec assumptions.

## Structure

- `hooks/hooks.json`: exec-form `${CLAUDE_PLUGIN_ROOT}/bin/wuwei`, args `hook`, event.
- `cli/wuwei/commands/hook.py`: validation, dispatch, and documented output translation.
- `cli/wuwei/guards/__init__.py`: Guard record, module discovery, plain list result.
- `cli/wuwei/shell.py`: shlex-backed command parsing, wrapper removal, opaque predicate.
- `tests/test_hooks.py`, `tests/test_shell.py`, `tests/payloads/`: replay and table tests.

## Implementation Sequence

1. Fixtures and clean replay tests, observe failure, implement hook wiring and discovery.
2. Refusal/error/validation tests, observe failure, implement dispatch and translation.
3. Shell tables, observe failure, implement shared normalizer.
4. Run full suite and check touched files for prohibited characters and diff errors.

## Design Decisions

Registry modules expose `GUARDS = [Guard(event, matcher, check)]`, with a regex matcher or
None. Discovery skips private modules like command discovery. Every matching guard runs,
even after a failure; exceptions and invalid return values are errors. Clean messages
are only emitted for SessionStart, as structured additionalContext so JSON-looking memory
cannot accidentally be interpreted as hook decisions.

Policy refusals on blocking events exit 2 and emit structured decisions plus stderr.
PostToolUse and SessionStart failures exit 2 and report stderr. Ordinary PreCompact
failures exit 1 with stderr to preserve non-blocking behavior. Invalid payloads always
exit 2, including PreCompact, as the acceptance criterion explicitly requires.

Shell normalization returns a list of `Command(argv, subshell, env)` records. ParseError is a
ValueError subclass that guard callers translate to status 2. Recursively invoked shells
and parenthesized groups set subshell=True. Wrappers are stripped without executing
anything. Unknown wrapper options and unsupported shell syntax raise ParseError rather
than hiding commands. Keep git options intact for policy guards to interpret.

## Validation

Each behavior has a failing test before implementation. Assert exit codes, JSON structures,
messages, selection and ordering of fake guards, and argv/scope tables. Run the requested
full pytest command after all tasks. No external CLI or live Claude process is required.

## Adversarial fix round

- Restrict shim validation to the envelope; validate guard records in discover().
- Preserve explicit environments through recursive normalization and reject unresolved
  assignments. Extend launcher handling and fail closed on dynamic shell constructs.
- Parse static redirections and literal here-doc data without executing substitutions.
  Preserve background and pipeline subshell scope.
- Keep is_opaque as the shared hidden-argv and interpreter backstop; concatenated program
  names remain a documented residual covered by the policy pre-push anchor.
- Dispatch imports only the selected command module. Keep pkgutil enumeration for
  command names; top-level help imports every command to register descriptions.
  Benchmark the real hook executable over 60 runs; assert child
  CPU p95 below 50 ms locally and always print CPU and wall-clock p95, including in CI.

## Second delta review

Account for git/gh mentions structurally in normalization: exposed commands must have
literal argv, and every discarded region or unknown command is checked for mentions.
Reject input-driven launchers instead of unwrapping find or trusting xargs. Recursively
check supported shell/eval scripts, preserving the literal cat here-doc argument case.
Retain is_opaque's stdin backstop. Keep the real latency benchmark and remove its mocked
self-test; CI measurements stay advisory because of runner noise.
