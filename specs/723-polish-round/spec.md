# Feature Specification: an optional polish round after a pass

**Feature Branch**: `723-polish-round`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #723 (owner, 2026-10-10, item 49): "when every gate passes, WUWEI
raises the PR at once. Cheap hardening the reviewers recommended (an fsync, a lock, a
symlink check) needs a whole new item: plan add, worktree, brief, build and three gates."
Deliver: after a PASS with non-blocking notes, `dispatch next` offers `polish` (the builder
fixes only the listed notes, in the same worktree, within a small budget), then one gate
(the reviewer who wrote the notes, or quality) re-checks the delta; the PR is raised after
that. The planner may skip it (`dispatch skip-polish <item>`), and
`gates.polish = never|offer|always` configures it (default `offer`). The notes travel in the
brief and the polish round is recorded on the item.

Governing: docs/specs/2026-09-24-wuwei-design.md#5.3 Rules

## Root cause

Reproduced in-process on `main` (d3b7066): a temporary workspace built like the
`tests/test_dispatch.py` `root` fixture, item `A` at `gate`, three verdicts received with
`dispatch.receive`: arch PASS with one `blocks: no` finding, quality PASS with one
`blocks: no` finding, security PASS with none.

| Step | Today |
|---|---|
| `receive` of each verdict | records `notes` of length 1, 1 and 0 (dispatch.py:701, 705) |
| `dispatch next A` | `{'action': 'raise', 'notes': []}` |
| `load_config(...)['gates']` | no `polish` key |

In the code:

- `cli/wuwei/dispatch.py:376-379`: at phase `gate`, when no gate wrote FIX, `next_step`
  returns `{'action': 'raise', 'notes': []}`. The non-blocking notes the gates recorded are
  dropped: they reach neither a builder nor the shepherd brief (`commands/next.py:390-391`
  passes `action['notes']` to `_shepherd`, which writes one `Review note:` line per note).
  Only the delta tail (dispatch.py:396-397) carries notes to the PR.
- There is no path from a pass back to the builder. The only way back is a fix round
  (`build.open_fix`, commands/build.py:179-237), which `next_step` opens only for a FIX
  verdict (dispatch.py:377-382) or a blocking delta (dispatch.py:383-395).
- The delta machinery is keyed to FIX verdicts in five places, so a gate that passed cannot
  re-check a later change: `next_step` fix and delta roles (dispatch.py:349-350, 358-359),
  `delta_due` (dispatch.py:575, the shared rule for `_seats` and the launch guard
  `guards/agent_launch.py:188`), `receive --round delta` (dispatch.py:631-634) and
  `opinion` (dispatch.py:743).
- The readers that decide "gates passed at HEAD" judge a gate on its delta record only when
  its initial verdict was FIX: the PR guard (`guards/pr.py:105`) and its stale-head
  tolerance (`guards/pr.py:125-129`), and the merge verdict digests (`merge.py:344-346`). A
  gate that passed and was then re-checked would be judged on its old head and refused.
- `[gates]` has no `polish` key (`cli/wuwei/workspace.py:139-143`).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: When is polish offered? A: At phase `gate`, when every gate's round-one verdict is
  PASS (no FIX, PARK or ESCALATE), at least one recorded note exists, `gates.polish` is not
  `never`, the item has no `polish` record yet, and its rounds used are below its round cap
  (`dispatch.max_rounds`). Not after a delta: an item that already took a fix round ships
  its residual notes in the PR body, as #623 does today.
- Q: What is the polish round? A: A fix round opened through the existing `build.open_fix`
  with the notes as its feedback. It counts toward `gates.max_rounds` like any fix round
  (I35 holds unchanged), uses the same worktree and builder, and moves the item `gate` to
  `fix`; the build loop moves it to `delta` as for any fix round.
- Q: Which gate re-checks? A: The gate that wrote every note when one gate wrote them all
  (a second opinion such as `quality@codex` included, `goal` on a docs-only item); otherwise
  `quality`, which every gate set except the docs-only `['goal']` holds.
- Q: What do `offer` and `always` do? A: `offer` (default): `dispatch next` returns
  `{'action': 'polish', 'gate', 'notes', 'command': 'wuwei dispatch polish <item>',
  'skip': 'wuwei dispatch skip-polish <item>'}` and writes nothing; the planner runs one of
  them. `always`: `dispatch next` opens the polish round itself and returns the `fix`
  action, as it does for a FIX verdict. `never`: `raise`, as today.
- Q: Skip? A: `dispatch skip-polish <item>` records `items.<item>.polish` with status
  `skipped` and returns `raise` with the notes; the next `dispatch next` raises. It is
  refused unless `gates.polish = offer` and an offer is open.
