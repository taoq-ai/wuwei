# Feature Specification: PR guards

**Feature**: 009-pr-guards | **Date**: 2026-09-28 | **Status**: Ready
**Source**: Issue #9, amendments #75 and #86, binding orchestrator notes.

## User Scenarios & Testing

### US1: Raise reviewed work (P1)

As an implementation seat, I can create a PR only after all three pre-PR gates
passed for the code being raised, with a reviewer requested in that action.

Acceptance:
1. Missing security evidence for HEAD refuses creation and names security.
2. Passing arch, quality and security verdict files for the same item and HEAD,
   with a named reviewer, allow creation.
3. Missing reviewer, stale or failing evidence refuses creation.
4. Gate fields written into state.json never satisfy the gate check.
5. Unreadable or malformed evidence and unavailable HEAD measurements fail closed.

### US2: Preserve merge and review boundaries (P1)

As the owner, I retain decisions the merge policy cannot clear. No profile permits
an approval, admin merge, or branch-protection write.

Acceptance:
1. Every merge goes through the merge check and reports its failed precondition.
2. Until #77 lands, merge refuses with "merge policy not available; the owner merges".
3. Approve, admin merge and protection writes refuse in strict and standard profiles.
4. Equivalent API requests have the same policy as PR commands.
5. Alias set/import/delete refuse; unknown top-level gh commands are opaque.
6. Branch-merge API writes use the merge check; API pushes to default or environment
   branches refuse. An unknown repository's default branch is unmeasured.

### US3: Enforce only relevant workspace actions (P1)

As a user with a machine-wide plugin, my unrelated commands and projects remain usable.

Acceptance:
1. Relevant wrapped commands, shell directory changes and API forms cannot bypass guards.
2. Relevant opaque interpreter commands and parse failures refuse with a reason.
3. Irrelevant tests, loops and exports pass without parsing.
4. Either an in-scope cwd or resolved target activates the guard, including configured
   repositories and worktrees. Unrelated paths remain outside scope.

## Requirements

- FR-001: Read verdict files, never state gate fields, for arch, quality and security.
- FR-002: Bind evidence to current HEAD and require a nonempty reviewer in the same action.
- FR-003: Merge calls one replaceable policy check; approval and admin overrides always refuse.
- FR-004: Normalise relevant shell commands with the shared normaliser and relevance helper.
- FR-005: Match merge, review and branch-protection API endpoints after normalisation.
- FR-006: Return 0 clean, 1 policy findings, 2 unable to inspect; errors block with a reason.
- FR-007: External tool reads go through existing ports; tests use recording fakes.
- FR-008: Init adds approval and admin-merge deny patterns through the existing
  PERMISSIONS_DENY list and settings writer.
- FR-009: PR and deploy guards share one option reader. Repeated options use the
  last value, including the method and repository short/long aliases.

## Key Entities

- Gate evidence: item, gate, Head row and Verdict row in a decision file.
- PR action: normalized command, repository context, reviewer or PR reference.
- Workspace scope: workspace root, configured repositories and their worktrees.

## Assumptions

- Use today's decisions directory, consistent with existing day-based state helpers.
- All three gates must belong to one item; do not combine unrelated item verdicts.
- Abbreviated Head rows must resolve through the VCS port to the full current SHA.
- Existing verdict lint validates complete evidence, including duplicate and blocking rows.
- Repository overrides on PR creation, opaque API input and unsupported mutations fail
  closed when they cannot be tied safely to the checked local HEAD.
- PR creation runs separately without redirections; compound commands could change
  HEAD or evidence after the guard measured them.
- Outside a workspace, a parse failure blocks only for a nonliteral cd/pushd target
  or a directory target resolving into a workspace. Dynamic gh arguments alone do
  not establish workspace scope. The fallback conservatively scans quoted scripts
  for directory candidates and uses the shared normalizer to validate those targets.
- PR creation refuses repository-selecting GIT_DIR, GIT_WORK_TREE, GIT_COMMON_DIR,
  GIT_INDEX_FILE, GIT_NAMESPACE, GIT_CONFIG*, GH_REPO, GH_HOST and GH_CONFIG_DIR.
  Other environment variables do not prevent the evidence check.
- Workspace discovery uses the existing workspace environment or ancestor convention.
  External worktrees require a discoverable workspace configuration.

## Success Criteria

- Every acceptance case has an in-process test and all three exits are exercised.
- Disabling guard registration makes the enforcement assertion fail.
- Full repository pytest suite passes without real network or code-host operations.

## Deferred

- #77 supplies the real current-head merge policy and atomic merge operation.
- Shared shell grammar and workspace discovery expansion belong to their owning issues.
  A partial-target result from #6 would permit more precise scoping of parse failures.
