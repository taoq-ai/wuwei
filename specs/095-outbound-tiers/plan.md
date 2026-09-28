# Implementation Plan: Outbound approval tiers

**Branch**: `095-outbound-tiers` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Extend `outward.classify`, retaining the existing `(code, send|draft)` contract and
adding destination context. Keep `check_call` as the hook/adapter policy seam;
classify before lint. Add a thin `outbound tier` stdin-JSON command.

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests. Config is existing TOML
schema/default machinery. No new runtime dependencies or persistent state. Use
`registry.load('vcs'|'code_host', config)` for commit and PR evidence. Tests use
in-process fakes and CLI entry functions, never real network/tool reads.

## Constitution Check

Before and after design: stdlib only, three-state fail-closed exits, shared policy,
test first, no logs of text, no approval tokens, no subprocess imports in core.
No gate exceptions. The current branch is already an isolated worktree.

## Design and Research Decisions

- Add `outbound` config for work/external channels, company domains, code-host orgs,
  people mapping, sensitive keywords and sensitive/commitment/disagreement patterns.
- Use existing normalized Unicode text and full-message allow forms. PR technical
  forms require a subject observed in the discussion, not caller-provided tier labels.
- Keep all audience evidence restrictive: contradictory/external evidence beats work
  channel status. Unknown mentions and identities draft.
- Resolve team PRs and participants through existing `pr`, `reviews` and `threads` ports. Verify
  repository/number and reject incomplete or malformed evidence. Preserve VCS SHA checks.
- Route CLI JSON using the same payload shape accepted by shared policy. Document it
  in contracts/outbound.md, along with conservative classification limitations.
- Apply guard scope using workspace, configured repo paths and native worktree anchors;
  share the scope helper in workspace.py and match tool relevance first. Extend
  protect-state to cover config.toml using existing normalized target checks.
- #85 voice module is absent. Keep existing lint call intact for future integration.

## Project Structure

- `cli/wuwei/outward.py`: shared destination and message classification, payload checks.
- `cli/wuwei/workspace.py`: validated outbound defaults.
- `cli/wuwei/guards/outward.py`: scope and shared policy routing.
- `cli/wuwei/registry.py`: identify DM operations at the port boundary.
- `cli/wuwei/commands/outbound.py`: thin CLI tier command.
- `templates/workspace/config.toml`: documented opt-in configuration.
- `tests/test_outbound.py`: acceptance, precedence, evidence, integration and scope tables.
- `tests/test_outward.py`: migrate old unconditional-send expectations to destination rules.

## Validation

For each task, run new tests to an expected failure, then implement and rerun. Finish
with the full suite using the task-specified interpreter, `git diff --check`, and a
scan of changed files for forbidden characters and machine-local paths.
