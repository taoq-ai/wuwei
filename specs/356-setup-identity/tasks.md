# Tasks: setup identity, adapter interview and the doctor PR flow section

**Input**: `specs/356-setup-identity/` (spec.md, plan.md)

Test first, always: each test task is written, run with the command given, and seen to fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. No absolute local paths, client, repository or
handle names (use `acme/*`, `pat-example`, `example.com`/`example.test` values), emojis or
em-dashes in any file. Tests never need the network or the real `gh`: use the replay
recordings, `tests/fakes/code_host.py` and the existing SimpleNamespace fakes.

## Phase 1: the code_host port (setup's inputs)

- [X] T001 Test, `tests/test_adapters.py`: add `('code_host', 'viewer_login', (), True)` to
  `CALLS`. Run `python -m pytest -q tests/test_adapters.py` (fails: no such operation on
  the `github` and `none` adapters, no `PARAMETERS` entry).
- [X] T002 Test, `tests/fixtures/code_host/recordings.json` and `tests/test_code_host.py`:
  add a `viewer_login` recording (`argv` `api user --hostname github.com`, stdout
  `{"login": "pat-example", ...}`, `data` `{"login": "pat-example"}`) and add
  `'viewer_login'` to `CASES`, so the existing fail-closed matrix (error body, `null`,
  `{}`, `[]`, non-JSON, exit 1) runs against it. Update the `merged_prs` recording: the
  query reads `first:50` and `author{__typename login ...on Bot{databaseId}}`; stdout has
  one `User` node (`pat-example`), one `Bot` node (`dependabot`, `databaseId` 49699333)
  and one node with `author: null`; `data` rows carry `author` and `author_email`
  (`dependabot[bot]`, `49699333+dependabot[bot]@users.noreply.github.com`; the user row
  `pat-example`, `None`; the null row `None`, `None`). Run
  `python -m pytest -q tests/test_code_host.py -k "viewer_login or merged_prs"` (fails).
- [X] T003 Implement: `cli/wuwei/registry.py` (`'viewer_login': ()`),
  `adapters/code_host/github.py` (`_run` case `['api', 'user']`, `viewer_login`,
  `_MERGED`, `merged_prs` author fields), `adapters/code_host/none.py` (`viewer_login`),
  `tests/fakes/code_host.py` (`viewer_login`). Rerun T001 and T002; pass.

## Phase 2: US1, setup fills the identity

- [X] T004 [US1] Test, `tests/test_calibrate.py` (`test_survey_keeps_bot_authors`):
  `survey` with a fake code host whose `merged_prs` returns the T002 rows gives
  `result['bots'] == {'49699333+dependabot[bot]@users.noreply.github.com':
  'dependabot[bot]'}` and the same `baseline` as before; `merged_prs` exit 2 gives
  `bots is None`; `merged_prs` is called once per repository. Run
  `python -m pytest -q tests/test_calibrate.py -k bot_authors` (fails).
- [X] T005 [US1] Implement `bot_authors` and the `survey` change in
  `cli/wuwei/calibrate.py`. Rerun T004; passes.
- [X] T006 [US1] Test, `tests/test_calibrate.py` (`test_apply_writes_author_inline_table`):
  `calibrate.apply(template_raw, [(('shepherd', 'authors'), 'pat@example.test',
  {'login': 'pat-example'})])` yields the line `"pat@example.test" = {login =
  "pat-example"}` inside `[shepherd.authors]`, the text loads through
  `workspace.load_config` with `mention == ''`, and the same addition on a config without a
  `[shepherd.authors]` header appends the table. In the same file: a `shepherd.authors`
  entry without `mention` loads through `load_config` (today it raises `mention:
  required`). Run `python -m pytest -q tests/test_calibrate.py -k author`
  (fails).
- [X] T007 [US1] Implement: `cli/wuwei/workspace.py` (`mention` default `""`) and
  `cli/wuwei/calibrate.py` `apply` (quoted key for `('shepherd', 'authors')`, inline table
  for a dict value). Rerun T006; passes.
- [X] T008 [US1] Test, `tests/test_setup.py`: add `viewer_login` to the `host` fixture
  (`Result(0, {'login': 'pat-example'})`, switchable) and bot rows to its `merged_prs`.
  `test_discovery_reads_the_login` (`discover` lines contain `code host login:
  pat-example` and `found['login'] == 'pat-example'`; with auth missing, `code host login:
  unmeasured`, `found['login'] is None`, `viewer_login` not called).
  `test_identity_settings` (pure `setup.identity`): empty config gives the handles,
  lead_login and one authors setting per lowercase identity email and per bot email; a
  chat-ID-only `handles` (`["U0123ABC"]`) gives `["U0123ABC", "pat-example"]`; an existing
  code-host handle, two code-host handles, a set `lead_login`, an already mapped email
  (any case) are not proposed; `login=None` gives only the bot entries. Run
  `python -m pytest -q tests/test_setup.py -k "login or identity"` (fails).
- [X] T009 [US1] Test, `tests/test_setup.py` (`test_setup_fills_identity_end_to_end`): a
  confirmed `run_setup` on the three-repository project writes `owner.handles =
  ["pat-example"]`, `shepherd.lead_login = "pat-example"` and `[shepherd.authors]` entries
  for `pat@example.test` and the bot email; the printed digest has each as one `+` line;
  a second run proposes no identity line. Run `python -m pytest -q tests/test_setup.py -k
  fills_identity` (fails).
