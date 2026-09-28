# Implementation Plan: Repository scaffold

**Branch**: `001-scaffold` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Add a metadata-only Claude Code plugin and self-hosted marketplace, one manifest
contract test, Python test configuration, Apache licensing and CI/release workflows.
Existing main contains design and spec-kit tooling only; reuse its scripts and ignores.

## Technical Context

Python 3.11+; stdlib JSON/pathlib/re in tests, pytest as the only dev dependency.
No runtime code, storage, external adapters or build backend in this issue.
GitHub Actions runs pytest on 3.11 and 3.12. Release-please uses the simple
strategy and an extra-files JSON updater for `$.version` in plugin.json.
The simple strategy skips absent version.txt (createIfMissing is false), avoiding
another version source. Release state starts at 0.1.0 in its required manifest.
CI installs pytest directly without trying to build an absent Python package.

## Constitution Check

Before and after design: PASS. No runtime dependencies, duplicate behavior,
state writers, commands or guards. One test is written and observed failing first.
No abstractions or speculative directories. Workflow token permissions are scoped
for tests (read) and release PR creation (contents and pull requests write).
No commits, pushes, gh commands or extension hooks during this task.

## Project Structure

- `.claude-plugin/{plugin,marketplace}.json`: install contract.
- `tests/test_manifest.py`: one test for loader fields and root source.
- `pyproject.toml`: metadata and pytest settings.
- `.github/workflows/{tests,release}.yml`: checks and conventional releases.
- `release-please-config.json`, `.release-please-manifest.json`: release settings/state.
- `LICENSE`, `NOTICE`, `README.md`: license, attribution and installation stub.
- `specs/001-scaffold/{spec,plan,tasks}.md`: feature workflow artifacts.

## Validation

Run the user-specified interpreter against the manifest test before manifests exist
and confirm FileNotFoundError. Add manifests, rerun the full suite, validate both
with Claude Code, and exercise installation with isolated temporary configuration.
Parse TOML/JSON and inspect workflow triggers, matrix and permissions. Scan all new
files for prohibited characters. Actual hosted release PR creation is not claimed.

## Sources and decisions

- [Claude manifest reference](https://code.claude.com/docs/en/plugins-reference):
  use name, version, description, author and license; no absent component paths.
- [Marketplace schema](https://code.claude.com/docs/en/plugin-marketplaces):
  name, owner, plugins with name and source; omit duplicate version.
- [JSON updater](https://github.com/googleapis/release-please/blob/main/docs/customizing.md#updating-arbitrary-json-files):
  type json, path .claude-plugin/plugin.json, jsonpath $.version.
- Local ZIRAN release-please workflow/config: retain simple strategy and v-prefixed
  tags, omit publishing and branch filtering unrelated to this issue.

No separate research, data model or contracts are needed for these static files.
