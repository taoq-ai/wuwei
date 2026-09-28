# Implementation Plan: Protect state files and the workspace root

**Branch**: `010-protect-state` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Add one discovered guard module with separate file-tool and Bash checks. Reuse
`find_workspace`, `normalize` and the existing three-state hook dispatcher.
Extend the shared normalizer only where it currently discards information needed here.

## Technical Context

- Python 3.11+, stdlib runtime, pytest for development.
- No new storage, external calls, adapter changes or configuration.
- POSIX shell commands are inspected statically and never executed.
- Existing hook latency budget remains p95 under 50 ms. Workspace configuration is
  loaded only when a root is discoverable; Bash parsing runs regardless of workspace.

## Constitution Check

Pass before and after design: stdlib only; exits 0/1/2; one core implementation;
tests precede behavior changes; no new abstraction or external integration; fail closed.

## Design Decisions

- Add a defaulted `Command.writes` tuple for literal output redirection targets.
  Preserve it through wrappers, subshells, pipelines and redirection-only commands.
- Reject nonliteral arguments for cd and dynamic writer operands in the shared
  normalizer, while preserving glob-only writer arguments for guard expansion.
  Reject input-driven writer argv.
- Keep interpreter policy local to the state guard. Only snippets or arguments mentioning
  protected names are opaque; unrelated parse failures pass. Preserve NonliteralPathError
  through normalization; scope failures to state mentions, protected cwd containers
  or workspace directory changes, following the F11 assumption in spec.md.
- Resolve direct tool paths relative to payload cwd. Match resolved day/archive paths with casefold and check multiply linked files with
  samefile. Validate required relevant payload data.
- Refuse protected shell operands except known readers and source-only cp/dd/rsync.
  Preserve copy/move destination-directory checks and output redirections, including >!.
- Check file targets regardless of workspace; scan hard-link aliases only with a known root.
  Gate only directory containment on cwd being inside the workspace. Keep possible
  prior cwd values for conditional chains; refuse unknown directory forms or CDPATH searches.
  The final pipeline stage is persistent under zsh; other stages and subshells are isolated.
- Match registrations to PreToolUse Write/Edit/MultiEdit/NotebookEdit and Bash. Keep hook translation unchanged.
- Expand parsed writer globs with glob.glob(root_dir=cwd), including dd output values.
  Refuse rm/mv of state containers and workspace ancestors, check chmod/chown in
  directories mode, and refuse git apply at or inside a workspace, resolving git -C.
- Pass mode=0o444 to the shared atomic state writer. Keep events on O_APPEND, temporarily
  chmod existing files under state.lock, restore 0444 before writing, and restore on error.

## Project Structure

- `cli/wuwei/guards/protect_state.py`: guard records, payload checks and path policies.
- `cli/wuwei/shell.py`: normalized output targets and shared bypass checks.
- `tests/test_protect_state.py`: direct in-process guard tables and hook discovery replay.
- `tests/test_shell.py`: parser regression tables for new metadata and bypass failures.
- `tests/test_hooks.py`: isolate the empty-registry contract from installed guards.
- `cli/wuwei/state.py` and `tests/test_state.py`: independent read-only file-mode anchor.
- `specs/010-protect-state/contracts/guards.md`: guard exits and shell metadata contract.
- `specs/010-protect-state/`: specification, checklist, plan and task ledger.

## Validation

Run the supplied interpreter with `-m pytest -q` from the repository root. During
implementation run focused tables first and record red/green outcomes in tasks.md.
Then run the full suite, inspect the diff, and check authored files for machine paths,
emojis and em-dashes. No commits, pushes or GitHub commands.

## Deferred

See spec.md. No research or data-model file is needed: all interfaces are local and
existing, and this feature creates no persistent entities.
