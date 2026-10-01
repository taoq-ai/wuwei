# Feature Specification: risk-tiered gates computed from the diff, with per-repository floors and escaped-defect measurement

**Feature Branch**: `280-tiered-gates`
**Created**: 2026-10-01
**Status**: Ready for implementation
**Input**: Issue #280, feat(gates). References: design spec 5.3 (tracks, flags, gate set),
4.6 (never-auto paths), 5.6 (outcome metrics), 9.1 (threat model and guard scope); the
whole-system review C3 (ceremony unmeasured); `cli/wuwei/dispatch.py`. Evidence: owner
question 2026-10-01 ("whether the gates are adaptive for the work item complexity"):
they are not.

## Root cause (read on main, fb3be19; reproduced read-only)

- **The gate set is a constant.** `cli/wuwei/dispatch.py:11` defines
  `ROLES = ('arch', 'quality', 'security')` and `next_step` uses it unconditionally in the
  initial round (`dispatch.py:85`, `roles = list(ROLES)`), in the fix phase
  (`dispatch.py:77-81`) and in the delta phase (`dispatch.py:88-91`). Neither the item's
  diff, its `flags`, its `track` nor any configuration is read. Reproduced with
  `tests/test_dispatch.py::test_gate_dispatch_and_live_builder_refusal` (passes on main):
  an item with no flags, no worktree and no diff gets `{'action': 'gates', 'roles':
  ['arch', 'quality', 'security'], 'seats': []}`.
- **Every consumer downstream repeats the constant.** The pre-PR guard requires all three
  recorded verdicts per item (`cli/wuwei/guards/pr.py:17` `GATES`, used at
  `pr.py:88-97` in `_recorded_gates`), and the merge policy reads a verdict file for each
  of the three (`cli/wuwei/merge.py:247-256`; a missing role becomes a fabricated
  `gate-<item>-<role>.md` path whose `read_bytes` fails). Lowering the set in dispatch
  alone would leave a LIGHT item unable to raise or merge.
- **A slot already exists.** Every item carries an empty `gates` dict
  (`cli/wuwei/state.py:45`, `ITEM_DEFAULTS`), reset when an item is imported into a new
  day (`cli/wuwei/plan.py:169`), and nothing writes or reads it. The diff reads the tier
  needs already exist in `brief.write` (`cli/wuwei/brief.py:193-201`: repository match,
  `merge_base` against `<brief.remote>/<default_branch>`, `diff_stat`), and the FULL-track
  path detector is `brief.full_path_patterns` (`brief.py:214-218`). The suffix glob match
  for never-auto paths is written inline twice (`merge.py:242-244`,
  `cli/wuwei/discovery.py:54-55`).
- **Escaped defects are measured per PR, not per gate set.** `metrics._escaped_defects`
  (`cli/wuwei/metrics.py:166`) has no notion of tier, so the ceremony cost the review
  called out (C3) cannot be weighed against defects.

## User Scenarios & Testing

### User Story 1 - A small, safe diff runs one gate (Priority: P1)

The owner has lowered a repository's floor to `light` after calibration. A docs-only item
with no lead flags reaches the gate, and `dispatch next` asks only for the quality gate;
the tier and why are recorded on the item and visible to the planner.

**Independent Test**: `python -m pytest -q tests/test_dispatch.py -k tier`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given a repository with `gates.floor = "light"` and an item with
   no flags, track SLICE, whose diff against its base is `docs/guide.md` (+3 -1), when
   `dispatch next` runs in phase `gate`, then it returns `{'action': 'gates', 'roles':
   ['quality'], 'seats': [], 'tier': <record>}` where the record is `tier: light`,
   `computed: light`, `roles: ['quality']` and one reason naming the measured size
   (`4 changed lines within light_max_lines 100`); the same record is stored at
   `items.<item>.gates` and one `gate.tiered` event carries it with the item id.
2. Given the same item, then a second `dispatch next` returns the same action, reads no
   diff again (the recorded tier is reused), and writes no second `gate.tiered` event.
