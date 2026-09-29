# Implementation Plan: Checkout install integrity

**Branch**: `165-install-integrity` | **Date**: 2026-09-29
**Spec**: [spec.md](spec.md)

## Summary

Extend the existing integrity core with one checkout evidence helper using
`registry.load('vcs', config)` and its existing `head` and `status` operations.
Store checkout evidence alongside the content fingerprint in protected confirmations
and verdicts. Validate it on cached reads. Leave the signed verification path intact.

## Technical Context

- Python 3.11+, stdlib runtime, pytest development tests.
- Existing atomic JSON writers under `.wuwei/integrity/` and host TTY confirmation.
- Existing in-process VCS fake and hook table tests; no new port or configuration.
- Signed releases retain cheap cached reads. Checkout reads need HEAD and status
  through the adapter; no full content inventory per tool call.
- README, docs/site/index.md and marketplace metadata are the documentation scope.

## Constitution Check

Pass before and after design: stdlib only, fail closed, one shared implementation,
red before green, existing producer protection and scope helpers reused. No exceptions.

## Investigation and Design

A read-only replay of the operator workspace, redirecting verdict writes to memory,
reproduced a missing-manifest finding and PreToolUse exit 2 on `ls`. The saved verdict
had already been clean; no evidence files or probe scripts were executed or changed.
The existing reconfirmation pins only content; cached reads do not inspect checkout
HEAD or status. Reuse both existing VCS reads rather than adding a checkout adapter.

Checkout detection requires its own `.git` entry and absent release artifacts.
Missing or partial signed assets retain existing verification behavior. For checkouts,
validate the full SHA and status list, record `{head, clean}`, and include that evidence
in the content fingerprint. Dirty evidence produces a finding without a confirmable
fingerprint. Reconfirmation remeasures after terminal input, rejecting commit or
content changes. Cached checkout reads compare current clean evidence with the verdict
and fail closed on changes or errors. Legacy confirmations cannot match the new evidence.

## Project Structure

- `cli/wuwei/integrity.py`: shared measurement, checkout evidence and cache handling.
- `tests/test_integrity.py`: fake-backed lifecycle, failure and scope tables.
- `tests/test_docs.py`: release installation and marketplace documentation regression.
- `README.md`, `docs/site/index.md`, `.claude-plugin/marketplace.json`: installation.
- `specs/165-install-integrity/`: spec, quality checklist, plan and ordered tasks.

## Validation

Run failing checkout lifecycle and failure table tests first, implement the core, then
run focused integrity tests. Add failing documentation assertions before updating the
entry guides. Run the full suite with the user-specified interpreter and inspect the
diff for unintended changes, local paths, em dashes and emojis. Existing signed-release,
protection, adapter and scope tests remain the regression boundary.
