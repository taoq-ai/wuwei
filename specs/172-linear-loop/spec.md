# Feature Specification: Linear tracker in the loop

## User Scenarios & Testing

1. Given a recorded tracker backlog, `wuwei discover` lists its candidates, excluding items already in today's plan or linked to open PRs.
2. Given an item started, a PR raised, and the PR merged with a fake tracker, calls occur in order: claim, in review, done.
3. Given no tracker, discovery and transitions are unmeasured with reason `tracker adapter is none`.

## Requirements

- FR-1: The tracker port exposes `backlog(filter)` with candidate id, title, url, state, and updated time.
- FR-2: Discovery reads that port and deduplicates candidates against current items and open PR links.
- FR-3: Item start claims its tracker issue; PR raise and confirmed merge transition it to configured state names.
- FR-4: Linear resolves state names to team state IDs and caches the resolution.
- FR-5: Unavailable or failed tracker calls report unmeasured and do not prevent loop progress.

## Success Criteria

- The three acceptance scenarios pass with recorded payloads and fakes, without network access.
- Existing command and guard behavior remains covered by the full test suite.

## Assumptions

- A WUWEI item ID is its Linear issue identifier.
- The backlog filter is a configured Linear team ID; an empty filter reads accessible issues. Both queries exclude completed and canceled workflow states.
- A merge transition is made after the host confirms the merge, not when it merely accepts a request.
- Merge polling resolves the linked item from the day that recorded the merge intent.
- Open PR dedupe uses tracker issue IDs already linked to today's PRs.