3. Given the LIGHT item, when `dispatch receive <item> arch ...` runs, then it is refused
   (`gate role arch is not in the item gate set`); a quality PASS then yields
   `{'action': 'raise', 'notes': []}`; a quality FIX yields `{'action': 'fix', 'roles':
   ['quality'], ...}` and the delta asks for quality only.
4. Given the LIGHT item with a recorded quality PASS at HEAD, then the pre-PR guard
   (`gate_check` with the item) returns `(0, '')` without arch or security verdicts, and
   the merge policy's verdict evidence lists the quality verdict only.

### User Story 2 - Risky paths and flags cannot be tiered down (Priority: P1)

Whatever the floor, a diff that touches a trust surface, a never-auto path or a
FULL-track pattern, or an item the lead flagged, gets at least the three gates. A lead
cannot talk an item down.

**Independent Test**: `python -m pytest -q tests/test_dispatch.py -k tier`.

**Acceptance Scenarios**:

1. (Issue acceptance 2) Given `gates.floor = "light"` and the docs-only item whose diff
   also touches `cli/wuwei/guards/pr.py`, then the tier is `standard`, the roles are
   `['arch', 'quality', 'security']`, and a reason names the path and the rule
   (`cli/wuwei/guards/pr.py matches trust path guards/*`).
2. (Issue acceptance 3) Given a diff that changes `uv.lock`, then `security` is in the
   returned roles for every floor (`light`, `standard`, `full`) and for track FULL, and a
   reason names `uv.lock` and the never-auto pattern it matched.
3. Given a diff path matching a configured `brief.full_path_patterns` regex (the
   FULL-track criterion for interface and schema changes), then `arch` is in the roles
   and the reason names the pattern.
4. (Issue acceptance 4, first part) Given `gates.floor = "light"`, a LIGHT diff and the
   lead flag `trust_surface` (each of the three flags in turn), then the tier is
   `standard` and a reason names the flag; given the lead's candidate `tier: "full"`,
   then the tier is `full`.
5. (Issue acceptance 4, second part) Given a STANDARD diff (a trust path) and the lead's
   candidate `tier: "light"`, then the tier stays `standard`, the roles stay all three,
   and a reason records the refusal (`lead tier light refused: below standard`).
6. Given track FULL, then the tier is `full` and the roles are all three (FULL adds
   nothing new to the gate set).
7. Given a diff of more than `light_max_lines` changed lines, or a binary change whose
   size `diff_stat` reports as `None`, then the tier is at least `standard` and the reason
   names the size or the binary path.

### User Story 3 - An unmeasured diff never lowers the gates (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_dispatch.py -k tier`.

**Acceptance Scenarios**:

1. Given `gates.floor = "light"` and an item with no recorded worktree, or a vcs read
   that fails, or a worktree that matches no configured repository, then the tier is
   `standard` with the reason `diff unmeasured: <reason>`; `dispatch next` does not exit
   2 for this (the three-gate set is the fail-closed answer).
2. Given an item that already has an initial verdict but no recorded tier (an item in
   flight across the upgrade), then `dispatch next` records no tier, keeps all three
   roles, and its `gates` action has no `tier` field.
3. Given a malformed `items.<item>.gates.roles` (not a list, a role outside the three, or
   no `quality`), then dispatch, the pre-PR guard and the merge policy fail closed with
   `invalid recorded gate set` (exit 2 path in each).

### User Story 4 - The tier is visible where the work is read (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_signal_status.py tests/test_shepherd.py -k tier`.

**Acceptance Scenarios**:

1. Given an item with a recorded tier, when `status --json` runs, then its output has
   `gates: {<item>: <record>}` with tier, computed, reasons and roles.
2. Given an item with a recorded tier, when `pr raise` creates the PR, then the body sent
   to the code host ends with the line `Review tier: light (quality)` (or
   `Review tier: standard (arch, quality, security)`), and the outward lint runs on the
   body with that line included. An item without a recorded tier gets no line.

### User Story 5 - Escaped defects are counted per tier (Priority: P2)

The retro shows, per computed tier, how many merged items were later followed by a fix,
so the owner can lower the floor or move `light_max_lines` from evidence.

**Independent Test**: `python -m pytest -q tests/test_metrics.py -k tier`.

**Acceptance Scenarios**:

