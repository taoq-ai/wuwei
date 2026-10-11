# Implementation Plan: delete grants; the merge policy alone decides a merge

**Branch**: `b3-decision-framework` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at main ac5403f, the batch base. Batches 1 and 2 (#798 to #801, #808 to
#811) land first and the lead rebases. Make an edit marked "skip if already gone" only if
the code is still there.

This is part 11. It assumes parts 9 (#814) and 10 (#815) are done on this branch, so this
part no longer touches:

- `cruise.py`, its call of `grants._record` and its gate widgets (part 9);
- `novelty.py` and its import of `grants.REPO` (part 10);
- the novelty branch in `grants.gate` and `active` (part 10);
- the novelty condition at `commands/decision.py:254` (part 10);
- `tests/test_novelty.py` (deleted in part 10);
- the design spec Novelty paragraph (part 10).

Line numbers in `commands/decision.py`, `grants.py` and `plan.py` shift after parts 9 and
10. Locate by function name.

## Summary

Delete grants. The merge policy alone decides a merge. Deploy, release and publish refuse
from the session, and the owner runs them in a host terminal. An evidence miss is a seat
step, with no card. The process control kept, and where:

| Rule | Where | How |
| --- | --- | --- |
| A merge happens only when the policy clears it | `merge.check` (no `granted`), `merge.execute` (no `by_grant`) | one decision function, unchanged preconditions |
| A refusal a grant used to lift reaches the owner | `merge.Owner(Refused)`, `merge.policy_blocked.owner`, `commands/next.py::step` | `next` returns one park row for that PR |
| A wait the policy clears later stays a wait | quiet hours, daily cap, soak, gates, reviews, checks | the `pr` row as today |
| Deploy, release, publish | `guards/deploy.py` | refuse in every posture, naming the host-terminal step |
| Evidence before push or PR raise | `guards/commit_push.py`, `guards/pr.py`, `shepherd.raise_pr` | posture publish level: off passes, warn warns, block refuses with the seat's step |

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. One new exception class (`merge.Owner`) and one
event field (`owner`). The rest is net deletion. Run only the touched test files. CI runs
the suite.

## Constitution Check

- I: nothing added.
- II: every guard keeps exit 1 for a refusal. The deploy guard's exit-0-after-grant path
  goes, so no grant lets a call through. `merge.execute` exits 1 or 2 as today.
- III: the merge decision stays in `merge.check`. The owner row is in `next.step`, the one
  place that names next actions.
- IV: tasks.md writes red tests first for the owner block, the `next` row, the deploy
  refusal, the evidence refusals, the plan lines and the CLI.
- V: `by_grant`, the grant gate, standing lines and the default tier go.
- VII (amended): under observe and guarded, owner-only publishing is now a floor next to
  records. Edit `.specify/memory/constitution.md` VII: "with two floors: records are written
  by the workflow and answered by the owner, and owner-only publishing (deploy, release,
  publish) runs only from the owner's host terminal (#816)". Its last sentence becomes "A
  merge happens only through the merge policy; a merge the policy does not clear is the
  owner's decision (design 4.6, 9.2)". Bump the version (minor, after #798's) with a dated
  amendment line.
- Workflow invariant rule: the guard change edits the 9.2 table where grants appear. Skip if
  #798 replaced it; then edit only grant wording in the edge table.
- Design spec ownership: part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Grant cards for deploy, release, publish (`grants.gate`, `ask`, `active`, `_record` use) | (a) the model and owner reason about grant scope and reruns | the deploy guard refuses; the owner runs it in a host terminal |
| `[grants] standing`, `wuwei grants`, `grants revoke`, `grants.standing`, the doctor row | (a) | nowhere |
| `merge.default_tier` (`ask`, `owner_only`, `today`), `merge_tier`, `DEFAULT` | (a) a second, day-scoped merge policy | `repos.<n>.merge` (auto, caps, paths) alone |
| `merge.by_grant`, `check(granted=True)` | (a) a second merge path that skipped eligibility and pacing | `merge.check` only; what it skipped becomes `Owner` (one owner decision) or a wait |
| Evidence cards (`grants.evidence` card branch) | (a) | the evidence reason under the posture publish level (b, kept) |
| `grants.evidence` posture levels | (b) push and PR raise only after evidence at head | `commit_push.check`, `pr.create_check` (hook levels them), `shepherd.raise_pr` (inline) |
| Planned grant cards (`grants.plan`, `gate_widgets`) | (a) | `plan.owner_steps` lines |
| `grants.understood`, `OWNER_ACTIONS` | (b) the lead's JSON stays validated | moved into `plan.py` |
| `grants._record` | shared builder | moved into `calibrate.py` (its only caller) |
| Report `## Grants`, `grant.*` events, state `grants` | (a) | nowhere |
| `GUARD_CODE` `'grants*'` | names this module | dropped; AUTH `'grants*'` stays (generic) |

No (b) check is lost.

## Files to delete (3)

- `cli/wuwei/grants.py`
- `cli/wuwei/commands/grants.py`
- `tests/test_grants.py`. Its evidence-under-observe and evidence-under-strict cases are
  covered by `tests/test_commit_push.py:921` and `tests/test_shepherd.py:985,1011`, so
  nothing moves.

## Files to edit, code (24)

### `cli/wuwei/merge.py`

- 22-24: the `Routed` docstring becomes "a refusal the owner cannot lift either (a gate to
  wait on, an owner path)".
