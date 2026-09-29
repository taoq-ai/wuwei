# Feature Specification: Item to PR link and PR claiming

**Feature Branch**: `162-pr-link`
**Created**: 2026-09-29
**Status**: Ready

## User Scenarios and Testing

### Raised PR (P1)

Given an approved item and a PR raised for it, the item records the PR and the day owns it. Merge checking can find the linked item, and PR state lists the PR.

### Claimed PR (P1)

Given an existing PR for an approved item, claiming it records the same item link and day ownership. Once merged, the item's lead time can be measured.

### Protected link (P1)

Given `wuwei state set items.X.pr ...`, the write is refused and names `wuwei pr raise` or `wuwei pr claim` as its producers.

## Requirements

- Raising or claiming a PR MUST atomically record its canonical reference on exactly one existing item and in the corresponding raised or claimed set.
- Claim MUST verify the PR through fresh code host evidence before writing.
- A PR linked to a different item, or an item linked to a different PR, MUST be refused without changing state.
- Generic state and event commands MUST NOT forge the item link or claim evidence.
- Existing merge, ownership and metrics readers MUST consume the recorded link without a parallel data structure.

## Success Criteria

- Raised and claimed PRs have one item link and appear in ownership state.
- Merge checks for linked raised PRs progress past the missing item finding.
- Lead time for a claimed PR is measurable after merge evidence becomes available.
- Generic state writes to the item PR link are refused with the dedicated producer names.

## Assumptions

- Claim accepts canonical `owner/repo#number` syntax and an existing approved day item.
- A repeated claim of the same PR and item is idempotent.
- The dry run workspace had no raised PR because its code host adapter was unmeasured; the missing link is reproduced through in-process fake ports.

## Deferred

- None.
