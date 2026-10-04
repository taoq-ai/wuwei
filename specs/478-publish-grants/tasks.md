# Tasks: an owner-only action asks the owner instead of blocking, the answer is a decision and a grant, the gate pre-approves planned deploys, and the reason names the action and the target

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures, reasons and record texts are in plan.md;
the row and the config line in data-model.md. Fixtures: `workspace` and `check()`
(`tests/test_deploy.py`), `hook_call`, `fixed`, `events` (`tests/test_posture.py`),
`proposal()`, `lead()`, `root` (`tests/test_plan.py`). The owner's confirmation: monkeypatch
`wuwei.integrity._host_confirm` to return True. Neutral names (`fixture-org/app`, `acme/app`,
`Deploy Production`); no absolute local path, no em-dash and no emoji in any file.

## The reason names the action and the target (FR-002, FR-003, US4)

- [X] T001 In `tests/test_deploy.py`, add a failing test: with `deploy.workflows =
  ["deploy-production.yml"]` and a `[[repos]]` entry `fixture-org/app` at `.`,
  `check(workspace, 'gh workflow run "Deploy Production" -R fixture-org/app --ref main')`
  returns exit 1 with a reason starting `publish: `, containing `fixture-org/app` and `is a
  deploy (deploy.workflows)`, and not containing `resolution`. Fails today: exit 2, "requires
  unavailable workflow resolution".
- [X] T002 In `tests/test_deploy.py`, update the table rows `gh workflow run test.yml`, `gh run
  rerun 123`, `gh workflow run 123` and `gh api repos/acme/app/actions/runs/123/rerun -X POST`
  to exit 1 with `workflow`, and `test_workflow_aliases_fail_closed` to exit 1 with `deploy` in
  the reason and `resolution` not in it. Fails today: exit 2.
- [X] T003 In `tests/test_grants.py` (new), add a failing table test for `grants.action(rule)`
  (`release create`, `tag push`, `release API`, `tag or branch ref API` give `release`;
  `deploy.deny: make publish*` gives `publish`; `deploy.workflows`, `environment branch push`,
  `tofu apply` give `deploy`) and for `grants.target(root, config, cwd, repo)`: an explicit
  `fixture-org/app` wins; `None` with a cwd inside the configured repository gives
  `repo:fixture-org/app`; a cwd outside every repository, or a repo value with a space or `$`,
  gives `None`. Fails today: no module `wuwei.grants`.
- [X] T004 In `cli/wuwei/merge.py`, extract `configured(root, config, cwd)` from `reference`
  (lines 49-56, unchanged behaviour). In `tests/test_deploy.py`, existing merge tests stay green.
- [X] T005 Create `cli/wuwei/grants.py` with `ACTIONS`, `REPO`, `action` and `target`.
- [X] T006 (SC-003) In `tests/test_hooks.py`, add a regression test: a `wuwei hook PreToolUse` run of `git status`
  in a workspace leaves `wuwei.grants` and `wuwei.merge` out of `sys.modules` (follow
  `test_hook_imports_no_unused_stdlib`). It passes today (no such module) and must stay green
  after T007: import `wuwei.grants` only on a refusal.
- [X] T007 In `cli/wuwei/guards/deploy.py`, make `deny(rule, repo=None)` return `(1, (rule,
  repo))`, pass the known repository at the gh, api and merge sites, turn the three workflow
  resolution `unknown` calls into `deny('deploy.workflows', repo)`, move the loop body into
  `command_result`, and route every exit-1 result to `grants.gate` (lazy import). Write
  `grants.gate` with only the target-`None` and heartbeat branches and a temporary card-less
  reason so T001 and T002 pass; T010 completes it. Every other `tests/test_deploy.py` row stays
  green.

## The card (FR-001, FR-004, FR-005, US1 scenarios 1, 5, 6)

- [X] T008 In `tests/test_grants.py`, add failing tests on the `tests/test_deploy.py` style
  workspace with `fixture-org/app` at `.`: (a) `deploy.check` on `gh workflow run
  deploy-production.yml -R fixture-org/app` returns exit 1 with exactly the card reason of the
  plan naming `D-1` and `guarded`; `days/<date>/decisions/D-1.md` passes `decision.lint`; the
  `grants` row matches data-model.md (`answered` null, `planned` false, `seat` from
  `agent_type`); `decision_routes` holds `D-1`; a `grant.asked` event exists. (b) The same call
  again names `D-1` and no `D-2.md` exists. (c) `decision show D-1 --widget` labels are `Keep
  owner-only (Recommended)`, `Allow once`, `Allow today`, `Always allow`; under `[security]
  posture = "strict"` a new workspace's card has the first three only. (d) A payload with
  `session_id = "wuwei-heartbeat"` writes no record. (e) `terraform apply -auto-approve`
  (a `PERMISSIONS_DENY` pattern) returns exit 1 with `the workspace permissions deny it` and
  writes no record. Fails today: no card is written.
