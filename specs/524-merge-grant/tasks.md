# Tasks: Merge grant

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Fixtures are neutral (`example/project`, `fixture-org/app`). Reuse
the `case`, `config_change` and `events` helpers of `tests/test_merge.py`, the `root`,
`answer`, `standing`, `strict` and `posture` helpers of `tests/test_grants.py`, and the
existing fixtures of `tests/test_plan.py`, `tests/test_pr_actions.py`,
`tests/test_pr_guards.py` and `tests/test_code_host.py`. No new fixture framework.

## Phase 1: squash is measured (FR-003)

- [X] T001 Test in `tests/test_code_host.py`: `protection` returns `squash: True` when the
  repository read has `allow_squash_merge: true` and no ruleset narrows it; `False` when
  `allow_squash_merge` is false; `False` when a ruleset `pull_request` rule has
  `allowed_merge_methods: ["merge"]`; a missing `allow_squash_merge` fails closed (exit 2).
  Update `tests/fixtures/code_host/recordings.json` with the repository read.
- [X] T002 Implement the `squash` field in `protection` in `adapters/code_host/github.py`.
- [X] T003 Test in `tests/test_merge.py`: with `squash: False` in the fake protection,
  `check` exits 1 naming the repository, the base and the host terminal; a non-boolean
  `squash` is exit 2 (damaged). Add `'squash': True` to every fake protection dict in
  `tests/test_merge.py`, `tests/test_merge_ports.py`, `tests/test_pr_guards.py` and any
  other fixture that `grep -rn merge_queue tests` finds, so existing tests stay green.
- [X] T004 Implement the squash validation and requirement in `check` in
  `cli/wuwei/merge.py`.

## Phase 2: merge is a grant action (FR-001, FR-005, FR-006)

- [X] T005 Test in `tests/test_grants.py`: `action('merge: example/project#7 at <sha>')` is
  `merge`; `action('merge_deploys')` and `action('environment branch merge')` stay `deploy`;
  `merge_tier` is `ask` under observe and guarded, `owner_only` under strict, and the
  configured value when `merge.default_tier` is set (both postures); a standing line with
  `action = "merge"` passes `config check`, and `active` ignores it under strict; `wuwei
  grants` lists it.
- [X] T006 Implement `ACTIONS['merge']`, the `action` line and `merge_tier` in
  `cli/wuwei/grants.py`; the `merge.default_tier` key and the standing action choice in
  `cli/wuwei/workspace.py`.

## Phase 3: the granted check (FR-002)

- [X] T007 Test in `tests/test_merge.py`: with `granted=True`, each auto-only refusal passes
  (parametrized: `auto = false`, a tripped breaker, the daily cap reached, quiet hours, item
  not in the approved plan, a risk flag, over the cycle budget, diff over
  `max_changed_lines`, a never-auto path, soak not passed) while `check` without `granted`
  still refuses each with its current reason; with `granted=True` each precondition still
  refuses (gate verdicts at an older sha naming `pre-PR gates not passed at current HEAD`, a
  red required check, a missing approval at head, changes requested, an unresolved thread,
  `merge_deploys = true`, an environment base, a draft PR).
- [X] T008 Implement `granted` in `check` (the skips and the granted refusal text) and in
  `item_evidence` in `cli/wuwei/merge.py`.

## Phase 4: execute under a grant or a card (FR-004, US1, US2, US3)

