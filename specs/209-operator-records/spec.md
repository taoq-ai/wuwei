# Feature Specification: Records the operator reads are correct

**Feature Branch**: `209-operator-records`

**Created**: 2026-09-30

**Status**: Ready

**Input**: GitHub issue #209, "fix(team): records the operator reads are correct". Design spec sections 5.5 (steward) and 5.9 (cockpit, signals and briefings). Evidence: the v0.5.0 operator dry run of 2026-09-30.

## Root causes (reproduced read-only in the v0.5.0 dry-run workspace)

The dry run ended with one PR merged, decision D-1 answered (`defer`), and a pending reply sent through the drafts queue. What the operator read:

| Surface | What it showed | Root cause |
|---|---|---|
| `wuwei drafts` after `pr act --reply` (row 32) | `[]` | `cli/wuwei/pr_actions.py:393-405` (`_thread`) stores the draft in a private `pr_reply_drafts` state key (write at line 399) instead of the owner queue that `cli/wuwei/drafts.py:create` writes and `wuwei drafts` lists. Only `wuwei reply` reached the queue, through the `registry.outward_operation` wrapper. |
| `wuwei report` "Open at close" and "Carry" (row 9) | phantom `DISCOVERY: planned (queued)` | `cli/wuwei/brief.py:238-239` runs `fresh['items'].setdefault(item, {})` for every role except `steward`, so `wuwei brief lead DISCOVERY lead-1` created a work item. Items are otherwise only created by `wuwei plan approve` and `wuwei plan add`. |
| `wuwei report` (acceptance) | no line anywhere says an item merged | `cli/wuwei/report.py:22-24` and `:54` drop `merged` items from "Open at close" and "Carry" and no section lists them. |
| `wuwei status --line` (row 38) | `spec 0/1 \| implement 0/1 \| fix 0/1` while DIVIDE-1 was in `delta` | `cli/wuwei/commands/status.py:103` counts only `state.BUILD_PHASES` (`spec`, `implement`, `fix`); any item in `planned`, `gate`, `delta`, `raised`, `merged`, `parked` or `escalated` is invisible. |
| `wuwei nudges` (19 nudges at close, nothing owed) | `plan.approved`, `build.started` x2, `build.checked` x3, `verdict.rejected` x3, `tracker.call` ("tracker adapter is none"), `draft.created` x3 (all three already sent or dropped), `merge.policy_blocked` x2 (PR already merged), `plan.proposed` x2 | (a) routine progress kinds are missing from `cli/wuwei/signal.py:6` `SILENT`, and `tracker.call` (`signal.py:40-41`) nudges when the owner configured the tracker adapter as `none`; (b) `cli/wuwei/commands/status.py:77-83` keys `draft.created` and `merge.policy_blocked` by line number, so no later event can clear them; (c) the `pr.action` event written at `cli/wuwei/pr_actions.py:138` does not carry the PR state, so a merge cannot clear the merge nudge; (d) the `plan.proposed` rows come from the steward-queue bug below. |
| `briefs/pack-daily.md` (row 48) | Headline and Changed "tracker adapter is none"; Decided "No recorded decisions"; deep dives are guard refusal messages | `cli/wuwei/brief_pack.py:29-50` (`_evidence`) takes any event payload `text`, `summary`, `outcome` or `reason`, so adapter and guard messages become the headline; `decision.decided` carries `id` and `option`, not `outcome`, so the answered decision never appears. |
| `steward-decisions.json` (row 45) | `demo-org/demo#1:thread:PRRT_1` and `:PRRT_2` with lint "candidate id must be unique and safe" | `cli/wuwei/discovery.py:150` builds follow-up ids from the PR ref (`/`, `#`, `:`), `cli/wuwei/plan.py:57-58` rejects them, and `cli/wuwei/discovery.py:237-242` (`intake`) records every `plan.add` `ValueError` as an owner proposal, which `cli/wuwei/steward.py:78-85` (`decision_queue`) then lists. No owner answer can admit such a candidate. |

## User Scenarios & Testing

### User Story 1 - A composed PR reply waits in the owner queue (Priority: P1)

