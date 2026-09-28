# Implementation Plan: Deployment ban

Branch: `076-deploy-ban`. Specification: [spec.md](spec.md).

## Summary

Add one discovered PreToolUse Bash guard using the existing shell normalizer,
workspace configuration, code-host port and hook result translation. Extend the
normalizer's literal argument checks to deployment tools and custom executable
names from deploy.deny. Mention and opaque checks remain git/gh only. Check workspace
scope and command relevance before parsing. Initialize local Claude deny rules.

## Technical Context

Python 3.11+, stdlib-only runtime; pytest development tests. No network in tests.
Configuration remains TOML; workspace settings are JSON. No new dependencies.

## Constitution Check

Pass: reuse discovery and normalization, three-state fail-closed decisions, tests
before implementation, external reads only through registry ports, atomic settings
writes, no commits or pushes, no changes outside this worktree. No exceptions.

## Design decisions

- Add deploy.workflows/deploy.deny string arrays and repos.merge_deploys (conservative true default).
- Environment register keys match branch globs. Values stay descriptive.
- Check custom patterns on normalized argv, with exact-prefix argument support.
- Match tool verbs after global options; unsupported target-sensitive options block.
- Resolve explicit PR numbers plus repository through code_host.pr. Missing or
  unsuccessful evidence returns exit 2; never parse failed adapter results as data.
- No new port operations: implicit Git targets and workflow run IDs block when
  their deployment status cannot be proven.
- Add only unambiguous static deploy verb permissions to .claude/settings.json.
  Merge existing deny entries, preserve other settings, reject malformed settings
  or symlinks before installing the workspace, and use the existing atomic writer.

## Project Structure

- cli/wuwei/guards/deploy.py: rule matching, check, GUARDS and static denials.
- cli/wuwei/shell.py: protect literal executable arguments; no second shell parser.
- cli/wuwei/workspace.py: validated policy settings.
- cli/wuwei/commands/init.py: workspace-local permission settings.
- templates/workspace/config.toml: document policy configuration.
- tests/test_deploy.py: in-process guard, config, init and hook tables with fakes.
- tests/test_hooks.py and tests/test_workspace.py: update discovery/default expectations.

## Validation

Run failing tables before each implementation group, then focused tests. Run the
full suite with the interpreter supplied by the task. Review bypasses, adapter
errors, local/global settings isolation, and file hygiene. No extension hooks.
