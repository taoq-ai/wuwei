# Feature Specification: Generic role charters

**Feature Branch**: `019-charters`
**Created**: 2026-09-28
**Status**: Draft
**Input**: Issue #19, generic charter set for nine roles.

## User Scenarios & Testing

### User Story 1: Run a chartered team (Priority: P1)

Each of nine seats can read its own ordered checklist and the shared rules without needing engagement-specific facts.

**Independent Test**: All eleven charter files exist, carry a version in frontmatter, and name the role's required work and boundaries.

**Acceptance Scenarios**:
1. Given any seat, when it reads its charter and common rules, then it finds its work order, decision routing, proposal process, and retro shape.
2. Given a code item, the lead flags and ranks it, the builder tests and implements it, the sentinels gate it, and the shepherd raises and watches its PR under the amended policy.
3. Given a steward sweep, the steward records steering and proposals without dispatching or changing item state.

### User Story 2: Keep rules generic and traceable (Priority: P1)

The owner can audit every design rule and ship the charters without leaking source engagement details.

**Independent Test**: A lint scans all charters for generic ticket and chat ids, URLs, emoji and em dashes; a rule table maps every section 5.3 bullet and amended engineering standard to one stable anchor.

**Acceptance Scenarios**:
1. Given the complete `charters/` tree, a lint finds no generic ticket or chat id, emoji, em dash or URL.
2. Given each section 5.3 rule, a distinctive clause from its body appears in exactly the assigned charter or common section.
3. Given a rule change, `_common-authoring.md` directs a proposal. `wuwei promote` writes the dated verbatim entry to `memory/CHANGELOG.md` and the outcome to `memory/ledger.jsonl`. Seats never write or load the changelog.

## Requirements

- FR-001: Ship `_common.md`, `_common-authoring.md`, and planner, lead, builder, sentinel-arch, sentinel-quality, sentinel-security, sentinel-goal, shepherd and steward charters.
- FR-002: Each file has `version:` frontmatter and role-specific ordered checklists; shared rules have one home.
- FR-003: Boundary and environment registers, owner, repositories, adapters and policy values come from `config.toml` and day state, not embedded engagement values.
- FR-004: Honor amended sections 4.6, 4.7, 5.3, 5.7, 5.8 and 6.8, including no approval or deployment, merge through `wuwei merge`, decision records and proposal-only charter/note changes.
- FR-005: Add `tests/test_charters.py` lint and rule table.
- FR-006: Document `wuwei promote` as the sole writer of dated, verbatim rule history in workspace `memory/CHANGELOG.md` and proposal outcomes in `memory/ledger.jsonl`; seats never write either or load the changelog.

## Assumptions

- `version: 1.0.0` is the initial charter version; issue #40 owns upgrade behavior.
- Shared decision and proposal rules live in `_common.md`; role files point to it rather than repeating the complete procedure.
- The workspace template's `memory/CHANGELOG.md` already exists, so this issue documents its convention without changing the template.
- Organisation-specific names are checked by an owner-local pre-publish scan (issue #42), never in this repository.

## Success Criteria

- SC-001: The requested full pytest suite passes.
- SC-002: All eleven charter files pass the lint and each rule table entry has one matching anchor in the assigned file.

## Deferred

Agent generation and charter upgrade behavior belong to issue #40. Runtime decision, promotion and merge guards belong to their CLI issues.