The operator runs `wuwei pr act <ref> --reply "<text>"` on an unanswered review question whose outward tier is draft. The reply is stored as an owner draft, `wuwei drafts` lists it, and `wuwei drafts approve <id>` sends it as a reply in that review thread.

**Independent Test**: fake code host with one unanswered thread; `pr act --reply` then `wuwei drafts`.

**Acceptance Scenarios**:

1. **Given** an owned PR with an unanswered review thread and a draft tier, **When** the operator runs `wuwei pr act <ref> --reply "<text>"`, **Then** it exits 1, prints a `draft_reply` action naming the draft id, and `wuwei drafts` lists one pending `code_host` `comment` draft with destination `<ref>`, the reply text, the thread root comment id and the linked item.
2. **Given** the same reply is submitted twice, **Then** the queue holds one pending draft, not two.
3. **Given** the outward tier is unmeasured, **Then** the command exits 2, says the reply was kept as a draft, and `wuwei drafts` lists it.

### User Story 2 - Only real items appear in the day's records (Priority: P1)

A lead or steward brief does not create a work item, so report, close, carry and status list only items the plan approved or admitted.

**Acceptance Scenarios**:

1. **Given** an approved day with item DIVIDE-1, **When** `wuwei brief lead DISCOVERY lead-1` and a steward brief are written, **Then** `state.json` items are still exactly `{DIVIDE-1}` and the report names no DISCOVERY item.
2. **Given** a builder brief with `--track FULL` or `--worktree` for an existing item, **Then** the item's track and worktree are recorded as before.

### User Story 3 - Status line and nudges tell the truth (Priority: P1)

**Acceptance Scenarios**:

1. **Given** items in `delta` and `merged`, **When** `wuwei status --line` runs, **Then** the line shows `delta 1/<cap>` and `merged 1/<cap>`, and `status --json` `phases` carries the same counts.
2. **Given** events `plan.approved`, `state.import`, `build.started`, `build.launched`, `build.checked` and `verdict.rejected`, **Then** none of them is a nudge.
3. **Given** a `tracker.call` event whose reason is `tracker adapter is none`, **Then** it is silent; any other failed tracker call is still a nudge.
4. **Given** a `draft.created` event, **Then** it is one nudge until a `draft.sending`, `draft.sent`, `draft.failed` or `draft.dropped` event for the same draft id, after which it is gone (a `draft.failed` remains its own nudge).
5. **Given** two `merge.policy_blocked` events for one PR, **Then** they are one nudge, and a later `pr.action` event reporting that PR `merged` or `closed` clears it.

### User Story 4 - The briefing pack reports the day's work, not tool chatter (Priority: P1)

**Acceptance Scenarios**:

1. **Given** DIVIDE-1 merged with PR `org/repo#1` and D-1 answered `defer`, plus events carrying `tracker adapter is none` and guard refusal reasons, **When** `wuwei brief pack` runs, **Then** Headline and Changed name `DIVIDE-1: merged (org/repo#1)`, Decided names `D-1: defer`, At risk says `No recorded risks`, and no adapter or guard message appears anywhere in the pack.
2. **Given** a parked item, a pending owner decision, or an owned PR with an open action episode, **Then** each appears under At risk and the headline leads with the first risk.
3. **Given** a decision outcome containing HTML, **Then** the pack escapes it.

### User Story 5 - The steward queue only offers candidates it can lint (Priority: P2)

**Acceptance Scenarios**:

1. **Given** discovery returns `org/repo#1:thread:PRRT_1` and a safe but incomplete candidate `PARTIAL`, **When** intake runs, **Then** no proposal, `plan.proposed` event or steward queue row exists for the unsafe id, and `PARTIAL` still goes to the owner as today.

### Issue acceptance (end to end)

