# Feature Specification: Codex plugin spike

**Feature Branch**: `261-codex-plugin-spike`
**Created**: 2026-09-30
**Status**: Ready
**Input**: GitHub issue #261, "spike(codex): what a WUWEI plugin for Codex needs: hook contract, tool map, packaging, planner without the Agent tool"

## User Scenarios & Testing

### User Story 1 - Decide whether to port WUWEI to Codex (Priority: P1)

The owner reads one document and decides port, partial port or not now, knowing which
claims rest on current Codex documentation or CLI output and which are unverified.

**Acceptance Scenarios**:

1. Given the document, then every hook and tool row of the gap table cites the Codex doc
   or CLI output it rests on, and unverified rows are marked as such.
2. Given the recommendation, then it names what the enforcement story would lose if Codex
   hooks cannot block a tool call before it runs.
3. Given the diff, then only the spike document and its spec-kit artifacts changed.

### User Story 2 - File the follow-up work (Priority: P2)

If the answer is port, the owner files the follow-up issues the document lists, each
sized in the milestone's terms.

**Acceptance Scenarios**:

1. Given the recommendation is a port or partial port, then the document lists follow-up
   issues with a conventional-commit title, scope and size.

## Edge Cases

- A Codex documentation page redirects: the redirect target is cited, not the old URL.
- A source cannot be fetched: the claim resting on it is marked unverified.
- Codex documents a behaviour that current issues contradict (hooks under `codex exec`):
  both are cited and the consequence follows the observed behaviour.

## Requirements

### Functional Requirements

- **FR-001**: The document `docs/specs/2026-09-30-codex-plugin-spike.md` must map each
  WUWEI hook in `hooks/hooks.json` (PreToolUse, PostToolUse, SessionStart, Stop,
  SubagentStop, PreCompact) to a Codex event or to "no equivalent" with the consequence.
- **FR-002**: It must map the tool names the guards key on (Bash, Write, Edit, MultiEdit,
  NotebookEdit, Agent, AskUserQuestion, MCP) to Codex tools, including how file guards
  would extract targets from an `apply_patch` body.
- **FR-003**: It must state what replaces `.claude-plugin/plugin.json`, `hooks.json`, the
  marketplace, `permissions.deny`, the statusLine and `CLAUDE.md`, and how the signed
  manifest and `wuwei init` fit Codex packaging.
- **FR-004**: It must describe how seat launches map to the existing Codex runtime adapter
  and what the daily path loses without the Agent tool.
- **FR-005**: It must contain a gap table (feature, Claude Code mechanism, Codex mechanism
  or none, consequence, size, source), a recommendation with its reason, and follow-up
  issues.
- **FR-006**: Every source carries its URL or CLI command and the date fetched or run.
- **FR-007**: No runtime code, test, hook, skill or template changes.

## Success Criteria

- The document is under 1500 words.
- Every gap-table row has a non-empty source cell.
- `python -m pytest -q` passes with no new or changed test.
- The files changed are the spike document and `specs/261-codex-plugin-spike/` only.

## Assumptions

- The notes for this issue assign the spike document to the spec author; the builder
  checks it against the acceptance and runs the suite. The document is already written in
  this change.
- No pytest test is added: the issue's third acceptance scenario allows only the spike
  document and spec-kit artifacts in the diff. Acceptance is checked with the read-only
  commands in `tasks.md`; the existing `tests/test_hygiene.py` covers machine paths.
- "Sized in the same terms as this milestone's issues": milestone issues carry no explicit
  size field, so the document defines S, M and L by track and scope (one file, one adapter
  or several guards, a launch-contract change).
- Codex 0.156.1 is the installed version; the open issues cited were reported against
  nearby versions (0.144.1, 0.157.1) and are taken to apply.
- The issue premise that Agent has no counterpart is corrected: Codex exposes
  `spawn_agent` and related tools, but their input shape is undocumented, so the launch
  guard mapping is recorded as unverified.
- The owner request to create a spike as another issue is this issue; no further issue is
  filed from here (no `gh`).