- [X] T009 In `tests/test_decision.py`, add a failing row: a record whose status-quo title is
  `Keep owner-only` lints clean, and `Another fix` still fails with `Do nothing, Defer or Keep`
  (update the existing `test_lint_findings` substring). In `tests/test_control_plane.py`, `drop
  it` on a one-decision queue whose status quo is `Keep owner-only` picks it. Fails today: the
  rule accepts only Do nothing and Defer.
- [X] T010 In `cli/wuwei/decision.py` add `STATUS_QUO` (with `Keep`) and use it in `_scored`;
  in `cli/wuwei/control_plane.py` use it for `drop it`. In `cli/wuwei/grants.py`, write
  `_record`, `ask` and the rest of `gate` (host rule, keep, reuse, ask) per the plan; T008
  passes.

## The answer and the grant (FR-006, FR-007, US1 scenarios 2 to 4)

- [X] T011 In `tests/test_grants.py`, add failing tests, each starting from the T008 card:
  (a) `owner_outcome(SimpleNamespace(id='D-1', option='Allow today'))` with the host
  confirmation faked; the row's `answered` is `today`; `deploy.check` on the same command
  returns `(0, '')` twice and two `grant.used` events carry `decision D-1`, `scope today`;
  `wuwei close` (`commands.close.run`, or `state._write_state` setting `close_requested`) then
  makes the call return exit 1 naming `D-2`. (b) `Allow once`: one `(0, '')`, `spent` true, a
  `grant.used` with `scope once`, and the next call names `D-2`. (c) `Keep owner-only`: the next
  call returns the keep reason naming `D-1` and no `D-2.md` exists. Fails today: the answer is
  not stored on the row and the guard reads no grant.
- [X] T012 In `cli/wuwei/commands/decision.py`, store `answered` on the `grants` row in
  `owner_outcome`'s update; in `cli/wuwei/grants.py` write `active` and the `grant.used` branch
  of `gate` (the `once` spend under the lock with the RACE check).
- [X] T013 In `tests/test_hooks.py` (or `tests/test_posture.py` with the real deploy guard), add
  a failing test: `wuwei hook PreToolUse` on the T008 payload exits 2, prints the `publish:`
  reason as the only stderr line (no `posture:` line), and `permissionDecisionReason` equals it;
  a fake deploy refusal `deploy generic` still gets the posture line. Fails today: the posture
  line is appended.
- [X] T014 In `cli/wuwei/commands/hook.py` `posture()`, drop the line for a deploy reason that
  starts with `publish: `.

## Standing grants (FR-008, FR-009, FR-010, US2)

- [X] T015 In `tests/test_grants.py`, add failing tests for the config line: `load_config`
  accepts the data-model example and `repo:fixture-org/*`; it raises `ConfigError` naming
  `grants.standing.0` for target `fixture-org/app`, decision `X-1`, date `today` and action
  `merge`; the default is `[]`. Fails today: `grants` is an unknown key.
- [X] T016 In `cli/wuwei/workspace.py`, add `SCHEMA['grants']`, the `load_config` checks and
  `CONFIG_CACHE_VERSION = 8`.
- [X] T017 In `tests/test_grants.py`, add a failing test under guarded: answer the T008 card
  `Always allow`; `config.toml` holds one `standing` line with `decision = "D-1"` and today's
  date; with `workspace.now` moved to the next day the call returns `(0, '')` with a
  `grant.used` `scope always`; under strict (posture switched after the answer) the call writes a
  new card instead. Also: answering `Always allow` on a four-option card after switching to
  strict returns exit 1 and writes no line. Fails today: nothing is written to config.
- [X] T018 In `cli/wuwei/grants.py`, write `standing`; call it from `owner_outcome` for
  `always` before the state update (`cli/wuwei/commands/decision.py`).
- [X] T019 In `tests/test_grants.py`, add failing tests for the command: `wuwei grants` prints
  the plan's listing (standing numbered, `today:` rows, ` (ignored under strict)` under strict,
  `No grants.` when empty); `wuwei grants revoke 1` with the digest confirmation faked removes
  the line and appends `grant.revoked`, and the next deploy call writes a new card; `revoke 2`
  with one line is exit 1. In `tests/test_cli_known_command.py`, `grants` is read-only and
  `grants revoke` writes. Fails today: no `grants` command.
- [X] T020 Create `cli/wuwei/commands/grants.py`; add the paths to `cli/wuwei/commands/__init__.py`.
- [X] T021 In `tests/test_owner_edits.py`, add a failing test: a seat payload running
  `bin/wuwei grants revoke 1` is refused by `protect_state` with the revoke reason, and `bin/wuwei
  config set grants.standing '[]'` gets the `GUARD_CONFIG` reason; the planner session that
  asked `D-1` may run `bin/wuwei decide D-1 "Allow today"` outside strict. Fails today: revoke is
  not an owner action.
