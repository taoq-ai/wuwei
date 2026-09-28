# Implementation Plan: Versioned charter upgrade

**Branch**: `040-charter-upgrade` | **Date**: 2026-09-28 | **Spec**: `specs/040-charter-upgrade/spec.md`

## Summary

Extend the existing `init` command with upgrade and dry run flags. Validate the existing TOML with the shared schema before planning changes. Insert only absent template keys into their matching sections, preserving owner text. Compare local and shipped charter frontmatter versions. Write changed files through the shared atomic writer and print the updated status line.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib only
**Storage**: `.wuwei/config.toml`, `.wuwei/executable`, local charter files
**Testing**: pytest, focused tests then full suite
**Target Platform**: local CLI on macOS and Linux
**Constraints**: no external tool calls; three-state exits; no lost owner data

## Constitution Check

- Runtime uses stdlib only: pass.
- Validation errors fail closed: pass by validating before writes.
- Shared atomic writer handles mutations: pass.
- Each behavior gets a failing test first: required during implementation.
- Scope remains `init` and workspace configuration: pass.

## Project Structure

- `cli/wuwei/commands/init.py`: command flags, plan and apply.
- `cli/wuwei/workspace.py`: existing validation and atomic writer reused.
- `tests/test_workspace.py`: previous template fixture and upgrade cases.

## Design

Read and validate all inputs before writing. Treat TOML as text to preserve owner formatting and comments; use parsed data only to identify absent keys. Copy default assignment lines and their template comments into their sections. For missing sections, copy the whole section. Parse the result and compare every existing owner value before applying it; refuse layouts whose values would change. For local charter overrides, compare frontmatter versions by name and report differing or missing stamps. Atomic rename protects each written file; the config write precedes pointer write so retry completes an interrupted upgrade.
