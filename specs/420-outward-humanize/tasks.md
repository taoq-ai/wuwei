# Tasks: Every external write goes through the humanizer pass by default

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root using
the interpreter the task names. Signatures, texts and formats are in plan.md.

## Config keys (US1, FR-001)

- [X] T001 In `tests/test_workspace.py`, add a failing test: a default config gives
  `config['outward']['humanize'] is True`, `humanize_kinds == ['dm', 'tracker', 'docs', 'pr', 'review']`
  and `humanize_strict is False`; `humanize_kinds = ["chat"]` raises `ConfigError`;
  `templates/workspace/config.toml` still loads. Fails today: `KeyError: 'humanize'`.
- [X] T002 In `cli/wuwei/workspace.py`, add the three keys to `SCHEMA['outward']`; in
  `templates/workspace/config.toml`, add the three commented lines under `[outward]`.

## The tells table covers the em dash (US1, FR-004)

- [X] T003 In `tests/test_outward.py` `test_tells_table`, add a `dash` hit with an em dash
  (the escape for U+2014 in `'Two options X A or B.'` in place of X); keep the existing rows. Fails today: `tells` returns `[]`.
- [X] T004 In `cli/wuwei/outward.py`, make the `dash` row match U+2013, U+2014 (as escapes) or ` -- ` and update
  the comment above `TELLS`.

## `humanize_lint`, the one function (US1, FR-002, FR-003)

- [X] T005 In `tests/test_outward.py`, add a failing table test for `outward.humanize_lint` on the
  `configured` fixture with the text `'This is not just a fix but a rewrite. We delve into it.'`:
  kind mapping (`{'chat'}` with `is_dm=True` gives `dm`; `{'chat'}` and `{'slack'}` give `review`;
  `{'tracker'}`, `{'code_host'}` give `tracker`, `pr`; `{'docs'}` gives `docs`; `{'customer'}`
  gives no event); default returns `(0, reason)` with both names and `humanizer` in the reason,
  appends one `outward.ai_tells` event `{'kind', 'tells', 'draft'}` whose JSON line does not
  contain the text, and prints `warning:` to stderr; `humanize_strict = true` returns
  `(1, reason)` and appends nothing; `humanize = false` and `humanize_kinds = ['dm']` (for a
  `review` text) return `(0, '')` with no event; a text with tells only in inline code returns
  `(0, '')`; an invalid payload (`{'text': 1}`) returns exit 2. Fails today:
  `AttributeError: humanize_lint`.
- [X] T006 In `cli/wuwei/outward.py`, add `import sys`, `KINDS`, `HUMANIZE` and `humanize_lint`.

## Ports: drafted and sent writes (US1, FR-005)