1. **Given** a day with one merged item and one answered decision (built through plan approve, a lead brief, a steward brief, state transitions to `merged`, an answered D-1, the routine events above, a sent draft, a policy-blocked merge followed by a merged `pr.action`), **Then** the report lists DIVIDE-1 under Merged and D-1 under Decisions answered with Open at close and Carry `none`; the status line shows `pages 0 | nudges 0` and `merged 1/`; the pack headline names DIVIDE-1 merged and Decided names D-1; `wuwei nudges` prints `[]`; and no DISCOVERY item appears in any of them.
2. **Given** `pr act --reply`, **Then** `wuwei drafts` lists the draft.

## Edge Cases

- A day state that already holds a `pr_reply_drafts` key (written by v0.5.0) still loads; the key is simply no longer written.
- A brief for an item that does not exist leaves `items` unchanged; the brief file and `brief written` event are still produced.
- A pack on a day with no state file reports `No recorded changes`, `No recorded decisions`, `No recorded risks`.
- Duplicate or symlinked decision records keep failing the report and the pack (exit 2) exactly as the report does today.
- A draft id that never had a `draft.created` event in today's stream is ignored by the clearing rule.
- Status line on a day with no items shows pages, nudges and meeting only.

## Requirements

### Functional Requirements

- **FR-001**: `pr act --reply` must store a draft-tier reply through `drafts.create` (channel `code_host`, operation `comment`, the configured `code_host` adapter, inputs `ref`, `text`, `thread`) and must not write `pr_reply_drafts`.
- **FR-002**: A repeated identical `pr act --reply` must not add a second pending draft.
- **FR-003**: `brief.write` must never create an item; it records track and worktree only on an item that already exists, and never for the steward.
- **FR-004**: The report must list merged items in a `## Merged` section.
- **FR-005**: The status snapshot must count every item phase in `state.PHASES` order; the line shows each nonzero phase as `<phase> <count>/<cap>`.
- **FR-006**: Routine progress kinds (`plan.approved`, `state.import`, `build.started`, `build.launched`, `build.checked`, `verdict.rejected`) must classify silent; `tracker.call` with reason `tracker adapter is none` must classify silent.
- **FR-007**: `draft.created` nudges must clear when that draft is claimed, sent, failed or dropped; `merge.policy_blocked` nudges must be one per PR and clear when a `pr.action` event reports that PR `merged` or `closed`.
- **FR-008**: Every `pr.action` event must carry the PR state it observed.
- **FR-009**: The pack's Headline, Changed, Decided and At risk must come only from state items, decision records and owned PR action episodes; event payload text must not feed them.
- **FR-010**: The report and the pack must read answered and pending decisions through one shared helper.
- **FR-011**: Discovery intake must not propose a candidate whose id fails the plan's id rule; safe but incomplete candidates keep going to the owner.
- **FR-012**: No exit code, guard, reservation or producer allowlist is loosened.

## Success Criteria

- The issue acceptance day produces the four surfaces above with zero nudges and no phantom item.
- `wuwei drafts` lists a reply composed through `pr act --reply` on the first call.
- All tests run in-process without network or real tools.

## Assumptions

- Item phases move only through `wuwei state transition`; syncing an item to `merged` when its PR merges outside WUWEI is not in this issue. The acceptance fixture transitions the item.
- `verdict.rejected` is seat rework: the dispatcher sends the verdict back to the seat and the steward metric `verdict_lint_rejections` counts it, so the owner has nothing to act on and it is silent. Spec 5.9 does not list it among nudges.
- A tracker adapter configured as `none` is an owner choice, so a skipped tracker call is routine. A failed call against a configured tracker still nudges.
- Unsafe discovery ids come from PR follow-up sources whose work is already handled by `wuwei pr act` on the owned PR; dropping them from intake loses no owner decision. Making those ids admissible is a separate design change.
- The `pr_reply_drafts` state producer entry and the `pr.reply.drafted` event reservation stay, so legacy day files load and the kinds stay unforgeable.
- A reply drafted for an unthreaded review or comment surface and later sent by `wuwei drafts approve` does not record a reply acknowledgement; this matches the existing `wuwei reply` draft path and is deferred.
- The pack's first risk, else first change, stays the headline rule; changes list merged items first.
- No new config keys, so the template and `docs/site/configuration.md` key tables do not change; only the pack and nudges prose there is updated.
