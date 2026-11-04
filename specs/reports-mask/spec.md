# Feature Specification: a kept seat report is masked before it is written

**Feature branch**: `fix/reports-mask`
**Item**: reports-mask, tier full, goal G-2
**Input**: the security gate on #1278 found that outside auto mode the hook keeps the whole seat
report under `.wuwei/reports` with neither `guards.SECRETS` nor the canary masked. `sync.LOCAL`
does not list reports, so they push to the `wuwei/state` branch of a public repository. A scan of
121 synced reports on 2026-11-04 found only a test fixture and no canary.

## The promise in my words

When `subagent_stop` keeps a seat's report for the planner, the text it writes to
`.wuwei/reports/pending/` has every `guards.SECRETS` match and the workspace canary replaced by
`***`. This is the same expression `_seat_stop` and `post_tool` (the `seat.started` row) already
apply. A report with neither is written byte for byte as before. Reports already on disk stay as
they are; any history rewrite of `wuwei/state` is the owner's call.

The masked text is what the planner reads, so the two checks that compare a kept report with what
the planner was already shown compare masked text too:

1. the repeat check in `subagent_stop` (one file per text, #1208);
2. the "already notified" check in `deliver` (the Claude task notification) and `_native_told` (the
   Codex final answer). The notification holds the seat's raw text, so it is masked before the
   comparison.

Outside: listing reports in `sync.LOCAL`, traces, ledger fields.

The acceptance scenarios, restated:

1. A seat report holding a `ghp_` token and the canary, kept outside auto mode: the file under
   `.wuwei/reports` holds `***` for both, and neither reaches the planner's note.
2. A report with neither, kept: its text is unchanged.

## How this fails

1. The masked report no longer equals the notification the harness gave, so a notified report is
   given again in full and blocks the planner's Stop once. Guarded by masking the notification side
   of both comparisons, with a test for each.
2. The repeat check compares the masked file with the raw report, so a seat looping on a refused
   hand-back writes one file per stop. Guarded by comparing the masked text, with a test.
3. A report kept before this change, still pending, holds a secret and was notified: the masked
   notification no longer equals its raw text, so it is given once more in full. Accepted: it needs
   a pending file from before the upgrade that holds a secret; the cost is one repeated report.

## Clarifications

### Session 2026-11-04

- Q: Is a new masking helper added? A: No. The brief says reuse; the kept write uses the same
  inline `guards.SECRETS.sub('***', v).replace(canary or '\0', '***')` the hook uses elsewhere.
- Q: Where is the canary read? A: From `.wuwei/canary`, the same file the other sites read; no
  canary file means only `guards.SECRETS` applies.
- Q: Is the whole report masked or cut like `seat.stopped` lines? A: Masked whole and never cut; the
  planner still needs the full report.
- Q: Are reports already on disk rewritten? A: No, per the promise.
- Q: The Codex frame names the sender, which may hold a secret; how is it compared? A: Both sides
  of `_native_told`'s comparison are masked, frame included, so a sender `seat_identity` hashes
  still matches (tests/test_native_identity_privacy.py).
- Q: Does the hashed file name change? A: No. It is built from the session, agent and role, which
  `seat_identity` and the `[^\w-]` filter already cover.

## User Scenarios & Testing

### US1: a kept report holds no secret or canary (P1)

Acceptance 1, read from the file and from the planner's next call.

### US2: a clean report is unchanged (P1)

Acceptance 2.

### US3: the masked report still dedupes and still counts as notified (P2)

A seat stopping twice with the same secret-holding report keeps one file; a Claude notification and
a Codex final answer that carry the raw text make the masked report a pointer.

## Requirements

- FR-001: `hook.subagent_stop` writes the kept report with `guards.SECRETS` and the canary masked.
- FR-002: The repeat check compares the masked text.
- FR-003: `hook.deliver` and `hook._native_told` mask the notified text before comparing it.
- FR-004: The runtime stays at 4,000 lines or fewer, at most 2 more than main.

## Assumptions

- The masker is the existing inline expression, not a new helper. Overturned if the retro wants
  one `mask()` for all sites; that is a refactor outside this promise.
- A pre-upgrade pending report with a secret may be given once more (How this fails 3). Overturned
  if a live session shows such a file.

## Rollback

Revert the commit. No config key, ledger kind or file format changes.
