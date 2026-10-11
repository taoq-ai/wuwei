# Implementation Plan: tracker lifecycle updates become outward duties; the ticket walls go

**Branch**: `b7-leftovers` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at d60253b8. **[after 16]**: part 16 (#838) already deleted `tracker.pending`,
`tracker._held`, the draft branches of `tracker.create` and `tracker.log`, and the
`drafts.approve` branch of `plan approve`; it kept `outbound.code_host_orgs` and
`outward._external_tracker` for this part. **[after 17]**: `guards/edges.py` holds the edges;
`guards/__init__.py` lines moved. Parts 18 (#840) and 19 (#841) run first on this branch:
`commands/next.py`, `commands/doctor.py`, `closing.py`, `dispatch.py` and `plan.py` lines
shifted, so locate code by function name.

## Summary

Delete the one ticket rule (`tracker.check`, `in_force`) and every refusal it fed, the
auto-create at approve and add, `skip_tiers`, `strict_close` and `required`. Make the three
lifecycle updates duties: `dispatch.tracker_call` records `duty.due` and `duty.done`, the PR
link and merged note move from `tracker log` into the duty, `next` lists open duties, and
`close` waits on them.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion of the walls (about 250 lines of code,
600 of tests); the duties add about 60 lines (two events, one pure reader, one `next` row, one
close finding). Four config keys retire.

## Constitution Check

- I: nothing added. II: `tracker_call` never raises (as today); `close` exits 1 on an open duty.
- III: one performer (`dispatch.tracker_call`), one reader (`tracker.open_duties`), shared by
  `next` and `closing`.
- IV: red tests first for each US1 scenario (they refuse today), the duty events, the `next`
  row and the close finding.
- V: the duty is two events on the function that already records `tracker.call`; no new
  module, no state key.
- VII: the outward edges are unchanged; tracker writes stay WUWEI port writes (part 16); the
  external-tracker label guard stays.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `tracker.check` / `in_force`, refusals in `plan approve`, `plan add`, `build next`, `dispatch next`, agent launch | (a) a ticket wall; the planner reasons about tickets before work | nowhere (owner, 2026-10-11) |
| Auto-create at approve and add, `tracker.skipped`, `plan._skipped`, `skip_tiers`, the light `later` rule | (a) machinery of the wall | nowhere; `tracker create` stays on demand |
| `close` under `strict_close`: merged ticket not done; shipped without a ticket | (b) for "not done" (an outward update missed); (a) for "without a ticket" | "not done" becomes the `tracker.done` duty that `close` waits on; "without a ticket" goes |
| doctor `tracker` row's `required` coupling | (a) | the row checks a configured tracker only |
| Lifecycle moves without a record of done | (b) outward process followed | duties: `duty.due`/`duty.done`, `next` row, close wait |
| relabel's host-terminal text | (a) terminal step (#831) | the reason names `bin/wuwei init --upgrade`, then `tracker move` |
| External-tracker label guard (`_external_tracker`, `code_host_orgs`) | (b) no write to a tracker someone else owns | kept |

## Files to delete

None. Test cases go with their code (below).

## Files to edit, code (17)

### `cli/wuwei/tracker.py`

- Delete `in_force` (71-72) and `check` (84-102) **[after 16: `pending` and `_held` are gone]**.
- `_entries` (202-258): delete the `pr.raised`/`pr.claimed` branch, the `phase == 'merged'`
  `close` entry (keep `Phase: <phase>.` progress for other phases), and the
  `decision.decided` branch with its `decision.naming` call and imports.
- `log` (266-339): the fold category is the first folded kind (`next(iter(counts))`);
  `settings['auto']` goes.
- `relabel` (366-382): the missing-label reason becomes `f'{item} not moved to {name}: the
  tracker label {quoted} is missing; run bin/wuwei init --upgrade, which creates it, then
  bin/wuwei tracker move {item} in_review'` (no host terminal; init asks its own card if it
  needs the owner).
- Add `open_duties(rows)`: from event rows (dicts with `kind` and `payload`), the
  `(item, duty, command)` list of `duty.due` pairs with no later `duty.done`, in due order.
  Pure, no imports beyond what the module has (hook paths import it lazily).

### `cli/wuwei/dispatch.py`

- `tracker_call` (361-390): read `ticket = tickets.<item>.id` and `pr = items.<item>.pr`.
  When the adapter is not `none` and `ticket` is recorded:
  - append `duty.due` `{item, duty: 'tracker.' + action, ticket, command: f'wuwei tracker move {item} {action}'}`;
  - `claim`: `port.claim`; `in_review`, `done`: `port.transition` (with relabel for
    `in_review`), then, on exit 0 and with a PR, `port.comment(ticket, f'[{day} {item}] Pull
    request: {pr}.' | f'[{day} {item}] Merged in {pr}.', 'pr' | 'close')`;
  - append `duty.done` `{item, duty, ticket, pr}` when every step returned 0.
  Without a recorded ticket it keeps today's behaviour (the item id as the ticket, no duty).
  `tracker.call` is still appended with the first non-zero step's exit and reason.
- `next_step` (517-519): delete the `tracker.check` refusal.

### Other code

- `cli/wuwei/shepherd.py:404` (`claim_pr`): after `state.record_pr(..., raised=False)`, call
  `dispatch.tracker_call(item, 'in_review', root)`; print the reason on a non-zero exit as
  `raise_pr` does (362-364).
- `cli/wuwei/commands/tracker.py:30`: `move` choices `('claim', 'in_review', 'done')`; help
  text.
- `cli/wuwei/commands/build.py:245-248`: delete the ticket refusal (this also frees
  `pr_actions` adopted fix rounds, 396-402).
- `cli/wuwei/guards/agent_launch.py:288-291`: delete the ticket check.
- `cli/wuwei/guards/__init__.py:44-45`: `CAPACITY` drops `' has no ticket: '` and the comment
  "a missing ticket".
- `cli/wuwei/plan.py`:
  - `_skipped` (168-171) and its two `tracker.skipped` appends (482-483, 601-602) go;
  - `_tickets` (174-186): shown whenever `adapters.tracker` is not `none`, no `skip_tiers`
    filter;
  - `approve`: delete the auto-create loop (428-440) **[after 16]** and the in-write
    `tracker.check` refusal (454-460); tickets are still recorded from candidates and carried
    days;
  - `add`: delete the owner-item create and the missing refusal (538-551).
- `cli/wuwei/closing.py:169-201` (`unresolved`): replace the ticket block with: unless
  `adapters.tracker` is `none`, each `tracker.open_duties(rows)` entry is a finding
  `f'{item}: {duty} not recorded: bin/{command}'`; `strict_close` goes.
- `cli/wuwei/commands/close.py:67-75`: the comment "strict_close is the close rule" goes.
- `cli/wuwei/commands/next.py`:
  - `_seen`: parse lines holding `"duty.` and return their rows (keeps the #346 budget);
  - `step`, after the item loop: unless `config['adapters']['tracker'] == 'none'`, append one
    `_row('duty', f'{label}: the tracker {action} update is due and not recorded.', command,
    item=item)` per open duty to `found` (before PR rows, so terminal items are covered);
  - the `finding` row drops "its ticket follows after it ships".
- `cli/wuwei/commands/doctor.py`: `_tracker` (637-657) checks any configured tracker; the fix
  names the credentials or `bin/wuwei config set adapters.tracker none`; `_tracker_labels`
  (660-672) drops the `required` branch.
- `cli/wuwei/workspace.py`: SCHEMA `tracker` drops `required`, `skip_tiers`, `strict_close`,
  `auto` (92-94, 98); `RETIRED` gains them; bump `CONFIG_CACHE_VERSION`.
- `cli/wuwei/commands/event.py`: producer rows `duty.due`, `duty.done` (`wuwei tracker
  lifecycle`); drop `tracker.skipped`.
- `cli/wuwei/signal.py`: `duty.due` and `duty.done` silent; `tracker.call` is silent when the
  reason starts with `'tracker adapter is none'`; drop `tracker.skipped` if listed.
- `cli/wuwei/outward.py` **[after 16]**: any comment naming `tracker.auto`.

## Files to edit, tests (about 18)

Deleted with the walls:

- `tests/test_tracker.py`: `test_missing_reason_names_the_card` (21),
  `test_owners_none_is_skipped` (27), `test_check` (32-43), `test_small_item_reads_later` (47);
  any part 16 survivor of `test_pending_items_draft_names_approval` (69).
- `tests/test_agent_launch.py:636-641`; `tests/test_enforce.py:70` row.
- `tests/test_dispatch.py`: `test_dispatch_refuses_an_item_without_a_ticket` (1547) and
  `test_light_item_skips_the_ticket_until_its_tier_rises` (1562) become "dispatch next returns
  the gates for an item with no ticket" (red first); `test_issue_acceptance_ticket_then_dispatch`
  (1660) keeps only the dispatch half.
- `tests/test_build_next.py:425`: becomes "build next with no ticket writes the action; with a
  ticket it claims and records the duty" (red first).
- `tests/test_pr_actions.py:570`: an adopted fix round needs no ticket (red first).
- `tests/test_intraday_intake.py:230, 347`: the ticket refusal and the draft go; `plan add`
  admits an owner item with no ticket (red first). (Part 21 deletes the rest of the intake
  cases.)
- `tests/test_plan.py`: `test_approve_links_and_opens_the_proposed_tickets` (685) keeps the
  link half and asserts no create; delete `test_owners_none_is_approved_without_a_ticket`
  (704), `test_a_small_item_is_approved_without_its_ticket` (721),
  `test_a_failed_open_does_not_hold_a_small_item` (729),
  `test_light_candidate_is_approved_without_a_ticket` (737); add "approve admits items with no
  ticket" (red first).
- `tests/test_stop.py`: `test_close_needs_the_merged_ticket_done` (838) becomes "close waits on
  an open `tracker.done` duty and names `tracker move`"; delete
  `test_close_names_the_ticket_a_small_item_shipped_without` (876).
- `tests/test_doctor.py`: `test_tracker_row` (1142), `test_tracker_row_on_a_rate_limit` (1157),
  `test_github_tracker_row_names_the_auth_fix` (1216) drop `required`; the fix names
  `adapters.tracker none`.

Duties (red first):

- `tests/test_dispatch.py`: `tracker_call` appends `duty.due` then `duty.done` on success; no
  `duty.done` when the move or the comment fails; no duty without a recorded ticket; the
  in-review comment text; keep `test_tracker_call_uses_the_ticket` (1575) and the relabel cases
  (1623-1653), with the relabel text check updated.
- `tests/test_tracker.py`: `open_duties` (due, done, retry, order);
  `test_log_pr_merge_and_carry` (311) asserts no `Pull request:` or `Merged in` entry; the fold
  category case (374) uses the first folded kind; `test_tracker_move_runs_the_shared_move`
  (453) adds `claim`.
- `tests/test_next.py`: a `duty` row for an open duty, also for a merged item, listed in
  `rows`; none with `adapters.tracker = "none"`.
- `tests/test_shepherd.py`: `pr claim` runs the in-review duty; `test_raise_prints_the_tracker_reason`
  (346) unchanged.
- `tests/test_merge.py:535, 546`: the done duty is recorded on merge.
- `tests/test_signal_status.py`: the new kinds; `test_tracker_none_is_silent_but_tracker_failure_warns`
  (312) uses the full reason text.
- `tests/test_linear_loop.py:101, 121`: run (order and failures); update if they count events.
- `tests/test_workspace.py:231, 1534-1541`, `tests/test_config_transition.py:16` (the
  `required = true` replace) and its retired-keys fixture.
- `tests/test_reasons.py`: delete the LEFT row `('tracker.py', 'init --upgrade in a host
  terminal', 20)`.
- `tests/test_outward.py` **[after 16]**: `tracker.auto` cases left after part 16 go;
  `test_tracker_github_outside_code_host_orgs_drafts` keeps its label half if any.

## Files to edit, governance and docs (11, plus generated agents)

- `charters/lead.md:12` (1 version bump): a candidate carries the open ticket when it has one;
  drop "With ... `tracker.required` on", "the gate opens a new one", the `null` none and the
  light exception.
- `charters/planner.md:11-12` (version bump): drop "Approve opens the tickets", the plan add
  ticket draft, "When an item still has no ticket ...", and the close ticket line; add one
  sentence: "When `wuwei next` returns a `duty` row, run its command."
- `bin/wuwei agents build`.
- `templates/workspace/config.toml:35-37, 40`: the four keys and their comments go; `log`
  comment says `pr` is written by the in-review duty.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 4.1 (171) and 9.1 (1558-1561): no ticket check at launch;
  - 5.11 (1077-1223): intro, Configuration (drop `required`, `skip_tiers`, `strict_close`,
    `auto`), "Enforcement" and "Close" replaced by "Duties" (the spec's table and events),
    Comments (the PR link and merged note are duties), doctor (no `required`), Approval (the
    tier text part 16 left);
  - 4.9 tracker writes (404-412) if part 16 left `tracker.auto`.
- `docs/site/concepts.md:128-136, 224-250`; `docs/site/configuration.md:33-35, 38`;
  `docs/site/daily.md:267-271`; `docs/site/reference.md:42, 60`; `docs/site/adapters.md:97-101`.
- `.specify/memory/constitution.md`: unchanged (its tracker bullet governs WUWEI's own GitHub
  issues, not the product rule).

## RETIRED

`workspace.RETIRED` gains `tracker.required`, `tracker.skip_tiers`, `tracker.strict_close`,
`tracker.auto`.

## Risks

- **Dead end.** A tracker that never answers holds close. The owner's way out is
  `adapters.tracker = "none"` (Assumption 6); `next` and `close` both honour it. Batch 8's
  property test gets the rows "no item done with an open duty" and "every due duty in next".
- **Double comments.** If `_entries` keeps the `pr` or merged entries, the link posts twice;
  the `tests/test_tracker.py` log case asserts it does not.
- **Day boundary.** Duties are read from today's events; a duty left open on a carried item
  does not reappear tomorrow. Close holds the day until it is done, so this only happens when
  the owner overrides; batch 8 owns cross-day derivation.
- **Hook budget.** `next` runs at SessionStart; the duty rows come from lines `_seen` already
  reads, filtered by `"duty.`.

## Handoff

- Batch 8 (part 22): derive open duties from `duty.due`/`duty.done` (fields above); add the
  duty rows to the loop property test.
- Part 23: the channel ping, shepherd replies and day summary become duties on the same two
  events; `obligations` and `closing` move into `next` as duties.