1. Given day states where item `A` merged with computed tier `light`, item `B` merged
   (computed `standard`) with a builder brief whose text references `A`, and item `C`
   merged with computed tier `standard` referenced by nothing, then
   `metrics.collect()['escaped_defects_per_tier'] == {'light': {'merged': 1, 'escaped': 1},
   'standard': {'merged': 2, 'escaped': 0}}`.
2. Given no merged item with a recorded tier, then the metric is `unmeasured`, never zero.
3. The retro's `## Metrics` block carries the metric (it already dumps `metrics.collect`).

### User Story 6 - The default keeps today's behaviour (Priority: P1)

**Acceptance Scenarios**:

1. (Issue acceptance 5) Given the default floor (`standard`), then every existing
   dispatch, verdict, pre-PR guard, merge and mutation test passes. The only edit to
   existing tests is the additive `tier` field in exact-equality expectations of a
   first initial-round `gates` action (`tests/test_dispatch.py` line 34 and lines
   613-614, `tests/test_e2e_day.py` lines 27 and 181). No expected role list, verdict, phase, exit
   code or existing event of an existing test changes.

### Edge Cases

- Empty diff (HEAD equals the merge base): measured, 0 lines; LIGHT if the floor allows.
- Renamed paths: `diff_stat` runs with `--no-renames`, so both sides appear as paths and
  both are matched.
- A path matched by several rules: one reason per (path, rule) pair, in the order trust
  path, never-auto path, FULL-track pattern.
