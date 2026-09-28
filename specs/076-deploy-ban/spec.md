# Feature Specification: Deployment ban

**Feature Branch**: `076-deploy-ban`
**Created**: 2026-09-28
**Status**: Ready
**Input**: GitHub issue #76, feat(guards): deployment ban

## User Scenarios & Testing

### User Story 1: Refuse deployments in every profile (P1)

As the owner, I need attempted deployments refused before a tool runs, with the
matched rule named, regardless of the selected profile or shell wrapper.

Independent test: table-driven guard calls cover clean, refused, and uninspectable
commands under strict and standard profiles.

Acceptance scenarios:
1. Given `sh -c 'terraform apply -auto-approve'`, refuse naming `terraform apply`.
2. Given `git push origin v1.2.0` or `git push --tags`, refuse.
3. Given `deploy.yml` in `deploy.workflows`, refuse `gh workflow run deploy.yml`.
4. Refuse releases, tag pushes, environment branch pushes and merges, deployment
   and environment API calls, common deploy tool verbs, and custom deny patterns.
5. Read-only commands remain clean. Missing information or malformed commands
   fail closed with an explanatory exit 2.

### User Story 2: Install workspace permission denials (P1)

As the owner, I need initialization to install deployment denials in workspace
settings while preserving existing settings and the owner's global settings.

Independent test: initialize a temporary workspace and inspect its settings;
exercise malformed existing settings and verify no partial workspace is created.

## Requirements

- FR-001: PreToolUse refuses deployment commands in strict and standard profiles.
- FR-002: Inside a WUWEI workspace, parse only commands mentioning guarded or
  protected programs. Inspect normalized commands including wrappers, command
  chains, subshells, executable paths, environment assignments and options.
  Opaque git/gh mentions fail closed; deploy tool names match executable argv only.
- FR-003: Refuse configured deploying workflow dispatch/rerun, release creation,
  tags, environment branches, deployment/environment APIs and merge deployments.
- FR-004: Refuse kubectl apply/create/replace/rollout/patch/set image, helm
  install/upgrade/rollback, terraform/tofu apply/destroy, pulumi up/update,
  vercel/vc deployment (including bare invocation), netlify/ntl deploy,
  fly/flyctl deploy/launch, cloud deployment verbs (including up/start-deployment),
  docker/podman push and build/buildx build with --push or registry output.
- FR-005: `deploy.deny` extends built-in rules and cannot remove them.
- FR-006: Return 0 clean, 1 named refusal, 2 unable to inspect; errors block.
- FR-007: Initialization writes only unambiguous deployment permission denials in
  workspace settings; target-dependent decisions stay with the hook.

## Key Entities

- Deployment policy: workflow identifiers and extra command patterns.
- Environment register: branch patterns mapped to descriptions.
- Command: normalized argv, environment and subshell context.

## Assumptions

- Existing environment register keys are branch globs; values remain descriptions.
- `deploy.workflows` is a list of names, filenames, paths or IDs; filename/path
  equivalents match. Unmatched names/IDs and run IDs fail closed when workflows
  are configured, because the current code-host port cannot resolve runs/workflows.
  Distinct filenames clear only when all configured selectors are filenames.
- `deploy.deny` is a list of case-sensitive globs over normalized argv joined by
  spaces; exact command prefixes also match their arguments. Each pattern starts
  with a literal executable basename, followed by optional argument globs.
- Bare vercel deploys. Cloud deploy verbs include deploy/deployment/deployments,
  AWS create-deployment, CloudFormation stack mutations, and service/code updates.
- Explicit branch destinations, including unqualified feature branches, can be
  inspected locally. Implicit push destinations and local merge targets without a
  current-branch port fail closed. Tag-looking refs are refused explicitly.
- Outside a WUWEI workspace the guard returns 0 before parsing. Within a workspace,
  unrelated commands skip parsing; interpreter flags alone are not opaque findings.
- `repos[].merge_deploys` defaults to true; only explicit false clears a merge against
  that repository. Missing repository declarations fail closed for merges.
- Workspace settings means `.claude/settings.json` alongside `.wuwei`, never HOME.
  Static permissions cover the reviewed deploy verb list and explicit --tags pushes.
  Environment branches, workflows, API endpoints and merges remain hook decisions.

## Success Criteria

- SC-001: All named acceptance scenarios refuse with the matching rule.
- SC-002: Both profiles produce identical deployment decisions.
- SC-003: Every guard behavior has an in-process test, including exits 0/1/2.
- SC-004: Full existing and added test suite passes without network or real tools.

## Deferred

Workflow/run resolution and implicit Git destination resolution need future port
operations. Those forms block with exit 2 until their targets can be established.
The full merge policy and worktree pre-push hook belong to their own issues.
