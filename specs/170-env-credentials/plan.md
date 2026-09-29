# Implementation Plan: Workspace credentials

## Summary

Load literal workspace env values at the shared CLI boundary and after hook scope
resolution. Reuse the redactor for known credential values, the JSONL writer for
events/traces, atomic writes for provisioning, and the GitHub adapter for auth.
Add a credentials section to config check and document requirements.

## Technical Context

Python 3.11+, stdlib only, pytest for development. Existing POSIX filesystem and
adapter subprocess boundaries remain. No new dependencies or config keys.

## Constitution Check

Pass: tests precede behavior, subprocesses stay in adapters, private diagnostics,
three-state exits, shared scope helpers, no new trusted state or producer kinds.

## Design and Structure

- cli/wuwei/env.py: bounded, validated literal env loading and empty-file provisioning.
- cli/wuwei/__main__.py: load for ordinary CLI commands and redact stdout/stderr.
- cli/wuwei/commands/hook.py: resolve payload scope before loading env.
- cli/wuwei/guards/protect_state.py: protect env with existing configuration paths.
- cli/wuwei/redact.py and state.py: redact known values before truncation or JSON encoding.
- cli/wuwei/commands/init.py: create env and ignore rule for init and upgrade.
- cli/wuwei/commands/config.py: report local requirements and adapter auth status.
- adapters/code_host/github.py and registry.py: fixed auth_status port operation.
- tests/test_env_credentials.py: in-process behavior tests and entry-point smoke checks.
- tests/test_workspace.py: use a fake GitHub auth tool for existing config checks.
- docs/site/adapters.md and configuration.md: file format, precedence and requirements.

## Evidence

Read-only operator dry-run reproduction: no workspace env file, config check exit
0, LINEAR_API_KEY lookup fails, 142 existing events with no credential diagnostic.
The supplied hook probe writes files and events, so it was inspected, not executed.

## Validation

For each behavior, run the new failing tests, implement, and rerun. Use fake HTTP
responses and subprocess functions only. Verify a rendered watch plist reaches
bin/wuwei, module invocation uses -P, hook payload cwd controls scope, and private
values never appear in output, events, traces or refusal messages. Run the full
suite with the task's interpreter and inspect whitespace and local-path hygiene.

## Deferred

None. Keep the existing calendar.url runtime fallback for compatibility.