- The PR body line carries no paths or reasons, so a repository whose paths contain words
  the outward lint refuses (for example `wuwei` in the WUWEI repository's own `cli/wuwei/`)
  can still raise.
- An imported item (carried to a new day) starts over at `planned` with `gates` reset
  (`plan.py:169`, unchanged), so its tier is recomputed at its next gate.

## Requirements

### Functional Requirements

- **FR-001**: Each `[[repos]]` entry gains a `gates` table: `floor` (`light`,
  `standard`, `full`; default `standard`), `light_max_lines` (integer >= 0, default 100)
  and `trust_paths` (glob list; defaults `guards/*`, `state.py`, `adapters/*`,
  `.claude-plugin/*`, `.github/*`, `ci/*`, `workflows/*`, `deploy/*`, `infra/*`).
  Invalid values fail config loading like every other schema key.
- **FR-002**: At the first `dispatch next` of an item in phase `gate` with no recorded
  tier and no initial verdict, the CLI computes the tier from the diff of the item's
  worktree HEAD against `merge_base(<brief.remote>/<default_branch>)`, through the vcs
  port and the existing repository match (`guards.commit_push.context`).
- **FR-003**: Computed tier: `full` for track FULL; at least `standard` for any lead flag,
  any changed path matching the repository's `gates.trust_paths` or
  `merge.never_auto_paths` (suffix glob, the same rule as the merge policy) or
  `brief.full_path_patterns` (regex, as in `brief.write`), any binary change, or more
  than `light_max_lines` changed lines; otherwise `light`. An unmeasured diff is
  `standard`.
- **FR-004**: Effective tier = the highest of computed, the repository floor, and the
  lead's optional candidate `tier`. A lead tier below the higher of computed and floor is
  refused: it has no effect and adds the reason `lead tier <x> refused: below <y>`. A
  floor above computed adds the reason `floor <floor>`.
- **FR-005**: Gate set: `light` is `['quality']`; `standard` and `full` are
  `['arch', 'quality', 'security']`.
- **FR-006**: The record `{'tier', 'computed', 'reasons', 'roles'}` is written once to
  `items.<item>.gates` by `wuwei dispatch next` (producer-only, refused to `state set`)
  with event `gate.tiered` (reserved to `wuwei dispatch next`, silent in attention), and
  returned as `tier` on the phase `gate` `gates` action whenever the item has a record.
- **FR-007**: One shared reader returns an item's gate set: the recorded roles, or all
  three when none is recorded; a malformed record raises. Dispatch (`next_step`,
  `receive`), the pre-PR guard (`_recorded_gates`) and the merge policy (`merge.check`
  verdict evidence) use it in place of the constant.
- **FR-008**: `dispatch receive` refuses a role outside the item's gate set.
- **FR-009**: The plan accepts an optional candidate `tier` (`light`, `standard`,
  `full`), validated at propose, copied onto the item at approve and at intraday add, and
  reserved to `wuwei plan approve`.
- **FR-010**: `status --json` includes `gates` (item id to record) for items with a
  record.
- **FR-011**: `pr raise` appends `Review tier: <tier> (<roles>)` to the body before the
  outward lint when the item has a record.
- **FR-012**: `metrics.collect` returns `escaped_defects_per_tier`: per computed tier, the
  merged items with a record and how many of them are referenced by a different merged
  item's builder brief; `unmeasured` without any such merged item.
- **FR-013**: No change to the verdict contract, the fix round, the delta, post-PR
  behaviour, the agent-surface scanner path, or the rule that a trust-boundary finding
  always blocks.
- **FR-014**: Docs: `docs/site/configuration.md` rows for the three `repos.gates.*` keys,
  `docs/site/reference.md` for the candidate `tier`, `charters/_common.md` rule 4 (gate
  set by tier) and `charters/lead.md` rule 5 (the optional `tier` raises, never lowers),
  with `agents/` regenerated.

### Key Entities

- **Tier record** (`items.<item>.gates`): `tier` (effective), `computed` (diff rules,
  flags and track only, before floor and lead), `reasons` (list of strings), `roles`
  (list, subset of the three in canonical order, always containing `quality`).
- **Repository gate settings** (`repos[].gates`): `floor`, `light_max_lines`,
  `trust_paths`.
- **Lead tier** (`items.<item>.tier`, optional): the lead's candidate `tier`.

## Success Criteria

- **SC-001**: With `floor = "light"`, a docs-only unflagged item needs one sentinel seat
  instead of three.
- **SC-002**: No configuration, lead input or read failure produces a LIGHT tier for a
  diff that touches a trust path, a never-auto path or a FULL-track pattern, or for a
  flagged item.
- **SC-003**: The full suite passes with the default floor, with only the additive `tier`
  field edited into existing exact-equality expectations.
- **SC-004**: The retro shows escaped defects per computed tier.

## Assumptions

- **Forcing rules raise to STANDARD as a whole.** The issue says lockfiles force the
  security gate and interface or schema changes force arch. Every such path is in
  `merge.never_auto_paths` or `brief.full_path_patterns`, and both force STANDARD here,
  which includes security and arch. A finer "LIGHT plus security" set is not built; it
  would be looser than this, never stricter. Add it when calibration shows STANDARD is too
  costly for dependency-only bumps.
- **The lead's lowering attempt is the optional candidate `tier`.** Flags are booleans
  that can only raise. "Refused" means the lower tier is ignored and the refusal is
  recorded as a reason; raising `Refused` (exit 1) would strand the item at the gate,
  since the lead's input is fixed at approve.
- **One size threshold** covers docs, tests and code alike (the issue lists the three
  under one threshold). Default 100 changed lines; the default floor `standard` keeps the
  value inert until the owner lowers the floor.
- **The tier is fixed at the initial gate.** A fix round that later adds a forcing path
  does not add gates (FR-013 forbids changing the fix round and delta); the merge
  policy's never-auto rule still keeps such a PR from auto-merging.
- **The diff is read even at the default floor**, so the computed tier (and the escaped
  defects per computed tier) accumulates calibration evidence before the owner lowers the
  floor. A read failure only costs a `diff unmeasured` reason.
- **Escaped defects come from builder briefs only.** The code host adapter's `pr` read
  does not return the PR body and raise does not store it, so "brief or PR body" is
  narrowed to the fix item's builder brief text (the `brief written` events with role
  `builder`). Counted per computed tier because the thresholds govern the computed tier;
  the effective tier stays visible in the record.
- **The PR body carries tier and gate set, not reasons.** Reasons contain repository
  paths that the outward lint may refuse.
- **Design spec 5.3 ("arch, quality and security in parallel on every code item") now
  holds only at the default floor.** The design spec is amended by its owner only; the
  conflict is raised here for the owner and not edited.
- `status --json` shows the full record; `status --line` is unchanged.
