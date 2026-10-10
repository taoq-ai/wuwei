# Feature Specification: wuwei pr raise --draft opens a draft PR for an item the owner merges, keeping reviewer ranking and the raised record

**Feature Branch**: `726-pr-raise-draft`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #726 (owner, 2026-10-10, item 52): PRs that only the owner merges had
to be opened with `gh pr create --draft` plus `pr claim`, which skips reviewer ranking and
records the PR as unraised. Deliver `pr raise --draft` (and automatically when the item has
`owner_merge = true`, #678): open the PR as a draft through the code host port, record it as
raised with `draft: true`, rank reviewers as usual, and let `pr act` mark it ready when the
owner clears the flag or asks.

## Root cause (read on main at d3b7066)

No orchestrator notes (`_pipeline/notes/726-full.md`) and no dry-run workspace exist for this
issue, so the failure is reproduced read-only from the CLI and the code:

- `bin/wuwei pr raise --help` lists only `repo`, `--base`, `--title`, `--body-file` and
  `--item`: there is no way to ask for a draft (`cli/wuwei/commands/pr.py:15-21`).
- `shepherd.raise_pr` (`cli/wuwei/shepherd.py:278`) reads the owner hold
  (`shepherd.py:324`, `merge.owner_hold`) only for the body line and the label. It calls the
  port with `{'repo', 'base', 'head', 'title', 'body'}` (`shepherd.py:352-353`), so even a
  flagged item's PR opens ready for review. The github adapter already accepts an optional
  `draft` boolean in that payload (`adapters/code_host/github.py:538-545`); the core never
  sends it.
- `state.record_pr` (`cli/wuwei/state.py:416`) writes the `pr.raised` event with `pr`, `item`,
  `head` and `reviewers`; nothing says the PR is a draft.
- `raise_pr` prints only the ref, plus `reviewers: none (solo)` when nobody is selected
  (`shepherd.py:369-370`); the ranked reviewers are never listed.
- The workaround the owner used, `gh pr create --draft` then `pr claim`, goes through
  `shepherd.claim_pr` (`shepherd.py:380`), which records `raised=False` (`shepherd.py:404`:
  a `pr.claimed` event and `claimed_prs`) and never runs `_rank`.
- `pr_actions.act` (`cli/wuwei/pr_actions.py:513`) has no step that takes a PR out of draft,
  and the code host port (`cli/wuwei/registry.py:34-43`) has no operation for it. A draft PR
  in state `waiting` returns 0 at `pr_actions.py:521` and stays a draft; `merge.check`
  refuses it (`merge.py:299`, `PR is a draft`) and the ping gate refuses it
  (`shepherd.py:158`).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: When is a raise a draft? A: When `--draft` is passed, or when `merge.owner_hold` of the
  item is set (`owner_merge.value` true). A cleared or absent flag without `--draft` raises
  ready for review, as today.
- Q: What goes to the code host? A: The existing `create_pr` payload gains `'draft': <bool>`
  on every raise (false is GitHub's default, so an ordinary raise behaves as before). After
  creation, the existing check that the created PR matches the head and URL also checks that
  its `draft` equals what was asked; a mismatch is exit 2 like the other mismatches.
- Q: What is "recorded as raised with draft true"? A: The PR goes into `raised_prs` and the
  item phase moves to `raised` exactly as today (`state.record_pr(raised=True)`), and the
  `pr.raised` event payload gains `"draft": true`. No new state key: the draft status after
  raise is read fresh from the code host, so the event is history and nothing trusts it.
- Q: Are reviewers ranked and requested for a draft? A: Yes, as usual. `_rank` runs, the
  selection is stored in `pr_reviewers`, and `request_reviewers` is called; GitHub accepts
  review requests on a draft.
- Q: What does "lists the ranked reviewers" print? A: After the ref, `raise_pr` prints
  `reviewers: <login> <login>` (the format `pr reviewers` already uses), or
  `reviewers: none (solo)` when none. This holds for every raise, draft or not.
- Q: How does a draft become ready? A: A new code host operation `ready(ref)`, which the
  github adapter runs as `gh pr ready https://github.com/<repo>/pull/<n>` (one closed
  allowlist entry, shaped like the existing `gh pr merge` entry), and the none adapter
  records as unmeasured. `pr act <ref>` calls it, re-reads the PR, and fails closed (exit 2)
  if it is still a draft.
- Q: When does `pr act` mark it ready? A: Two ways. (1) The owner asks: `pr act <ref> --ready`
  on an open draft. (2) The owner cleared the flag: the item linked to the PR carries an
  `owner_merge` record whose value is false (the record exists and `merge.owner_hold`
  returns None). Clearing is owner-only (`protect_state`, #678), so a seat cannot trigger
  (2). A draft whose item never had the flag stays a draft until `--ready`, so an explicit
  `--draft` on an ordinary item is not undone by the next `pr act`.
- Q: What does `pr act --ready` do on a PR that is not a draft? A: Prints
  `<ref>: already ready for review` and exits 0, so a rerun is harmless; it never falls
  through to the PR's other actions (for example a merge of an approved PR).
- Q: Does marking ready lift the owner hold? A: No. Readiness is not merge authority:
  `merge.check` still refuses a flagged item (I37), so `pr act --ready` on a held item makes
  it reviewable and nothing more. No guard or decision rule changes, so the design 9.2 table
  and `tests/test_invariants.py` are untouched.

## User Scenarios and Testing

### User Story 1 - An owner-merge item raises as a draft (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an approved item with `owner_merge = true`, **When** `wuwei pr raise` runs
   without `--draft`, **Then** the code host `create_pr` receives `draft: true`, the PR is in
   `raised_prs` with the item at phase `raised`, the `pr.raised` event payload has
   `"draft": true`, `pr_reviewers` holds the ranked selection, `request_reviewers` is called
   with it, and stdout lists the ref and `reviewers: <ranked logins>`.

### User Story 2 - The owner asks for a draft on an ordinary item (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an approved item without `owner_merge`, **When** `wuwei pr raise ... --draft`
   runs, **Then** the same as User Story 1, scenario 1.
2. **Given** the same item without `--draft`, **Then** `create_pr` receives `draft: false`,
   the `pr.raised` payload has no `draft` key, and stdout still lists the reviewers.

### User Story 3 - pr act marks the draft ready (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an owned open draft PR whose item's `owner_merge` was cleared (value false),
   **When** `wuwei pr act <ref>` runs, **Then** the code host `ready` operation is called once,
   stdout is `{"action": "ready", "pr": "<ref>"}` and it exits 0.
2. **Given** an owned open draft PR whose item has the flag set or never had it, **When**
   `pr act <ref>` runs, **Then** `ready` is not called and the existing behaviour applies.
3. **Given** the same, **When** `pr act <ref> --ready` runs, **Then** `ready` is called and it
   exits 0, flag set or not.
4. **Given** a PR that is not a draft, **When** `pr act <ref> --ready` runs, **Then** it prints
   `<ref>: already ready for review`, exits 0 and calls no other action.
5. **Given** `ready` fails, or the PR is still a draft after it, **Then** `pr act` exits 2
   with `<ref>: PR action unmeasured: <reason>`.

### Edge Cases

- A malformed `owner_merge` record is exit 2 (damaged), at raise and at act, through
  `merge.owner_hold`; never read as cleared.
- A closed draft PR is never marked ready.
- `create_pr` returns a PR whose `draft` differs from what was asked: exit 2 before
  anything is recorded, with the existing "created PR does not match" message.
- `--ready` with `--run`, `--complete` or `--reply` is refused by argparse (one mutually
  exclusive group).

## Requirements

- **FR-001**: `pr raise` accepts `--draft`; `shepherd.raise_pr(..., draft=False)` raises a
  draft when `draft` is true or `merge.owner_hold(item)` is set.
- **FR-002**: `raise_pr` sends `draft` in the `create_pr` payload and verifies the created
  PR's `draft` matches.
- **FR-003**: `state.record_pr(..., draft=False)` adds `"draft": true` to the `pr.raised`
  payload when the raise was a draft; nothing else in the record changes.
- **FR-004**: `raise_pr` prints `reviewers: <logins>` after the ref when reviewers were
  selected (the solo line stays as is).
- **FR-005**: The code host port gains `ready(ref)`: registry parameters, the github adapter
  (`gh pr ready <url>`, closed allowlist), the none adapter, the port contract table in
  `tests/test_adapters.py`, the recording fake and one replay recording.
- **FR-006**: `pr state` rows carry `draft` (the fresh code host value); `pr act` marks an
  open draft ready on `--ready` or when the linked item's `owner_merge` record exists with
  value false, and `--ready` on a non-draft exits 0 without other actions.
- **FR-007**: `docs/site/reference.md` "Raising a PR" documents `--draft`, the automatic
  draft for `owner_merge`, the reviewers line and `pr act --ready`.

## Success Criteria

- **SC-001**: Both acceptance scenarios of the issue pass as tests on `raise_pr`.
- **SC-002**: An ordinary raise sends `draft: false` and records the same state and event as
  before, apart from the reviewers line on stdout.
- **SC-003**: The full suite passes.

## Assumptions

- No orchestrator notes and no dry-run workspace exist for #726; the issue and the code on
  main are the inputs, and the failure is reproduced from `pr raise --help` and the code.
- The workflow relay for this run quotes the owner's item 63 (owner commands carry
  `--workspace`), which is issue #735, not this one. This spec covers #726 (item 52) only.
- GitHub accepts `requested_reviewers` on a draft PR, so the raise requests reviewers as it
  does today. If a host refused, the existing error path reports it (exit 2).
- `gh pr ready` exits 0 on an already ready PR; the core still re-reads `draft` after it.
- "The owner clears the flag" is read from the item record (`owner_merge.value` false), which
  only the owner can write (#678). A record set and cleared before a `--draft` raise makes the
  next `pr act` mark it ready: the owner's clear outweighs the explicit `--draft`.
- Nothing schedules `pr act` for a waiting draft: the owner or the planner runs it after the
  clear. The watch and the headless shepherd are unchanged.
- The `pr.raised` event kind is already reserved to `wuwei pr raise`
  (`commands/event.py:67`), so the new `draft` field cannot be forged through
  `bin/wuwei event`, and nothing trusts it anyway.
- No new event for ready: the code host is the record, and `pr act` prints the action.

## Deferred

- A draft PR held for the owner still reaches `review_stale` after `pr.review_window`, and
  `pr act` then runs the ping, which refuses a draft (`PR is not open for review`, exit 1).
  This is pre-existing for every claimed draft; a follow-up issue should keep a held draft at
  `waiting` or name the hold.
- Printing the `pr act <ref>` next step from `plan set <item> owner_merge=false` when the item
  links a draft PR.