- Q: What is recorded on the item? A: `items.<item>.polish = {'status': 'opened' |
  'skipped', 'gate': <gate>, 'notes': [<note>, ...]}`, written by the CLI only (the state's
  generic writer already refuses every item key except `note`). Opening writes it in the
  same state write as the fix round (`build.fix_opened`, payload `polish: true`); skipping
  writes event `polish.skipped`.
- Q: How do the notes travel? A: In the fix feedback `open_fix` already passes on: in the
  continue prompt for a resumed builder, in the fresh `<item>-gate-fix` brief body
  otherwise. The re-check gate's continue feedback lists them too.
- Q: "Within a small budget"? A: The feedback bounds the round: fix only the listed notes,
  change nothing else, and leave a note that needs more than a small local change as a
  review note named in the handoff. The build loop's existing `build.max_iterations` and
  `build.stuck_after` still bound it; no new budget key.
- Q: After the re-check? A: The polish gate's delta is read by the existing delta tail: no
  blocking finding raises with that delta's notes; a blocking finding opens the next fix
  round under the cap, or parks at the cap, as #623 does. Polish is never offered twice.
- Q: How do the guards accept a PR after one gate re-checked? A: A gate is judged on its
  delta record whenever one exists (FIX, or the polish gate), and the gates not re-checked
  keep today's stale-head tolerance once any gate was re-checked.

## User Scenarios and Testing

### User Story 1 - A pass with notes gets one polish round before the PR (Priority: P1)

**Acceptance Scenarios**:

1. **Given** item `A` at `gate` with arch PASS carrying one `blocks: no` note, quality PASS
   carrying one, security PASS with none, at the defaults, **When** `dispatch next A` runs,
   **Then** it returns `action: polish` with both notes, `gate: quality` and the two
   commands, and writes nothing.
2. **Given** that offer, **When** `dispatch polish A` runs, **Then** the item moves to `fix`,
   `items.A.polish` is `{'status': 'opened', 'gate': 'quality', 'notes': [...]}`, the
   build record's action feedback names both notes (and its prompt ends with it), and the
   `build.fix_opened` event carries `polish: true` and `round: 1`.
