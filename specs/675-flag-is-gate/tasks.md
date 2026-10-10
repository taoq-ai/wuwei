# Tasks: a trust_surface flag asks for the security gate, not the owner

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the existing fixtures in `tests/test_merge.py` (`case`, `granted_case`, `owner`,
`standing_merge`, `merged_calls`, `cards`, `events`, `config_change`, `evidence` from
`test_pr_guards`) and neutral names; no test reaches git or the network. A flagged item is
set with one state write on `items.item-7.flags.trust_surface` plus a `plan.approved` event
carrying the same flags (a small local helper in the test file). Run the touched test files,
then the full suite.

## Phase 1: trust_surface asks for the security gate (FR-001; US1)

- [X] T001 Tests in `tests/test_merge.py`: with `trust_surface` set and all gates PASS at the
  head, parametrized over `merge.default_tier` `today` and `ask`: `merge.check` exits 0 with
  `head == SHA`; `merge.execute` exits 0, merges `[(REF, SHA)]`, writes no card and records
  `merge.intent` and `merge.auto` with no `grant.used`. Same result when the security
  gate's initial record is FIX at an older head and its delta record is PASS at `SHA`
  (the `gate_verdicts` setup of `test_merge_uses_quality_delta_record`, with `security` in
  place of `quality`). Fails today with `item carries a risk flag`.
- [X] T002 Tests in `tests/test_merge.py`: a `trust_surface` item whose recorded gate set is
  `{'tier': 'light', 'roles': ['quality']}` is refused by `merge.check` with a reason naming
  `trust_surface needs the security gate`; the same when only the `plan.approved` event
  carries `trust_surface` and the item row says false. `agent_surface` and
  `boundary_relevant` still give `item carries a risk flag` (parametrized). In
  `test_policy_preconditions`, change the `forged-flags` case to forge `agent_surface`.
- [X] T003 Implement the `item_evidence` change in `cli/wuwei/merge.py` (plan, Design 2).
  T001 and T002 pass.

## Phase 2: a gate not passed at the head waits on the gate (FR-002; US2)

- [X] T004 Tests in `tests/test_merge.py`: with `trust_surface` set and the security gate file
  rewritten as `evidence(SHA, 'FIX')` plus a `blocks: yes` finding line: `merge.check` exits 1
  with a reason starting `merge: waits on the gate:`, containing `security`, and containing
  neither `the owner merges` nor `ask the owner`. `merge.execute` under
  `granted_case(case, tier=t)` for `t` in `ask`, `today` exits 1 with the same reason, no
  merge, `cards(root) == []`, no `grant.used` and one `merge.policy_blocked` event. The same
  wait reason when the security gate file is missing (no verdict yet).
- [X] T005 Implement `Routed`, the gate line and the `except Routed` branch in
  `cli/wuwei/merge.py` (plan, Design 1 and 4). T004 passes, and the existing
  `test_policy_preconditions[gate-security]`, `test_grant_never_lifts_a_precondition[gates]`
  and `test_moved_head_merges_under_no_grant` still pass unchanged.

## Phase 3: owner paths stay the owner's and the reason names the path (FR-003, FR-004; US3)

- [X] T006 Tests in `tests/test_merge.py`: `workspace.load_config` gives
  `merge.owner_paths == []` for the fixture. With `[merge]\nowner_paths = ["guards/*"]`
  appended to the fixture config and the changed file path `cli/wuwei/guards/example.py`:
  `merge.check` exits 1 with a reason containing `cli/wuwei/guards/example.py matches
  merge.owner_paths guards/*`, the module's `COMMAND` string and `in a host terminal`;
  `merge.execute` exits 1 with the same reason and no merge, no card, no `grant.used` under
  each of (parametrized): `default_tier = "today"` in the same `[merge]` table, a standing
  merge line (`standing_merge`), and a seeded grant row answered `today` for
  `repo:example/project` (the state write of `test_planned_pr_card_answered_today`). A rename
  whose `previous_path` matches and whose new path does not gives the same refusal naming the
  old path. With the owner path and the security gate file FIX, the reason is the gate wait,
  not the owner path. With `owner_paths` set and a non-matching path, the PR merges as before.
- [X] T007 Implement the `owner_paths` schema line in `cli/wuwei/workspace.py`, and in
  `cli/wuwei/merge.py` `owner_command`, its use in `by_grant`, the owner-path collection in the
  file loop and the `Routed` raise before the cleared return (plan, Design). T006 passes and
  `test_strict_without_grant_names_the_owner_command` still passes unchanged.

## Phase 4: the invariant (FR-005)

- [X] T008 Test in `tests/test_invariants.py`, beside `test_merge_only_at_the_gated_green_head`
  and reusing its imports from `test_merge` but starting from `case` (merge.auto on), not
  `granted_case`: parametrized over posture (`observe`, `guarded`,
  `strict`), tier (`ask`, `today`) and route (`security-pass`, `security-fix`, `owner-path`),
  a `trust_surface` item run through `merge.execute`: `security-pass` merges at `SHA` in every
  posture and tier (the auto policy clears it); `security-fix` and `owner-path` never merge,
  write no card and record no `grant.used`, and their reasons contain `waits on the gate` and
  `matches merge.owner_paths` respectively, never `the owner merges` for the wait. It runs
  green once T003, T005 and T007 are in; run it before T009 to confirm it passes on the code
  and fails with T003 reverted.
- [X] T009 Amend design 4.6 (the `Amended (owner, 2026-10-10, #675)` paragraph) and the 9.2 I3
  row (Checked by and Notes) in `docs/specs/2026-09-24-wuwei-design.md` (plan, Docs).
  `tests/test_invariants.py::test_table_matches_the_checks` still passes (no new row).

## Phase 5: docs and the full suite (FR-006)

- [X] T010 Add the `merge.owner_paths` row to `docs/site/configuration.md` after
  `merge.default_tier`, and the one sentence to the merge paragraph of `docs/site/concepts.md`
  (plan, Docs). Run `tests/test_docs.py`.
- [X] T011 Run the full suite with `python -m pytest -q`; check every file written for
  em-dashes, emojis and absolute local paths.
