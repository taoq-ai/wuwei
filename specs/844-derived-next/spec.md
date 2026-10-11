# Feature Specification: derived next; every ready launch, due duty or one owner decision; state.json becomes a cache

**Feature Branch**: `b8-derived-next` (feature directory `specs/844-derived-next/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #844, part 22 of the #789 deletion pass (batch 8, the risky one): "feat(next):
derived state; next returns every ready launch, due duty or one owner decision; state.json
becomes a cache".

## Context

Today `state.json` is the day's truth. Every command reads it through `state.read_state`, and
`wuwei next` (`commands/next.py`) walks it to return one row:

- the first runnable item wins and the rest wait in a `rows` queue without their prompts
  (#666);
- an owner decision on one item hides ready launches on others;
- `build next` and `dispatch next` can answer `done`, `park` or `escalate`, and `next.run`
  loops up to eight times before it gives up with "the day did not settle";
- a PASS recorded before the builder moved the head still counts, so the PR is raised without
  a pass at head (#669);
- a PR merged on the host while the record says raised is still offered as a `pr act` (#729);
- a raised PR is never pinged and a merged item never gets its tracker update from `next`;
- `depends_on` is never read, so an item waiting on another takes a seat (#637);
- deleting `state.json` restarts the day at the session row.

Commit b34f15a3 on this branch adds `tests/test_loop.py`, which characterises today's `next`:
a property test over 300 generated day worlds, one test per recorded scheduler dead end and
state drift case, and a state.json deletion test. 22 tests pass and 9 are strict xfails, each
naming one gap above. This part makes every xfail pass and keeps every passing test passing.

The owner rules this part binds to (2026-10-11):

- process lives in code, judgment stays with the model: the code decides what is ready, due or
  waiting on the owner; the model decides what to build and writes every text;
- `next` offers, never commands: it lists what is ready and the planner does it;
- no terminal steps: an owner decision is one Owner step card in the session (#831);
- PARK parks in code, with no card;
- outward duties are followed in code: PR raised, ping the configured channel; review activity,
  shepherd (a reply to every thread); merged, tracker or page update; day end, summary.
  Duties are configured per workspace, `next` lists every due duty with its prompt, `close`
  waits on them, and the model writes the content.

## What `next` reads after this part

| Input | What it says | Read how |
|---|---|---|
| Plan file | `plan.md` exists (proposed); `proposal.json` candidates (scope, evidence, repo, `depends_on`) | files |
| Plan records | approval, admission, park, carry, resume, owner settings (`plan.approved`, `plan.added`, `plan.disposed`, `plan.resumed`, `plan.set`, `spec.override`) | the event log |
| Git worktree list | each item worktree exists and its HEAD sha | the worktree's `.git` pointer and git's per-worktree registry files, no subprocess |
| Verdict files | `decisions/gate-<role>-<item>.md`: lints, `Verdict:`, `Head:` | files |
| Cached PR listing | `prs.json`: each item PR's state (open, merged, closed), head, checks (pending, red, green), owner_merge label, latest outside review activity | file; refreshed by one code-host list call |
| Seat ledger | which seats run or stopped, their brief, agent id and head | the `seat launched` and `seat stopped` rows of the event log |
| Loop records | build loop record, fix rounds opened, gate receipts, owner answers, duty records, steward runs | the event log |

The event log (`events.jsonl`) is append-only and kept by the owner's constraints. Every state
write already appends one event; after this part that event carries the write's patch, so the
day's records fold back from the log. `state.json` is a cache of that fold: written after each
write, read only when its recorded log size equals the log's, never required. World facts (the
worktree HEAD, verdict files, the PR listing) are read fresh on every call and never cached.

## What `next` returns after this part

One JSON object. Before the loop (no workspace, no repository, no planner session, the lead,
the proposal, the morning gate) it is one row, as today: each of those is the only thing the
day can do. Once the morning gate is approved it is the set:

```
{"state": "set", "launches": [...], "duties": [...], "decision": {...} or null,
 "rows": [...], "why": "...", "then": "..."}
```

- `launches`: every ready launch, each `{kind, item, ...}` with its exact commands and, for a
  seat, its prompt and `agent_type`. Kinds: `build` (start or continue a builder), `fix`
  (a fix round, gate or PR), `gates` (gate seats, their brief and receive commands), `raise`
  (the shepherd seat that runs `pr raise --item`), `merge` (`wuwei merge <pr>`), `pr`
  (`wuwei pr act <pr>` for a conflicted PR), `stop` (`wuwei seat stop` for a stuck seat).
- `duties`: every due duty, each `{duty, item, prompt, record}`; `record` is the command that
  records it done.
- `decision`: at most one owner decision, `{item, why, command, card}`; the planner asks the
  card with AskUserQuestion and runs the command again on Yes.
- `rows`: one status row per open item in plan order (`build`, `verdicts`, `pr`, `merge`,
  `wait`), runnable first and PR rows last, for reading only.

When the set is empty, `next` returns one day row: `steward` (launch on the newest brief),
`wait` (seats or a held item running), `close`, `retro`, `promote`, `retro-applied`,
`report`, `closed`. `closed` is offered only when every approved item is merged, parked or
carried, every duty is recorded, and the retro and report are written.

`escalate`, `done`, `park` and `parked` never reach the planner: the item-level dead ends of
`build next` and `dispatch next` are resolved inside the derivation. The eight-step settle
loop in `next.run` goes.

## The item decision table

For each approved item that is not carried, in plan order (precedence top down):

| World | Offer |
|---|---|
| PR merged in the listing | none; the item is merged (its duties follow) |
| PR closed unmerged in the listing | none; the item reads as parked, reason `PR closed on the host` |
| a PARK verdict at the current head, no owner resume after it | none; parked in code, shown in `why` and the report |
| parked by the round cap or a stuck build loop, not answered No | decision: `wuwei plan resume <item>` card |
| other parks (PARK verdict, owner No, carry) | none |
| no worktree and no PR, `depends_on` all merged, CAP not reached | launch `build` (worktree add, builder brief, launch) |
| recorded worktree gone from the git registry, not merged | launch `build` with `wuwei worktree add <item>` first |
| builder seat running, or a fast check running | none (wait) |
| build loop not done (ready, check, failed checks) | launch `build` (the build loop's action) |
| held on a broken main (#648) | none (wait on the fix item) |
| a gate of its tier set without a received verdict that lints and whose Head is the current worktree HEAD | launch `gates` (initial, delta or re-check at head) |
| a blocking verdict (FIX, PARK, ESCALATE) and fix rounds used at the cap | decision: `wuwei dispatch next <item>` card |
| an ESCALATE verdict | decision: `wuwei dispatch next <item>` card |
| a FIX verdict | launch `fix` |
| every gate passes at head, no PR | launch `raise` |
| PR open, checks red, rounds below the cap | launch `fix` (`wuwei pr act <pr>`) |
| PR open, checks red, rounds at the cap | decision: `wuwei pr act <pr>` card |
| PR open, conflicted | launch `pr` |
| PR open, green, owner_merge set | decision: `wuwei merge <pr>` card |
| PR open, green, the merge policy recorded an owner block (`merge.policy_blocked`) | decision: `wuwei merge <pr>` card |
| PR open, green | launch `merge` |
| PR open, pending | none; it waits on people |

The precedence of verdict rows follows today's `dispatch.next_step`: a missing or stale gate
first, then the cap, then PARK, then ESCALATE, then FIX. CAP counts running builder seats from
the seat ledger. New `build` launches start in plan order while running builders plus new
starts stay below CAP; a gate that waits for host seats starts no new build (design 5.3). The
decision is the first in plan order; the others wait until it is answered.

## Duties after this part

| Duty | Due when | Prompt says | Recorded by |
|---|---|---|---|
| `ping` | the item's PR is open or merged and no `ping` is recorded | post the review request for the PR to `shepherd.review_channel` | `wuwei pr ping <pr>` on a post, or `wuwei duty <item> ping --evidence <link>` |
| `shepherd` | the listing shows outside review activity newer than the last `shepherd` record | launch the shepherd seat to reply to every open thread (`pr act --reply`) | `wuwei duty <item> shepherd --evidence <link>` |
| `tracker` | the item is merged and no `tracker` is recorded | move the ticket to done with the PR link, or update the configured page | `wuwei tracker done <item>` on exit 0, or `wuwei duty <item> tracker --evidence <link>` |
| `summary` | the report is written and no `summary` is recorded | post the day summary to the owner's channel (`outbound.owner_channel`) | `wuwei duty day summary --evidence <link>` |

A duty is due only when it is on in `[duties]` (configured per workspace). The model writes
the content; the code lists the duty until it is recorded. Sends to other people pass the
outward allowlist (#838); the owner's own surfaces are local. `close` refuses while a duty is
open, naming it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every ready launch, with its prompt, in one answer (Priority: P1)

**Why this priority**: the study days lost hours to one-row answers: a second ready item
waited in a queue without its prompt, and an owner question hid runnable work.

**Independent Test**: `tests/test_loop.py::test_every_ready_launch_is_offered`,
`test_666_a_pr_waiting_on_people_never_hides_runnable_work`, `tests/test_derive.py`.

**Acceptance Scenarios**:

1. **Given** two queued items and CAP 2, **When** the planner runs `wuwei next --json`,
   **Then** `launches` holds a `build` entry for each, each with its commands and prompt.
2. **Given** one item at its gates and another whose verdict ESCALATEs, **When** `next` runs,
   **Then** `launches` holds the gates of the first and `decision` is the card of the second.
3. **Given** a PR waiting on people and an item at its gates, **When** `next` runs, **Then**
   the gates are offered and the PR adds no launch.

---

### User Story 2 - Nothing ready is exactly one owner decision (Priority: P1)

**Why this priority**: the owner answers one card at a time (#831); a dead end with no
action, or two questions at once, is the failure the owner named.

**Independent Test**: `test_nothing_ready_is_exactly_one_owner_decision`,
`test_never_two_owner_decisions`, `test_623_...`, `test_732_...`.

**Acceptance Scenarios**:

1. **Given** a FIX verdict at the round cap and nothing else open, **When** `next` runs,
   **Then** the answer is one decision: the Owner step card of `wuwei dispatch next <item>`.
2. **Given** a PR whose checks are red at the round cap, **When** `next` runs, **Then** the
   answer is one decision, never a `pr act` row to run.
3. **Given** a green PR with owner_merge set, **When** `next` runs, **Then** the decision is
   the card of `wuwei merge <pr>` at once, read from the plan record and the listing label.

---

### User Story 3 - A pass counts only at the current head (Priority: P1)

**Why this priority**: #669: a PASS received before the builder moved the head raised a PR
that no gate had read.

**Independent Test**: `test_never_a_raise_without_a_pass_at_head`,
`test_669_a_pass_at_an_old_head_is_no_pass`.

**Acceptance Scenarios**:

1. **Given** three PASS verdicts whose `Head:` is an older commit than the worktree HEAD,
   **When** `next` runs, **Then** it offers `gates` (a re-check at the current head), not
   `raise`.
2. **Given** a fix round moved the head, **When** the blocking gates run their delta, **Then**
   the gates that passed before re-read the round's diff and rewrite their `Verdict:` and
   `Head:` lines at the new head (the light re-read of design 5.3), and `raise` waits for all.

---

### User Story 4 - Outward duties are listed until recorded (Priority: P1)

**Why this priority**: outward duties (owner, 2026-10-11): the outward process must be
followed, in code.

**Independent Test**: `test_every_due_duty_is_offered`, `test_never_done_with_an_open_duty`,
`tests/test_derive.py` duty rows, `tests/test_close_branches.py` duty finding.

**Acceptance Scenarios**:

1. **Given** `[duties] on` holds `ping` and a raised PR with no ping recorded, **When** `next`
   runs, **Then** `duties` holds `ping` for the item with its prompt and record command.
2. **Given** a merged item with `tracker` on and no tracker record, **When** every other item
   is done, **Then** `next` lists the `tracker` duty and offers no `close`, `retro`,
   `report` or `closed`.
3. **Given** an open duty, **When** the planner runs `wuwei close`, **Then** it exits 1 naming
   the duty and its record command.
4. **Given** `wuwei duty item-1 ping --evidence <link>`, **When** `next` runs again, **Then**
   the duty is gone.

---

### User Story 5 - state.json is a cache (Priority: P1)

**Why this priority**: a day must survive a lost or stale `state.json`; drift between the
record and the world was half the study days' state bugs.

**Independent Test**: `test_deleting_state_json_between_two_calls_changes_no_answer`,
`test_729_a_pr_merged_on_the_host_is_merged`, `tests/test_state.py` fold cases.

**Acceptance Scenarios**:

1. **Given** any day, **When** `state.json` is deleted between two `next` calls, **Then** the
   second answer equals the answer without the deletion.
2. **Given** the listing says a PR merged while the records say raised, **When** `next`
   runs, **Then** the item is merged: no `pr` or `merge` launch, its duties follow.
3. **Given** a `state.json` whose recorded log size differs from the log, **When** any command
   reads the day, **Then** it reads the fold, not the file.

---

### User Story 6 - Dependencies hold a seat back (Priority: P2)

**Why this priority**: #637 (open): an item whose dependency has not shipped took a seat.

**Independent Test**: `test_637_an_item_waiting_on_another_takes_no_seat`.

**Acceptance Scenarios**:

1. **Given** item-2's candidate says `depends_on: [item-1]` and item-1 is not merged, **When**
   `next` runs with free CAP, **Then** item-1 gets a `build` launch and item-2 none.

---

### Edge Cases

- A recorded worktree removed by hand (#517): the item's next `build` launch starts with
  `wuwei worktree add <item>`; a PR still open keeps its PR steps.
- The PR listing older than `pr.poll_seconds`: `next.run` refreshes it with one code-host
  list call before deriving; the hook path and `next.step` never call out. A failed refresh
  keeps the old listing and names its age in `why`.
- A PR WUWEI just raised or merged and the listing not yet refreshed: `pr raise`, `pr act`
  and `merge` refresh the listing after they act; until then the `pr.raised` record keeps the
  item raised.
- A verdict file edited after its receipt (verdict or Head differs): it counts as not
  received; `gates` offers the receive or re-check again.
- A legacy `escalated` phase in an old day's records reads as parked.
- An old day with only `state.json` and events without patches (written before this part):
  the fold falls back to that day's `state.json` once and writes one `state.migrated` event
  with the whole state as its patch, so later reads need no file.
- A repository whose refs live in `packed-refs` only: the HEAD reader resolves the ref there.
  A reftable repository is not read; the item reads as having no worktree HEAD and the gates
  wait, named in `why` (ceiling, see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `state._write_state` appends its event with a `patch` (the top-level keys the
  update changed, and for `items`, `builds`, `seats`, `gate_verdicts` and `tickets` the
  changed entries) before it writes `state.json`; the cache records the log size it reflects.
- **FR-002**: `state.read_state` returns the fold of the day's patches over `DAY_DEFAULTS`
  with the world overlays (FR-004); it reads `state.json` only when its recorded log size
  equals the log's. A missing `state.json` is never an error; the snapshot check goes.
  Writers fold without the overlays, so a derived fact is never written back as a record.
- **FR-003**: `_validate` keeps the schema and type checks and drops the lifecycle checks
  (legal transitions, `resume_phase`, new items start at `planned`); `_move` stops calling
  `_check_transition`. The phase a writer records is the loop's own log; FR-004 corrects it.
- **FR-004**: one new module, `cli/wuwei/derive.py`, holds the world readers and overlays:
  `head(path)` (the worktree's HEAD sha from its `.git` pointer and git's registry files, no
  subprocess), `listing(root)` and `refresh(root, config)` (the cached PR listing),
  `overlay(data, root, config)` (merged or closed on the host, worktree gone, PARK at head,
  verdict at head) and `offers(data, root, config)` (the decision table, pure: no write, no
  subprocess).
- **FR-005**: `next.step(root)` returns the day row or the set (launches, duties, decision,
  rows) from `derive.offers`; it writes nothing and runs no subprocess. `next.run` refreshes a
  stale listing, then resolves each launch into its prompt through the existing resolvers
  (`build.next_action`, `dispatch.next_step`, `dispatch.raise_action`, `dispatch._start`,
  `pr act`, `merge`), which append their loop records; it records `next.action` once.
- **FR-006**: `dispatch.next_step` treats a received verdict whose Head is not the current
  worktree HEAD as missing for its round; `dispatch.receive` replaces a stale receipt of the
  same round; after a fix round every gate of the tier set re-checks at the new head (blocking
  gates by the delta round, passing gates by the light re-read).
- **FR-007**: the round cap and an ESCALATE verdict are one Owner step card of
  `wuwei dispatch next <item>` as today (#834); a cap park or stuck-build park is the
  decision of `wuwei plan resume <item>` until the owner answers; a PARK verdict at head reads
  as parked without a write or a card.
- **FR-008**: `dispatch.launch_set` takes its entries from `derive.offers` and keeps the host
  measure (`host.seats`, the #658 rule) for the free seats; `wuwei dispatch next --all`
  prints it.
- **FR-009**: `[duties]` in `workspace.SCHEMA` and the template: `on`, a list from `ping`,
  `shepherd`, `tracker`, `summary`. `init` and `init --upgrade` write `on` from what the
  workspace configures: `ping` when `shepherd.review_channel` is set, `tracker` when
  `adapters.tracker` is not `none`, `shepherd` when `adapters.code_host` is not `none`, and
  `summary` always.
- **FR-010**: `wuwei duty <item|day> <duty> --evidence <text>` appends `duty.recorded`;
  `pr ping` on a post and `tracker done` on exit 0 append it too.
- **FR-011**: `closing.unresolved` reports each open duty as a finding naming its record
  command; `wuwei close` exits 1 while one is open.
- **FR-012**: `derive.offers` reads `depends_on` from the item's proposal candidate (#637).
- **FR-013**: the code-host port gains `pulls(repo)`: one list call returning, per PR, ref,
  state, head, draft, checks rollup, labels and the latest outside review or comment time;
  the GitHub adapter implements it with one `gh pr list --state all --json ...` call per
  repository.
- **FR-014**: the raise check (`gate_check`, in `merge.py` after #839) requires every gate of
  the tier set to pass at the current HEAD; the exemption for a gate that was not re-checked
  goes.
- **FR-015**: the planner loop text (`next.LOOP`, `THEN['set']`), `skills/wuwei-plan` and
  `skills/wuwei-report`, `charters/planner.md` and design 5.2, 5.3 say what the code does: do
  every launch and every duty, ask the one decision.

### Key Entities

- **Patch**: the part of the day's records one write changed, carried by its event.
- **Offer**: one ready launch, one due duty or the one owner decision.
- **Duty**: an outward step an item phase or the day end owes, configured per workspace,
  listed until recorded.

## Success Criteria *(mandatory)*

- **SC-001**: `tests/test_loop.py` has 31 passing tests and no xfail.
- **SC-002**: no module reads `state.json` except the cache read in `state.read_state`
  (grep in T030).
- **SC-003**: `next.step` writes nothing and runs no subprocess (the loop test's environment
  refuses both).
- **SC-004**: the touched test files pass; CI is the gate.

## Assumptions

1. **The event log is the sixth input.** The issue names five derived inputs; approvals,
   parks, owner answers, fix rounds, gate receipts and duty records are facts only WUWEI
   knows, and every one is already an append-only event. Carrying the write's patch makes
   them fold back without `state.json`. The owner keeps events as append-only logs.
2. **The loop's own phase stays, corrected by the world.** Recomputing every phase from the
   world alone would rewrite the build loop and most of the 444 fixture writes in the suite.
   The record says what WUWEI did; the overlays win wherever the world disagrees (merged or
   closed on the host, worktree gone, head moved, PARK at head). That covers every recorded
   drift case. Overturn: a drift case the overlays miss.
3. **Strict pass at head.** "Never a raise without a pass at head" is read literally: after a
   fix round the gates that passed re-read the round's diff at the new head, as light items
   already do (design 5.3). Cost: one short re-read per passing gate per fix round. Overturn:
   the owner prefers the delta-only rerun of #732 and accepts a raise on an older head.
4. **The decision rides along with launches.** The set carries at most one decision next to
   the launches, so the owner answers while seats work; when nothing else is ready it is the
   whole answer. The issue's "or" holds for the empty case and "never two" always holds.
5. **owner_merge is a decision at once.** The plan record and the listing label say it before
   any merge attempt, so the `pr` row that today runs only to be blocked goes;
   `test_729_an_owner_merge_row_ends_when_the_pr_merges` changes its first expectation
   accordingly (stricter, not looser).
6. **The worktree HEAD is read from files.** `next` runs on hook paths (SessionStart) and the
   loop test refuses subprocesses. The reader follows `.git` (gitdir), the registry `HEAD`
   and loose or packed refs, about 20 lines. Ceiling: reftable repositories; upgrade path: the
   vcs adapter's `worktrees` off the hook path.
7. **The listing is refreshed by `next.run`, not by the watch.** One list call per repository
   when the listing is older than `pr.poll_seconds` (120 s) and an item has a PR. The watch's
   PR polling and `merge.monitor`'s tracker call become redundant here and go in part 23.
8. **Duties default from the configured channels.** A ping with no review channel would be
   noise; `init --upgrade` turns on the duties whose channel the workspace has.
9. **Batches 5 to 7 land first.** This part is designed against their end state: part 16
   (`outward.allow`; owner surfaces local) gates duty sends; part 17 (`gate_check` in
   `merge.py`, exact argv edges, `commit_push.py` moved); part 18 (no `mcp` row in `next`);
   part 19 (no `docs` row in `next`, no docs value in the gate step); part 20 (tracker
   lifecycle updates as duties: if it lands a duty record or command, this part reuses it
   and FR-010 shrinks to the missing kinds); part 21 (no discovery intake; `plan propose`
   ranks). Each dependency is marked in plan.md.
10. **No config key retires.** `[duties]` is new; `pr.poll_seconds` is reused.

## Deferred

- Part 23 deletes what this part replaced; plan.md lists the modules.
- Part 25 adds the per-edge tests and the final property test; this part's test_loop.py is
  its first half.
