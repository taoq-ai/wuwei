# Implementation Plan: Consolidation

## Technical Context

Python 3.11+ standard library runtime. Reuse `promotion`, `memory`, `workspace`, `registry` and the VCS adapter. pytest is development only.

## Constitution Check

Three-state exits, fail-closed reads, CLI-only writes, external Git through an adapter, and test-first delivery are required.

## Design

The weekly command reports note findings and archive candidates. It archives expired day directories through a dedicated function, updates the shared index, and commits changed protected paths through the producer commit path. Promotion validates the index before a fold, snapshots memory and charters, and keeps the retired note in `memory/archive`. The skill tells the owner how to schedule weekly execution.

## Files

`cli/wuwei/consolidation.py`, `commands/consolidate.py`, `promotion.py`, `workspace.py`, `adapters/vcs/git.py`, `templates/workspace/config.toml`, `skills/wuwei-consolidate/SKILL.md`, and focused tests.