3. **Given** the builder's round done and the item moved to `delta`, **When** `dispatch next
   A` runs, **Then** it asks for `quality` only; a stopped quality seat with an agent id at
   the round-one head is offered one `continue` whose feedback starts `Polish re-check:` and
   lists both notes; `receive A quality <seat> --round delta` records it, while a delta for
   `arch` is refused (`did not need a delta`).
4. **Given** the quality delta PASS, **When** `dispatch next A` runs, **Then** it returns
   `raise` with that delta's notes, and polish is not offered again.
5. **Given** that state, **Then** the PR guard's gate check passes at the new HEAD although
   the arch and security verdicts name the round-one head, and refuses at the new HEAD
   without the quality delta.

### User Story 2 - The owner turns it off or on (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `gates.polish = "never"` and the verdicts of US1.1, **When** `dispatch next A`
   runs, **Then** it returns `raise` at once, with both notes as `notes` (no longer an empty
   list).
2. **Given** `gates.polish = "always"`, **Then** `dispatch next A` opens the polish round
   itself and returns `{'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next
   A'}`.
3. **Given** `gates.polish = "sometimes"`, **Then** the config fails to load naming the
   allowed values.

### User Story 3 - The planner skips it (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the offer of US1.1, **When** `dispatch skip-polish A` runs, **Then**
   `items.A.polish.status` is `skipped`, a `polish.skipped` event is written, it returns
   `raise` with both notes, and the next `dispatch next A` returns the same `raise`.
2. **Given** a skipped or opened polish, **Then** `dispatch polish A` and `dispatch
   skip-polish A` are refused (exit 1) naming `dispatch next`.
3. **Given** `gates.polish = "always"` or `"never"`, **Then** `dispatch skip-polish A` is
   refused naming the config value, and opens no round.

### User Story 4 - The planner's loop shows the offer (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the offer of US1.1, **When** `wuwei next` resolves the item's `verdicts` row,
   **Then** it returns a `polish` row whose command is `wuwei dispatch polish A` and whose
   then line names `wuwei dispatch skip-polish A` as the alternative.

### Edge Cases

- A pass without notes raises at once in every mode.
- A FIX verdict at round one opens a fix round as today; polish is not offered after its
  delta, the delta's notes ship in the PR body.
- The item already used its round cap: no offer, `raise` with the notes.
- Notes only from `quality@codex` (a second opinion): the polish gate is `quality@codex`,
  re-checked through `dispatch opinion`, whose delta path accepts it.
- Docs-only item (`['goal']`): the polish gate is `goal`.
- Light item (`['quality']`): the polish gate is `quality`; the re-check feedback is the
  polish text at every depth.
- The polish delta blocks: the next fix round opens under the cap from the delta (`rotate`
  moves the polish gate's FIX delta to `initial`), and that round's delta is asked of the
  FIX gates, as #623 does.
- A raised item (`pr` recorded) never reads its old polish record as open.

## Requirements

- **FR-001**: `gates.polish` (string, default `offer`, one of `never`, `offer`, `always`) in
  the config schema, the workspace template (commented) and the configuration page.
- **FR-002**: `dispatch.polish_offer(config, row, roles, results, used)` returns `None` or
  `{'gate', 'notes'}` by the rule of the first clarification and the gate rule of the third.
- **FR-003**: `dispatch.next_step` at phase `gate` with no FIX returns the offer (`offer`),
  opens the round (`always`), or returns `raise` with every recorded note (`never`, no
  notes, polish recorded, or at the cap).
- **FR-004**: `dispatch.polish(item)` opens the offered round through `build.open_fix` with
  the polish feedback and records `items.<item>.polish` in that same state write;
  `dispatch.skip_polish(item)` records the skip with event `polish.skipped`. Both are
  refused without an open offer; skip also outside `offer`. CLI: `wuwei dispatch polish
  <item>` and `wuwei dispatch skip-polish <item>`, exit 0 done, 1 refused, 2 could not run.
- **FR-005**: One predicate `dispatch.rechecks(data, item, role)` says whether a gate is due
  a delta: its `initial` verdict is FIX, or it is the polish gate while `polish.status` is
  `opened` and the item has no `pr`. `next_step` (fix and delta phases), `delta_due`,
  `receive --round delta` and `opinion` read it instead of their own FIX test.
- **FR-006**: The re-check gate's continue feedback (in `_seats` and `opinion`) is the
  polish text when the gate re-checks a polish round: the head range, the notes, drop
  closed notes, keep open ones as `blocks: no`, block only on a defect the delta introduced.
- **FR-007**: The PR guard and the merge verdict digests judge a gate on its `delta` record
  whenever one exists; the stale-head tolerance applies to every gate without a delta once
  any gate has one. Behaviour without a polish round is unchanged.
- **FR-008**: `wuwei next` turns a `polish` action into a `polish` row (US4).
- **FR-009**: `charters/_common.md` rule 5 says the polish rule for every seat (builder:
  only the notes; gate: re-check the delta; planner: skip when the notes are not small
  fixes), version bumped, agents regenerated with `bin/wuwei agents build`.
- **FR-010**: Invariant I58 in design 9.2 and `tests/test_invariants.py` (the plan names
  it).
- **FR-011**: `polish.skipped` joins the event command's reserved kinds; the state producer
  message names `wuwei dispatch polish or wuwei dispatch skip-polish` for `items.*.polish`.

## Success Criteria

- **SC-001**: An item whose gates all pass with notes reaches its PR after one builder round
  and one gate, in its own worktree, with no `plan add`.
- **SC-002**: Under `gates.polish = never` the gate-to-PR path is today's, and the notes of
  a round-one pass now reach the PR body.
- **SC-003**: No item takes more fix rounds than its round cap; no item polishes twice.

## Assumptions

- Polish is offered only from round one (phase `gate`). Why: the issue's case is "when every
  gate passes, WUWEI raises the PR at once", and #623 already decided that residual notes
  after a fix round ship in the PR body. Offering it after a delta too would touch `rotate`,
  the auto-merge cycle count and the re-check head rules for little gain. Overturn if the
  owner wants polish after a fix round.
- Polish counts as a fix round (`fix_rounds`, the round cap, the auto-merge cycle budget in
  `merge.py:176-182`). Why: it is a builder round plus a delta, and one counter keeps I35
  true without a second budget. Consequence: an item that polished and then needs a PR fix
  round is not auto-merged (cycle budget 1); the owner merges it. Overturn by excluding
  polish transitions from that count.
- When several gates wrote notes, quality re-checks all of them, a security note included.
  This follows the issue's rule ("the reviewer who wrote the notes, or quality"). A
  trust-boundary security finding always blocks (charters `_common.md` rule 5), so it never
  reaches polish as a note.
- "A small budget" is a scope bound in the feedback, plus the build loop's existing
  iteration and stuck limits; no new numeric key.
- The round-one notes are now carried in `raise` (they were dropped). This is the shepherd
  `Review note:` path the delta tail already uses, so the PR body gains notes it should have
  had.
- Under `offer`, `dispatch next --all` lists the polish entry with its `command`, which the
  launch-set loop runs; the planner skips by running `skip-polish` first. The charter says
  when.
- Invariant id I58 is the id reserved for this item (I56 and I57 are held by other
  items).
