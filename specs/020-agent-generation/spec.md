# Feature Specification: Agent generation from charters

**Feature Branch**: `020-agent-generation`
**Created**: 2026-09-28
**Status**: Draft
**Input**: Issue #20, generate Claude Code plugin agents from role charters and explicit tool allowlists.

## User Scenarios and Testing

### User Story 1: Build role agents (Priority: P1)

A plugin maintainer runs `wuwei agents build` to regenerate nine agent files after a charter or allowlist edit.

**Independent Test**: In a fixture plugin, build produces one agent per role with Claude Code frontmatter (`name`, `description`, `tools`) and the shared and role charter bodies in order.

**Acceptance Scenarios**:
1. Given the nine versioned charters and complete allowlist, when build runs, then all nine role agents are written atomically.
2. Given any generated agent, then its `tools` field explicitly lists its allowed tools and its body contains `_common.md`, the role charter, and `_common-authoring.md` for authoring roles.
3. Given an unreadable or invalid source, build exits 2 with a reason rather than writing an unrestricted agent.

### User Story 2: Detect generated drift (Priority: P1)

A reviewer or CI run uses `wuwei agents check` to detect stale or missing generated agents.

**Independent Test**: Changing a charter without rebuilding makes the golden pytest test fail; rebuilding restores it.

**Acceptance Scenarios**:
1. Given a charter edit without regeneration, then CI fails.
2. Given matching generated agents, check exits 0; given missing, stale or extra agent files, check exits 1.
3. Given malformed or unreadable sources, check exits 2 with a reason.

## Requirements

- FR-001: Source role bodies only from the nine `charters/<role>.md` files and shared common charters.
- FR-002: `agents/allowlist.json` maps every role to an explicit, nonempty list of supported tools. No role may use a wildcard or unrestricted list.
- FR-003: Document the least-privilege rationale for each role in `agents/README.md`.
- FR-004: Build uses the existing atomic writer. Check is read only and compares full generated content and role file set.
- FR-005: CI's pytest suite contains a golden drift test.

## Assumptions

- The nine roles and their charters from issue #19 are the complete generation set for this issue.
- Planner, lead, builder and shepherd author work; sentinels author verdicts; steward authors steering, retro and proposals. All roles receive `_common-authoring.md` because each writes an artifact.
- Claude Code agent `tools` values use a comma-separated list of built-in tool names. `Bash` is needed for CLI, tests, and configured adapters; workspace hooks remain the action boundary.
- No role-specific `model` is set here because day seat policy selects runtime and model.

## Success Criteria

- The full pytest suite passes with the golden test included.
- Every generated agent has an explicit `tools` field and the least-privilege matrix is documented.

## Deferred

ZIRAN's independent tool matrix audit and CI scanner integration belong to issue #36. Runtime command/path enforcement remains with the existing and subsequent guard issues.