- [X] T010 [US1] Implement in `cli/wuwei/commands/setup.py`: `discover` reads the login,
  new `identity(config, login, results)`, `_setup` extends `extra` with it after
  `calibrate.survey`. Rerun T008 and T009; pass. Then fix any existing
  `tests/test_setup.py` and `tests/test_interview.py` assertion whose digest now includes
  the identity lines (update, never weaken), and add `viewer_login` to the
  SimpleNamespace fakes in `tests/test_interview.py` (`:386`, `:422`).

## Phase 3: US2, the interview chooses the adapters

- [X] T011 [US2] Test, `tests/test_interview.py`: `test_adapter_questions` (`effects`:
  `tracker` `Linear` gives `{'adapters.tracker': 'linear'}`, `None` gives `'none'`;
  `chat` `C0123ABCD` gives `{'adapters.chat': 'slack', 'shepherd.review_channel':
  'C0123ABCD'}`, `Slack` gives only the adapter, `c-lower` is refused naming the expected
  form; `review_bot` `Greptile` gives `'greptile'`; each new row is in `widgets(...)`).
  `test_adapter_answers_promote_and_name_credentials`: record `tracker=Linear` and
  `chat=None` with `interview.record`, run `config promote` with a confirming callback
  (or `config.proposal` plus `offer`), then `load_config` has `adapters.tracker ==
  'linear'`, `adapters.chat == 'none'`, and `config.missing(config)` contains
  `LINEAR_API_KEY` (and `config check` output names it, exit 1). Run
  `python -m pytest -q tests/test_interview.py -k adapter` (fails: unknown question).
- [X] T012 [US2] Implement `_channel` and the three `QUESTIONS` rows in
  `cli/wuwei/interview.py`. Rerun T011; passes. Run `python -m pytest -q
  tests/test_interview.py tests/test_setup.py` and fix any test that counted the question
  table.

## Phase 4: US3, doctor PR flow

- [X] T013 [US3] Test, `tests/test_doctor.py`: first add filled `owner.handles = ["ada"]`,
  `shepherd.lead_login = "ada"` and `"ada@example.com" = {login = "ada"}` to `CONFIG` so
  the healthy and trial tests stay exit 0. Then `test_pr_flow_rows` (parametrized over
  `doctor.pr_flow(config)`): empty handles warns with value ending `will block: reviewer
  selection, review replies and obligations at pr raise` and fix
  `bin/wuwei config set owner.handles '["<code-host login>"]'`; empty lead_login, empty
  authors warn with their phase and fix; `adapters.chat = "slack"` with an empty channel
  adds a warning `shepherd.review_channel` row, and chat `none` has no such row;
  `adapters.*` `none` rows are `ok` with the `none: ...` text; `min_reviewers = 0` makes
  lead, authors and channel `ok` `not applicable: shepherd.min_reviewers = 0` while empty
  handles still warns; every non-ok row has `fix` and `docs`. `test_pr_flow_in_full_report`
  (`main(['doctor'])` prints `PR flow` after `Gates and adapters`).
  `test_pr_flow_section_only` (`main(['doctor', '--section', 'pr-flow'])` prints only the
  PR flow header and rows, exit 1 with a warn and 0 when filled; `heartbeat.measure`,
  `init.upgrade` and the code host are not called; with `--json` the rows all have
  `section == 'pr-flow'`; a config that does not load gives one `unmeasured` row and exit
  2). Run `python -m pytest -q tests/test_doctor.py -k pr_flow` (fails).
- [X] T014 [US3] Implement in `cli/wuwei/commands/doctor.py`: `SECTIONS` and `DOCS`
  entries, `pr_flow(config)`, `diagnose(section=None)`, `--section` in `register`, `run`
  passing it. Rerun T013, then `python -m pytest -q tests/test_doctor.py`; all pass,
  `test_fix_allow_list_is_pinned` unchanged.

## Phase 5: US4, the planner shows the rows

- [X] T015 [US4] Test, `tests/test_plan.py` (`test_propose_sweep_has_pr_flow`): `propose`
  on a workspace with empty `owner.handles` writes a plan.md sweep line `- pr-flow:
  measured: 1 warn (owner.handles); wuwei doctor --section pr-flow` (names as
  warned), and on a filled workspace `- pr-flow: measured: ok`. Test,
  `tests/test_docs.py` (extend `test_owner_interview_is_documented_next_to_calibration` or
  add `test_pr_flow_is_documented`): `skills/wuwei-plan/SKILL.md` contains
  `wuwei doctor --section pr-flow`; `docs/site/reference.md` Doctor section contains `PR
  flow` and `--section pr-flow`; `docs/site/configuration.md` Owner interview section
  names `tracker`, `chat` and `review_bot`. Run `python -m pytest -q tests/test_plan.py
  tests/test_docs.py -k "pr_flow or interview"` (fails).
- [X] T016 [US4] Implement: the sweep line in `cli/wuwei/plan.py` `propose`; the paragraph
  in `skills/wuwei-plan/SKILL.md`; the docs in `docs/site/reference.md`,
  `docs/site/configuration.md` (interview rows, optional `mention`) and
  `docs/site/daily.md` (what setup fills, the three new questions). Rerun T015; passes.

## Phase 6: verification

- [X] T017 Run the full suite, `python -m pytest -q`; everything passes. Grep every changed
  file for em-dashes, emojis, absolute local paths and real handles or client names, and
  remove any.