- New, after `Routed`: `class Owner(Refused): """#816: a refusal a grant lifted before: the owner decides through wuwei next."""`
  and `def owner(condition, reason)`, which raises `Owner(reason)` when the condition is
  false.
- `item_evidence` (175-203): drop `granted` and 180-181. The requires at 182, 192, 195
  and 203 become `owner(...)`. 178 (`PR needs one linked item`) stays `require`.
- `check` (287-289): drop `granted` and the docstring clause.
  - Becomes `owner(...)`: 303 (`merge.auto`), 307 (breaker), 359 (never-auto path), 367
    (size).
  - Stay plain `require(...)`: 311-313 (daily cap), 314 (quiet hours).
  - 315: `item_evidence(root, ref, data)`.
  - 411: `if workspace.now() < end:`.
  - 374: drop "no grant lifts this; ".
  - 423: the comment drops "no grant, standing line or default_tier".
- 432-440, the except branches, in this order:
  - `except Routed`: unchanged.
  - `except Owner as exc:` returns `Result(1, {'owner': True}, f'merge policy: owner decides: {exc}; wuwei next names it for the owner')`.
  - `except Refused as exc:` returns `Result(1, None, f'merge policy: waits: {exc}; run bin/wuwei pr act {ref} once it holds')`.
- 476-499: delete `by_grant`. Keep `owner_command` (471-473).
- 511-512: delete the `by_grant` fallback.
- 514-515: the payload gains `'owner': bool(result.data and result.data.get('owner'))`.

### `cli/wuwei/commands/next.py`

- `_seen` (107-137):
  - prefilter adds `or '"merge.' in text`;
  - for `merge.policy_blocked` and `merge.intent`, keep the latest payload per `payload['pr']`
    in a dict `merges` (intent stored as `{'owner': False}`);
  - return it as a sixth value and update the docstring;
  - 180 unpacks it.
- `step`, `phase == 'raised'` (264-267): when `merges.get(pr, {}).get('owner')`, append to
  `found` the row `_row('merge', f'{label}: the merge policy does not clear PR {pr}: {merges[pr]["reason"]} Park it for the owner, who merges it in a host terminal or leaves it.', f'wuwei plan park {name} --reason "the merge policy does not clear {pr}"', item=name)`.
  Otherwise append the `pr` row as today. No shlex: the reason is fixed text, and a PR ref
  has no double quote.
- POSTURES (13-20):
  - observe: "deploys, releases and approve-tier messages ask on a card" becomes "deploys
    and releases refuse (the owner runs them in a host terminal); approve-tier messages ask
    on a card";
  - guarded: the same change.

