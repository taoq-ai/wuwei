# Feature Specification: the shepherd duty is an executable launch and the seat classifies PR threads

**Feature Branch**: `906-shepherd-launch` (one batch with #887)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #906 (independent review, item 6): make shepherding an executable duty and
stop classifying review intent by keywords.

## Root causes (0.29.0, lines on main after 0.30.0)

1. `derive.duties` says "Launch the shepherd seat" but returns `wuwei duty <item> shepherd --evidence
   <link>`, a recording command (`cli/wuwei/derive.py:459`). Nothing briefs or launches a seat; the
   planner builds the launch by hand or skips it.
2. `wuwei duty <item> shepherd --evidence <text>` accepts any nonempty text as completion
   (`cli/wuwei/commands/duty.py:27`).
3. `pr_actions._thread` routes on keywords before it honours `--reply`: "change" opens a fix round,
   "scope" or "instead" opens an owner scope card (`cli/wuwei/pr_actions.py:548`). An explicit reply
   to "Could you explain this change?" opened a fix round. `pr_actions.launch` repeats the same
   keyword test for claimed PRs (`:462`).
4. `--reply` answers whichever reply is owed first. New activity that sorts first (a fresh PR
   comment) takes a reply meant for another thread.

## User Scenarios & Testing

### User Story 1 - review activity launches the shepherd seat once per activity revision (P1)

1. **Given** a raised PR with review activity newer than its last answer, **When** `wuwei next`
   runs, **Then** it returns one `shepherd` launch for the item; the launch set resolves it to the
   brief command, then to the seat launch of `shepherd-<item>-<revision>`.
2. **Given** that seat is registered (running or stopped), **When** `wuwei next` runs again,
   **Then** no shepherd launch is offered for the same revision; the PR waits.
3. **Given** newer activity arrives, **Then** a new revision launches a new seat.
4. `next` lists no `shepherd` duty to record by hand.

### User Story 2 - the seat classifies, the CLI never guesses (P1)

1. **Given** an owed thread "Could you explain this change?", "Is this in scope?" or "Why not X
   instead?", **When** the seat runs `pr act <pr> --thread <id> --reply "<answer>"`, **Then** the
   reply posts; no fix round and no card opens.
2. **Given** a plain `pr act <pr>` on any owed thread, **Then** it prints the reply action (thread
   id, question, every owed id) and opens nothing.
3. **Given** a genuine fix request, **When** the seat runs `pr act <pr> --thread <id> --fix
   "<reason>"`, **Then** a fix round opens with the thread text and the reason as feedback.
4. **Given** a change outside the item promise, **When** the seat runs `pr act <pr> --thread <id>
   --scope "<reason>"`, **Then** the owner's Owner step card is printed; Yes opens the fix round,
   No returns the defer reply. No card opens without `--scope`.
5. **Given** two owed threads, **Then** `--thread` answers the named one; a thread no longer owed
   is refused.
6. **Given** a new comment arrives while the seat composes a reply, **When** it replies with
   `--thread <id>`, **Then** the reply goes to that thread, never to the newer comment.

### User Story 3 - completion comes from the obligation ledger (P1)

1. **Given** a due shepherd duty, **When** a fresh PR read (`pr act`, `pr state`, `close`) finds no
   reply owed, **Then** `duty.done` is recorded with the time the read started.
2. **Given** activity newer than that read, **Then** the duty is due again.
3. `wuwei duty <item> shepherd --evidence <text>` is refused and names `pr act`; `--skipped` still
   records a skip.

## Requirements

- **FR-001**: `derive.offers` returns a `shepherd` launch (`kind: shepherd`) for a raised item whose
  shepherd duty is due and whose revision seat is not registered; `derive.seated` resolves it.
- **FR-002**: `dispatch.resolve_offer` resolves it through the brief and seat machinery
  (`brief.seat_action`), sharing the raise path's shape.
- **FR-003**: `pr_actions` loses `SCOPE` and `FIXES`; `launch` opens fix rounds only for a conflict
  or red checks.
- **FR-004**: `pr act` gains `--thread`, `--fix` and `--scope`; `--reply` is honoured first.
- **FR-005**: `observe` records the shepherd `duty.done` (`as_of` the read start) when no reply is
  owed and the duty is due; `derive.duties` uses `as_of` when present.
- **FR-006**: `wuwei next` omits the shepherd duty from its duty list (it is a launch); `close`
  still names it with `pr act` as its record.

## Success Criteria

- **SC-001**: the six thread cases of the issue (the three keyword questions, a fix request,
  multiple threads, activity during a reply) pass without a keyword in the code.
- **SC-002**: three consecutive `next` calls on one activity revision produce one brief command,
  then one seat launch, then nothing.

## Assumptions

- The shepherd launch is offered only while the item is `raised`; a reviewer question during a fix
  round is answered once the round returns the item to `raised`. Reason: a reply then cites the
  pushed fix, and the merge launch already defers to it in the same branch.
- The revision is the listing's `activity_at` and the PR head, written in the seat name
  (`shepherd-<item>-YYYYMMDDHHMMSS-<head7>`), which the brief name rule accepts. A pushed fix
  round moves the head, so a new seat answers the thread with evidence (review F1).
- No second shepherd seat starts while one for the item runs (review F3).
- A `--fix` or `--scope` leaves the thread owed. When the item is raised, no launch of any kind
  is offered for it and nothing of it is in flight (a scope No, a seat that stopped or died),
  `next` lists the shepherd duty with `wuwei pr act <pr>` as its step, so it is never a silent wait
  (review F1). During a fix round it stays a wait (delta D1).
- An open P1 bot thread is owed and its fix opens by its id; a reply to it is refused and points to
  `--fix`, since only the fix outdates it (review F4, delta D3).
- The scope card's token carries the item's fix round count: a Yes opens one round, and the same
  command after it asks the owner again (review F6).
- `--thread` stays optional for `--reply` (the first owed reply, as before) so existing callers
  keep working; the shepherd brief always passes it.
- The listing leaves the viewer's own reviews and comments out of `activity_at`, and the author's
  only when the author is the viewer: a teammate's follow-up on a claimed PR counts (delta D2) (top-level
  `viewer{login}`, no extra cost), so WUWEI's replies and pings on a claimed PR launch nothing
  (review F3).

## Deferred

- #884 (pings for PRs opened outside WUWEI) is unchanged.
