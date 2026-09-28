# Implementation Plan: Verdict lint and retro capture

**Branch**: `013-verdict-lint` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Port the production shell checks into a shared verdict module, retain diagnostic
order, and add per-finding severity and quality rows. A thin CLI and a discovered
Write/Edit/MultiEdit/NotebookEdit/Bash guard call the same lint. SubagentStop
captures charter-role retro events and evidence through existing state and atomic writers.

## Technical Context

- Python 3.11+, stdlib only; pytest for development.
- Storage: existing workspace day directory, events.jsonl, retro/.
- POSIX CLI and hooks; in-process tests, no network or external tool dependencies.
- Preserve the existing hook translation: guard exits 1/2 become hook exit 2.
- Scan the day's gate files independently of shell syntax. Retain a conservative
  literal interpreter refusal; no subprocess imports or adapters needed.

## Constitution Check

Pre-design and post-design: pass. Test-first work covers each behavior; shared
writers preserve append-only events and atomic artifacts. The common charter names
the Head row and class-sweep scope. No engagement-specific identifiers, new dependencies or speculative abstractions.

## Design Decisions

- Read the saved file for both Write and Edit; check lexical and resolved paths
  so a symlink alias cannot hide a gate file or its quality identity.
- Strip fenced samples, blockquotes and HTML comments before matching evidence.
- Preserve legacy document checks first; validate severity-led finding blocks after
  legacy checks. Explicitly reject duplicate verdict/retro/quality rows.
- Capture only final assistant text. Save a content-addressed retro JSON record
  then append the event. Active stop-hook retries record gaps without blocking again.
  Persistence failures return 2; artifact retries are safe and events append-only.
- Changes stay in retro records; the steward writes real proposals under #81.
- Scope verdict checks to a WUWEI workspace found from cwd or a file target;
  retro capture needs workspace cwd or WUWEI_WORKSPACE and a charter role.
  Bash commands mentioning gate- and sentinel SubagentStop both scan the day's
  decisions directory. Stop retries record rejections and return 0.
  File lint and relevant guard refusals append verdict.rejected through the shared writer.
- Existing hook harness tests isolate synthetic guard modules; replay the original
  recorded payloads unchanged to check that unrelated sessions pass.

## Project Structure

- `cli/wuwei/verdict.py`: shared text parsing and lint/file entry point.
- `cli/wuwei/commands/verdict.py`: `bin/wuwei verdict lint FILE [--role ROLE]`.
- `cli/wuwei/guards/verdict.py`: write and sentinel-stop verdict checks, retro persistence.
- `tests/test_verdict.py`: source parity, added lint, CLI and write guard tables.
- `tests/test_retro.py`: retro extraction, events, retained changes and hook mutations.
- `tests/test_hooks.py`: preserve real-shim coverage with new guard requirements.
- `contracts/verdict.md`: CLI, hook and retro persistence contract.

## Validation

For each task: write tests, observe expected failure, implement, run focused tests.
Then run the full suite with the interpreter supplied in the task, inspect the diff
and check changed files for machine paths, em-dashes and emojis. No commits or pushes.