- [X] T009 Test in `tests/test_merge.py` (all with `auto = false`):
  - a today grant row on `repo:example/project`: `execute` exits 0, one host `merge` call
    with `SHA`, events in order `grant.used` (`action: merge`, `scope: today`,
    `target: repo:example/project`), `merge.intent`, `merge.auto`;
  - an `Allow once` row: merges and the row is `spent`; the next ready PR writes a card;
  - a planned row answered `today` on `pr:example/project#7`: merges; on
    `pr:example/project#8` it does not;
  - a standing line `repo:example/*` under guarded: merges with `scope: always`;
  - no grant under guarded and under observe: exit 1, one card file and one pending row
    `{action: merge, target: repo:example/project}`, reason ends with
    `bin/wuwei decision show D-1 --widget`, no host `merge` call; a second run writes no
    second card;
  - the card answered `keep`: exit 1 naming the kept card;
  - strict, no grant: exit 1, no card, reason contains `merge.default_tier = owner_only` and
    `gh pr merge https://github.com/example/project/pull/7 --squash --match-head-commit`
    with `SHA`; strict with a standing merge line: the same; strict with
    `merge.default_tier = "ask"`: a card without `Always allow`;
  - a today grant and a head that moved after the gates: exit 1, no host `merge`, no
    `grant.used`, no card, reason names the gates at the current head and contains
    `no grant lifts this; run bin/wuwei pr act example/project#7` and not
    `ask the owner`;
  - an auto-policy exit 2 (unreadable evidence) with a today grant: exit 2, no grant path;
  - `WUWEI_SEAT_ROLE=shepherd` with a today grant: still refused.
  Existing `execute` tests in `tests/test_merge.py` that assert an eligibility reason
  (for example `merge.auto is off`) now reach the grant path and get the card: point them at
  `check` for the eligibility reason, or assert the card.
- [X] T010 Implement `by_grant` and the one `execute` line in `cli/wuwei/merge.py`, and the
  `pr` keyword of `gate` in `cli/wuwei/grants.py`.
- [X] T011 Test (built as the existing `act` tests in `tests/test_shepherd.py`, which stub
  `merge.execute`; the grant itself is covered end to end by T009): an approved PR with a today grant and
  `auto = false`: `act` exits 0 and the day has `grant.used`; without a grant it exits 1 and
  prints `<ref>: ` followed by the card reason (no `owner merge decision required`).
- [X] T012 Implement the `act` print in `cli/wuwei/pr_actions.py`.

## Phase 5: planned merges (FR-007, US4)

- [X] T013 Test in `tests/test_plan.py`: move the two merge rows out of
  `test_owner_actions_beyond_grants_never_stop_the_gate` into a new test: a merge on
  `repo:fixture-org/app` and one on `pr:fixture-org/app#7` each write a planned card (the
  day's `decisions` directory exists, `plan gate` lists them), the `pr:` question names
  `fixture-org/app#7`, and `plan.md` has no `(owner step)` line for them; message and
  secret-set rows stay owner steps.
- [X] T014 Implement the `repo_name` slice in `plan()` in `cli/wuwei/grants.py` (merge
  reaches it through `ACTIONS`).

## Phase 6: the session redirect (FR-008, US5)

- [X] T015 Test in `tests/test_pr_guards.py`: `gh pr merge 7 -R example/project --squash`
  refused by the auto policy names `bin/wuwei merge 7` in its reason; exit 2 reasons are
  unchanged.
- [X] T016 Implement the `merge_check` reason in `cli/wuwei/guards/pr.py`.

## Phase 7: docs and charters (FR-009)

- [X] T017 Test in `tests/test_docs.py`: `docs/site/configuration.md` has a
  `merge.default_tier` row naming `ask`, `owner_only` and strict; the `grants.standing` row
  names `merge`; `docs/site/concepts.md` Grants names merge.
- [X] T018 Update `docs/site/configuration.md`, `docs/site/concepts.md`, design spec 4.6
  and 9.1 (dated #524 amendment), `charters/lead.md` and `agents/lead.md` (merge becomes a
  card the gate pre-approves), and the `grants` producer text in `cli/wuwei/state.py`.

## Phase 8: verify

- [X] T019 Run `tests/test_reasons.py` (the new reason strings keep the next-step shape),
  then the full suite (`python -m pytest -q`) in the background to a file; all pass.
  Check every written file for em-dashes and emojis.
