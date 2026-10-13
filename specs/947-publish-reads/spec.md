# Feature Specification: Publish reads and exact command approval

**Feature Branch**: `947-publish-reads`
**Created**: 2026-10-13
**Status**: Ready
**Input**: GitHub issue #947, false owner cards for deployment reads.

## User Scenarios & Testing

### User Story 1 - Read deployment metadata (Priority: P1)

A planner or seat lists deployment metadata without interrupting the owner.
**Why this priority**: The reported commands do not change remote state.
**Independent Test**: Both field commands pass the publish guard without a card.

**Acceptance Scenarios**:

1. Given a workspace, when `vercel env ls production` runs, then it passes without a card.
2. Given a workspace, when `gh api "repos/org/repo/deployments?per_page=100"` runs, then it passes without a card.
3. Given deployment or environment endpoints, an implicit or explicit GET without fields or input passes; POST still requires the owner.
4. Given Vercel, `env ls`, `ls` and `inspect` pass; deployment and environment mutations still require the owner.

### User Story 2 - Understand the approved command (Priority: P1)

The planner reads the write card and knows to run the exact command alone.
**Why this priority**: Corrected options and compound commands need new approval.
**Independent Test**: A write card description names exact-command binding, and approval does not authorize a corrected or compound command.

**Acceptance Scenarios**:

1. Given a refused write, its card says only this exact command text is approved and instructs the planner to run it alone.
2. Given approval for `gh workflow run deploy.yml -f ref=abc`, a corrected `--ref main` call or a compound shell call still requires its own card.

### Edge Cases

- `--preview x` and `--preview=x` consume their value; preview GETs pass and preview writes require a card.
- Multiple operands including a deployment/environment path require a card in either order, even without an explicit write method.
- Header values containing `override`, case-insensitively, are conservatively non-reads on deployment/environment paths; ordinary headers remain reads.
- Unparsed short-option clusters remain owner-only; use separate flags for reads.
- Explicit GET with fields or input stays owner-only for deployment/environment paths.
- Attached and equals option forms follow the same classification as spaced forms.
- HEAD and OPTIONS remain owner-only on these paths; the requested exemption is GET only.
- Shell wrappers and compounds retain segment checking; a read cannot hide a following write.
- Explicit `deploy.deny` rules keep precedence over built-in read exemptions.
- Existing parse/config errors retain their exit behavior.

## Requirements

### Functional Requirements

- **FR-001**: Permit the named Vercel reads, including the existing `vc` alias, without an owner card.
- **FR-002**: Permit deployment/environment API requests only when all explicit methods are GET (or absent) and no `-f`, `-F`, `--field`, `--raw-field`, or `--input` occurs. Exactly one target is required, and headers naming an override are non-reads.
- **FR-003**: Keep mutations, explicit deny rules, and writes within compounds owner-only through the existing Owner step flow.
- **FR-004**: Write-card descriptions must say only this exact command text is approved and to run it alone; approval binding stays unchanged.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Both reported reads and their specified variants produce zero owner cards.
- **SC-002**: Every tested deployment mutation still requires approval.
- **SC-003**: Every publish card explains exact-command binding; edited and compound commands cannot reuse the original approval.

## Assumptions

- F2 owner decision, unchanged: init still writes `Bash(vercel*)` and `Bash(vc *)` into host permissions. The hook allows the named Vercel reads, but those host rules still deny them in initialized workspaces. The Vercel MCP connector remains the available route. Narrowing the deny rules and migrating existing settings require an owner decision and are outside this follow-up.
- F4 owner decision, unchanged: design section 4.7 still says all deployment/environment API calls are refused. This conflicts with the GET exemption requested by #947. Proposed owner wording: deployment/environment writes require approval; a single-target GET without fields, input or override headers is a read. Only the owner may amend the design; the PR must name this conflict.
- This explicit review follow-up authorizes the additional F1/F3 fix round. The approach remains the shared option scanner plus a conservative read predicate, not a new parser. Ambiguous multiple targets cannot qualify as reads.

- Issue #947 supplies the owner intent narrowing design section 4.7's broad API wording. Proposed owner wording: deployment/environment writes require approval; GET requests without fields/input are reads. The owner-only design file stays untouched.
- The exemption is deliberately limited to GET without request fields/input, even with explicit GET; HEAD/OPTIONS remain outside this issue.
- The existing option scanner does not parse Boolean-prefixed short clusters. Keep those owner-only rather than expanding shell parsing; separate `-i -X GET` is supported.
- Support `vc env ls` consistently with the existing alias; no new Vercel parser or global-option grammar.
- Existing read rules, explicit deny precedence, redaction, approval spending, state, status, report, close and doctor paths remain in force.
- Validation uses the task-specified interpreter and explicit affected test files, overriding the constitution's bare full-suite instruction. Tests use fixtures and never contact GitHub or the network.

## Clarifications

### Session 2026-10-13

No questions asked, as instructed. Scope, interaction, security, dependencies, errors and completion criteria reviewed. Recommendations are recorded under Assumptions; no unresolved ambiguity remains.

## Deferred

F2 host permission policy and migration, and F4 design amendment, remain owner decisions. F5 requires no action: a GET cannot dispatch or rerun; write forms remain owner-only.