### `cli/wuwei/guards/deploy.py`

- 44: the `deny` docstring becomes "An owner-only rule and the repository the command names;
  check refuses it."
- 137: delete the #478 comment.
- 344 and 352-366: replace the grants block with
  `result = (1, f'publish: {" ".join(hook.redacted_target(payload, root).split())} ({result[1][0]}) is owner-only: ask the owner to run it in a host terminal')`.
  Import `hook` locally, as grants did.
- Delete `moved`, `used` and the `for use in used` loop.
- 369: the reason ends "...; write it as plain literal commands".

### `cli/wuwei/guards/commit_push.py`

- 147-150: the comment says "the deploy guard's tag push rule refuses it from the session;
  the native hook lets the owner's push through below strict".
- 496-499: delete the grants call. `fast_evidence`'s `(1, reason)` stands.
- 502-505: delete `used` and the loop.

### `cli/wuwei/guards/pr.py`

- 32-33: `return 1, result.reason`.
- 214: import only `merge`.
- 263: `return code, reason`.
- 455 and 471-474: delete `used` and the loop.

### `cli/wuwei/shepherd.py`

- 309-317: replace the grants call with the inline posture rule:
  - `name, levels = workspace.posture(config)`;
  - when `levels['publish'] == 'off'`, pass;
  - when it is `warn`, append `guard.would_refuse` (the payload of `grants.py:238-241` with
    `target` = the joined argv) and print `warning: <reason>` to stderr, then proceed;
  - otherwise print the reason and return 1.
- 363-364: delete `use`.
- 592-596: the comment drops "#524 (merge grants)".

### `cli/wuwei/plan.py`

- New near `owner_steps`: `REPO`, `OWNER_ACTIONS` and `understood`, moved verbatim from
  `grants.py:13,17-33`.
- `owner_steps` (117-129): every understood entry becomes an `(owner step)` line. The
  docstring drops "not grant cards".
- 274-275: delete `grants.plan`.
- 301: delete the planned `Owner-only:` line.

### `cli/wuwei/commands/plan.py`

- 75-79: delete `grants.gate_widgets`. Part 9 already removed cruise.

### `cli/wuwei/commands/decision.py` (`owner_outcome`)

- Delete the `grant` lookup and the standing write (base 221-225).
- The answered-row loop (base 230-232) keeps only `outbound_learn`.

### `cli/wuwei/calibrate.py`

- 739-740: move `_record` here from `grants.py:58-87` and drop the `revisit` default (the
  9th positional, always passed). Call `_record(...)`.

### Small reference removals

- `cli/wuwei/report.py:242-247`: delete `## Grants`.
- `cli/wuwei/state.py:277`: delete `grants`.
- `cli/wuwei/signal.py:30`: drop the three `grant.*` kinds.
- `cli/wuwei/commands/event.py:99-100`: drop the three producers.
- `cli/wuwei/commands/doctor.py:500-504`: delete the standing-grant row.
- `cli/wuwei/workspace.py`:
  - 87-90: delete `default_tier` and its two comments; the `owner_paths` comment drops
    "whatever the grant";
  - 91-94: delete `grants`;
  - 770-776: delete the standing check.
- `cli/wuwei/interview.py:116-129`: the autonomy answer drops `merge.default_tier`. The
  Autonomous text says "merges run where repos.<n>.merge.auto is on"; the Supervised text
  drops "merges".
- `cli/wuwei/dispatch.py:218`: `GUARD_CODE = ('guards/*', 'outward*', 'hooks/*')`. 206 stays.
- `cli/wuwei/pr_actions.py:561`: the comment becomes "#816: the owner block, the wait or the
  owner's command". 106-107: the fallback `merge_decision` becomes `owner_decision`.
- `cli/wuwei/commands/hook.py:291-298`: comments name the host-terminal reason, not a card.
- `cli/wuwei/decision.py:24`: the comment becomes "Keep is the status quo".

### Skip if already gone (batches 1 and 2)