- [X] T022 In `cli/wuwei/guards/protect_state.py`, add `('grants', 'revoke')` to `_OWNER_ACTIONS`.
- [X] T023 In `tests/test_doctor.py`, add a failing test: under strict with one standing line,
  `doctor` has a `workspace` row `grant 1` with status `warn` naming the action, target and
  decision and the fix `bin/wuwei grants revoke 1`; under guarded there is no such row. Fails
  today: no row.
- [X] T024 In `cli/wuwei/commands/doctor.py` `_workspace`, add the rows.

## Records (FR-013, FR-014)

- [X] T025 In `tests/test_grants.py`, add a failing test: `wuwei event grant.used {}` exits 1
  naming its producer; `state set grants ...` is refused as producer-owned; `signal.classify`
  of the three kinds is silent. In `tests/test_report_retro.py`, a day with three `grant.used`
  events for `D-3` (action deploy) has `## Grants` with `- deploys run under grant D-3: 3`.
  Fails today: the kinds are free and the report has no section.
- [X] T026 Add `grants` to `cli/wuwei/state.py` `STATE_PRODUCERS`, the three kinds to
  `cli/wuwei/commands/event.py` and `cli/wuwei/signal.py`, and the section to
  `cli/wuwei/report.py`.

## The gate pre-approves planned actions (FR-011, US3)

- [X] T027 In `tests/test_plan.py`, add failing tests: `plan.propose` with candidate `A`
  carrying `owner_actions: [{"action": "deploy", "target": "repo:fixture-org/app"}]` writes
  `D-1` (planned row, item `A`), `plan.md` has `Owner-only: deploy repo:fixture-org/app (D-1)`
  under `A`; a second `propose` writes no `D-2.md`; an `owner_actions` entry with action `merge`
  or target `fixture-org/app` raises the `PLAN_JSON` error. The `plan gate` CLI prints a JSON
  list: the unchanged gate widget first, then the `D-1` card with labels `Allow today
  (Recommended)`, `Ask when it happens`, `Keep owner-only`; with no owner actions the list has
  only the gate widget. Fails today: `owner_actions` is ignored and `plan gate` prints an object.
- [X] T028 In `cli/wuwei/grants.py`, write `plan` and `gate_widgets`; in `cli/wuwei/plan.py`
  validate `owner_actions` and call `grants.plan` in `propose`; in `cli/wuwei/commands/plan.py`
  print the list.
- [X] T029 In `tests/test_grants.py`, add a failing end-to-end test: after T027's propose,
  `owner_outcome` `D-1` `Allow today`, then `deploy.check` on a deploy to `fixture-org/app`
  returns `(0, '')` with `grant.used` naming `D-1`; with `Ask when it happens` instead, the call
  writes a refusal card `D-2`. Fails before T028.

## Docs, skill, charters, design (FR-015, US5)

- [X] T030 In `tests/test_docs.py`, add a failing test: `docs/site/configuration.md` names
  `grants.standing`; `concepts.md` names `Allow once`, `Allow today`, `Always allow` and
  `bin/wuwei grants revoke`; `security.md` no longer says owner-only actions "always block"
  without the grant; `daily.md` names `Ask when it happens`; `skills/wuwei-plan/SKILL.md` says
  `plan gate` prints a list and names `decision show D-n --widget` for owner-only refusals.
  Fails today: none of it is there.
- [X] T031 Edit `docs/site/concepts.md`, `configuration.md`, `security.md`, `daily.md`,
  `reference.md` (`grants revoke` under Host terminal actions) and
  `skills/wuwei-plan/SKILL.md` per the plan (site pages address the reader).
- [X] T032 Edit `charters/_common.md` rule 2 and `charters/lead.md` step 4, bump both versions,
  run `python3 -P -m wuwei agents build`; `tests/test_charters.py` and `tests/test_agents.py`
  stay green.
- [X] T033 Amend `docs/specs/2026-09-24-wuwei-design.md` (non-goal, 4.7, the owner-only floor
  bullet) and `.specify/memory/constitution.md` Principle VII and version, dated 2026-10-04,
  #478.

## Review fixes

- [X] T035 In `tests/test_grants.py`, add failing tests: under an Allow today grant, `cd other &&
  gh workflow run ...`, `cd other && git push ...`, `git -C`, `git -c` and `GIT_DIR=...` pushes to
  an environment branch are not cleared; a refused compound neither records nor spends a grant.
- [X] T036 In `cli/wuwei/guards/deploy.py`, run the git override and `--receive-pack`/`--exec`
  checks before the push denies; in `check`, mark a command moved (earlier cd, pushd or popd,
  `git -C`, a `GIT_*` env key) so `grants.gate` takes no cwd target, and record or spend grants
  only after every command passed. Set `CONFIG_CACHE_VERSION = 9` (main already uses 8).

## Finish

- [X] T034 Run the full suite; everything passes. Grep the changed files for em-dashes, emojis
  and absolute local paths and remove any.