- [X] T007 In `tests/test_drafts.py`, add failing tests on the real chat port with the `root` and
  `sink` fixtures: (a) acceptance 1: `queued(root, 'I can deliver this tomorrow. This is not just
  a fix but a rewrite. We delve into it.')` stores `style == ['not-x-but-y', 'stock-word']` and
  today's events hold one `outward.ai_tells` with `{'kind': 'review', 'tells': [...], 'draft':
  True}`; (b) acceptance 2: with `[outward] humanize_strict = true` the post returns exit 1, the
  reason names both tells and `humanizer`, no draft row and no `draft.created` or
  `outward.ai_tells` event; (c) acceptance 3: with `humanize = false` the post drafts as before,
  no `outward.ai_tells` event and no `warning: outward: ai tells` on stderr, even with
  `humanize_strict = true`; (d) acceptance 4: `humanize_kinds = ["dm"]` gives no event for the
  post and one with `kind == 'dm'` for `adapter.dm(text)`. Fails today: no event, no refusal.
- [X] T008 In `tests/test_outward.py`, add a failing test for the send branch of
  `outward.check_call`: with `classify` monkeypatched to `(0, 'send')`, a clean text returns
  `(0, '')` and a text with a tell returns `(0, '')` plus an `outward.ai_tells` event with
  `'draft': False`; under `humanize_strict` it returns exit 1 with the findings; under
  `profile = "standard"` the strict finding is relaxed to `(0, '')` with a `hook.warning` event.
  Fails today: no event, exit 0.
- [X] T009 In `cli/wuwei/outward.py`, rewrite `check_call` as in plan.md (same signature).

## MCP writes through the hook (US1, FR-006)

- [X] T010 In `tests/test_outward.py`, add a failing test with the existing `payload()` helper
  (`tool='mcp__linear__create_comment'`, a tell in `text`): `guards.outward.check_lint` returns exit
  0 and records `outward.ai_tells` with `kind == 'tracker'` by default, and returns exit 1 with
  the findings under `humanize_strict = true`; a text without tells records nothing. Fails today:
  exit 0 and no event in both cases.
- [X] T011 In `cli/wuwei/guards/outward.py`, add `_lint` with its `ponytail:` comment and point
  `check_lint` at it.

## Writes outside the port wrapper (US1, FR-007)

- [X] T012 In `tests/test_pr_actions.py`, add a failing test on the `case` fixture, following
  `test_reply_draft_reaches_owner_queue`: with `humanize_strict = true` in the workspace config,
  `wuwei pr act <REF> --reply 'We delve into the race.'` exits 1, prints the findings and stores
  no draft; without strict it drafts and records `outward.ai_tells` with `kind == 'pr'` and
  `'draft': True`. Fails today: exit 1 with a stored draft and no event.
- [X] T013 In `cli/wuwei/pr_actions.py`, call `outward.humanize_lint` before `drafts.create`.
- [X] T014 In `tests/test_shepherd.py`, add a failing test following
  `test_raise_checks_gates_then_requests_recent_authors`: with `humanize_strict = true`,
  `shepherd.raise_pr(root, 'acme/widget', 'main', 'Feature', 'We delve into it.', 'ITEM-1')`
  returns 1 and `create_pr` is never called. Fails today: returns 0 and creates the PR.

## The walk test: no free text around the port (US3, FR-012)

- [X] T015 In `tests/test_outward.py`, add `test_every_free_text_adapter_write_goes_through_the_port`:
  for each kind and operation in `registry.PARAMETERS` whose parameters intersect
  `outward.TEXT_FIELDS | {'draft'}`, for each name in `registry.known(kind)`, load the module with
  `registry.load(kind, {'adapters': {kind: name}})` and assert the operation's
  `__code__.co_qualname == 'outward_operation.<locals>.decorate.<locals>.call'`, except
  `EXEMPT = {('tts', 'speak'): 'local', ('redactor', 'redact'): 'local',
  ('code_host', 'create_pr'): 'shepherd.raise_pr runs outward.lint and outward.humanize_lint'}`;
  the assertion message names kind, module and operation. Also assert the `raise_pr` source
  (`inspect.getsource(shepherd.raise_pr)`) contains `humanize_lint`, the exemption's premise.
  Fails today on that premise only; every current free-text operation is already wrapped.
- [X] T016 In `cli/wuwei/shepherd.py` `raise_pr`, call `outward.humanize_lint` on the title and
  body after `outward.lint` (makes T014 and T015 pass).

## Owner surfaces (US2, FR-008, FR-011)

- [X] T017 In `tests/test_drafts.py`, add failing tests: (a) `main(['drafts'])` lists the row with
  `style` naming both tells (passes today; keep as the acceptance guard); (b) with the `port`
  fixture and `integrity._host_confirm` replaced by a fake that records its `prompt` and returns
  True, `drafts approve <id>` sends once and the prompt contains the destination, the text and
  `not-x-but-y, stock-word`; (c) with `humanize_strict = true` set after queueing, `edit_to` a
  text with a tell and `drafts approve <id> --edit` exits 1 with the findings and `port[1] == []`.
  Fails today: (b) the prompt has no findings, (c) exit 0 and a send.
- [X] T018 In `cli/wuwei/drafts.py` `approve`, call `outward.humanize_lint` after the outward lint
  and add the findings line to the prompt.
- [X] T019 In `tests/test_remote.py`, add a failing test: with two pending drafts carrying three
  tells in total, `remote.handle` on a `status` event with a fake transport sends a text ending in
  `| ai tells 3` when `[owner.verbosity] dm = "full"`, and no `ai tells` at the default `brief`.
  Fails today: no count.
- [X] T020 In `cli/wuwei/remote.py`, append the count in the `status` branch at full DM verbosity.

## Metric and event kind (US1, FR-009, FR-010)

- [X] T021 In `tests/test_metrics.py` `test_ai_tells_per_text` (or a sibling), add two
  `outward.ai_tells` events, one `'draft': False` with two tells and one `'draft': True`; assert
  `ai_tells` gains exactly one `outward-<index>: 2` entry and keeps `draft-1` and `D-1`. In
  `tests/test_signal_status.py`, assert `signal.classify({'kind': 'outward.ai_tells', 'payload':
  {}}, {})[0] == 'silent'`; and `main(['event', 'outward.ai_tells', '{}']) == 1` with the producer
  named on stderr. Fails today: no `outward-` key and tier `nudge`.
- [X] T022 In `cli/wuwei/metrics.py`, count `draft is False` events; in `cli/wuwei/signal.py`, add
  the kind to `SILENT`; in `cli/wuwei/commands/event.py`, add the `EVENT_PRODUCERS` entry.

## Seats and the planner name the humanizer for outward text, once (US4, FR-013)

- [X] T023 In `tests/test_charters.py`
  `test_writing_for_a_person_names_the_humanizer_and_carries_the_checklist`, add failing
  assertions: the section names `tracker comments`, `docs pages`, `DMs`, `PR comments` and
  `review pings`, contains `outward.ai_tells` and `outward.humanize_strict`, and no longer
  contains `only an em dash or an emoji is refused`; each `agents/<role>.md` and
  `skills/wuwei-plan/SKILL.md` contains `humanizer` exactly once, and the skill names
  `tracker comments`. Fails today: the outward kinds are missing.
- [X] T024 Edit `charters/_common-authoring.md` and `skills/wuwei-plan/SKILL.md` as in plan.md, then
  run `bin/wuwei agents build` to regenerate `agents/*.md`; `bin/wuwei agents check` exits 0.

## Docs (FR-014)

- [X] T025 In `tests/test_docs.py`, add `('Humanizer', r'humanizer')` to `GLOSSARY` and a failing
  test: `configuration.md` names `` `outward.humanize` ``, `` `outward.humanize_kinds` `` and
  `` `outward.humanize_strict` ``; `concepts.md` contains `outward.ai_tells` and
  `humanize_strict`, and no longer says `a tell never blocks a send`; `reference.md`'s
  `drafts approve` row mentions humanize. Fails today: keys and glossary entry missing.
- [X] T026 Edit `docs/site/configuration.md`, `docs/site/concepts.md` (paragraph and `### Humanizer`
  glossary entry, two lines, last), `docs/site/reference.md` and the `README.md` credits link as
  in plan.md. Check every edited text with `outward.tells` and for em dashes.

## Finish

- [X] T027 Run `python -m pytest -q` from the repository root; everything passes. Grep the changed
  files for em dashes and emojis and for absolute local paths; remove any.