- `cli/wuwei/guards/protect_state.py:57-58` (`('grants', 'revoke')`) and 119-120
  (`GUARD_KEYS`, `GUARD_CONFIG` text) (#800).
- `cli/wuwei/commands/__init__.py:5,17` and `cli/wuwei/__main__.py:31` (#800).
- `cli/wuwei/guide.py:81-84,101-102` (#800).
- `cli/wuwei/pace.py:169,182` (#811).

## Files to edit, governance, charters and agents (3 plus generated)

- `.specify/memory/constitution.md` VII: see Constitution Check.
- `charters/_common.md:11`: "Never deploy, release or promote to an environment; on a
  `publish:` refusal stop and hand back the command: the owner runs it in a host terminal."
- `charters/lead.md:13`: `owner_actions` "are plan lines the owner runs; the gate does not
  pre-approve them".
- `agents/*.md`: `bin/wuwei agents build`.

## Files to edit, docs (6)

### `docs/specs/2026-09-24-wuwei-design.md`

- 4.6: replace the #524 amendment (345-356) with "Amended (owner, 2026-10-11, #816): grants
  are gone. The merge policy alone decides a merge. A merge it does not clear for an
  eligibility or pacing reason is one owner decision from `wuwei next` (the item is parked
  for the owner); a precondition names its condition."
- 366-369 (#675): drop "no grant changes that" and "whatever the grant, standing line or
  `merge.default_tier`".
- 4.7 (390-395): "Amended (#816): owner-only actions refuse from the session; the owner runs
  them in a host terminal; no card or grant."
- 540 and 913: drop "publish grants".
- 577: drop `grants` from the mutation step.
- 9.1:
  - 1997: drop the card list;
  - 2003: the owner-only bullet is "refuse from the session in every posture; the owner runs
    them in a host terminal; a merge the policy does not clear is an owner decision from
    `next`; missing evidence is the seat's check under the publish level".
- 9.2: grant wording in I1, I3, I5, I9, I18 and I37 (2012-2053). Skip if #798 replaced the
  table; then edit any grant word in the edge table.

### `docs/site/concepts.md`

- 184-195: replace `## Grants` with `## Owner-only actions` (two sentences: refuse in
  session, host terminal; the merge policy and the owner block).
- 212: drop `wuwei grants revoke`.
- 404: drop "grants".

### `docs/site/configuration.md`

- 15: drop `[grants]`.
- 335 and 336: delete the rows.
- 337: drop the grant clause.
- 339: becomes "a deploy never runs from a session" and links `concepts.md#owner-only-actions`.
- 379: drop `merge.default_tier`.

### `docs/site/security.md`

- 55 and 61: owner-only actions refuse with a host-terminal step, with no cards.

### `docs/site/daily.md`

- 225-232: planned owner actions are plan lines.
- 366: drop "under any grant".

### `docs/site/reference.md`

- 31 and 449: delete the `grants` rows.
- 114: drop the grant clause, if part 10 left one.

### `docs/site/agent.md`

- Regenerate if `guide.py` exists; after #800, edit lines 56, 59, 71 and 84 by hand.

## Files to edit, tests (22)

### New red tests

- `tests/test_merge.py`:
  - `test_an_eligibility_refusal_is_an_owner_block` (auto off: exit 1, no merge call, no
    `decisions/`, no `grant.*`, `merge.policy_blocked.owner is True`, reason starts
    `merge policy: owner decides:`);
  - `test_quiet_hours_are_a_wait` (`owner is False`, reason `merge policy: waits:`).
- `tests/test_next.py`: `test_an_owner_merge_block_is_one_park_row`, plus an `owner: false`
  case and a later `merge.intent` case that keep the `pr` row.
- `tests/test_deploy.py`: `test_owner_only_refuses_in_every_posture` (observe, guarded and
  strict refuse with the host-terminal reason; no state or decision written).
- `tests/test_commit_push.py:931-947`: becomes `test_missing_evidence_refuses_under_guarded`
  (`(1, MISSING)`, no card).
- `tests/test_shepherd.py:995-1008`: becomes "refused, exit 1, no card". 1015: drop the card
  line.
- `tests/test_plan.py`: `test_propose_writes_one_planned_card` (811-829) and
  `test_planned_merges_are_gate_cards` (872-889) become `test_owner_actions_are_plan_lines`.
- `tests/test_cli.py`: `main(['grants'])` raises `SystemExit` 2.

### Edits following the deletions

- `tests/test_merge.py`:
  - delete `auto_only`, `test_grant_lifts_only_auto_eligibility_and_pacing`,
    `test_grant_never_lifts_a_precondition` and the `owner` fixture (1008-1080);
  - delete 1101-1165, 1195-1207 and 1240-1265 (card, once, planned, standing, kept, strict
    and default-today cases);
  - convert 1172-1180 to "an owner path names the owner command in every posture";
  - edit 173 (`GRANT`), 242-249 (no `granted`), 252-256, 259-273, 1183-1192, 1210-1237,
    1427-1530 (drop `tier`, `standing` and grant filters).
- `tests/test_invariants.py` (kept lint part):
  - delete the `grants.py` row from `CALLED` (40) and its three `EXEMPT` rows (54-56);
  - add `('guards/deploy.py', 'is owner-only: ask the owner to run it in a host terminal', 'owner-only publishing floor (#816)')`.
  - Skip if already gone (#798): the import at 22 and everything in the walk.
- `tests/test_pr_guards.py:238-243`: the reason is `merge.check`'s, with no grant tail.
- `tests/test_posture.py:363-368`: the orientation says deploys refuse.
- `tests/test_interview.py`: 158 and 163-174 (four keys), 676, 927-928.
- `tests/test_card_confirms.py:202-216`: four keys.
- `tests/test_path_day.py:197-305`: enable `repos.merge.auto` with soak 0 for the merges.
  The deploy step expects the host-terminal refusal. Delete the grant and `## Grants`
  asserts (272-295).
- `tests/test_doctor.py`: delete `test_standing_grant_ignored_under_strict` (505-515).
- `tests/test_report_retro.py`: delete `test_report_counts_grant_uses` (432-447).
- `tests/test_state_allowlist.py`: delete 61 and 139-141.
- `tests/test_signal_status.py:386`: drop the three kinds.
- `tests/test_git_hook.py:89-104`: drop `granted` and the `[grants]` write.
- `tests/test_calibrate.py:1305-1312`: import `_record` from `calibrate`.
- `tests/test_workspace.py:225`: drop `default_tier` and `grants`. Add
  `test_grant_keys_only_warn`.
- `tests/test_docs.py`: delete `test_grants_are_documented` (1463-1475) and
  `test_merge_grant_documented` (1569-1580); edit 1550 if the skill phrases change.
- `tests/test_hooks.py:280`: drop `wuwei.grants`.
- `tests/test_protect_state.py:1055`: drop `grants.x` (skip if #800 removed the guard keys).

## RETIRED at rebase

The base has no `workspace.RETIRED`. After #799, the lead adds:

- `grants` (the table, with `grants.standing`)
- `merge.default_tier`

## Risks for the builder

- Behaviour change: workspaces that merged through `merge.default_tier = "today"` now need
  `repos.<n>.merge.auto = true`. Otherwise each merge becomes an owner block and a park row.
  Say so in the PR body.
- The wall lint: the deploy reason contains "host terminal" and "ask the owner to". Without
  the EXEMPT row, `test_reason_corpus_has_no_wall` fails. The constitution VII amendment is
  the reason it is not loosening.
- `next._seen` reads more lines (`"merge.` events). Keep the substring prefilter, and only
  `json.loads` matching lines.
- `merge.check` already raised `Refused` from `item_evidence` before the head was read. The
  `Owner` subclass must keep `Routed` handled first, and `Owner` before `Refused`.
- `tests/test_path_day.py` is the largest edit. Run it alone first.
- Shared files with parts 9 and 10: `commands/decision.py`, `plan.py`, `commands/plan.py`,
  `report.py`, `doctor.py`, `state.py`, `signal.py`, `event.py`, `workspace.py`.
