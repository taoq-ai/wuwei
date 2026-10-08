# Tasks: People, channels and tools register

**Input**: `specs/552-graph-register/spec.md`, `plan.md`
**Rule**: every behaviour has its failing test first; run it, see it fail for the expected
reason, then implement. Tests are in-process with neutral fixtures in `tmp_path` (ids like
`C01`, `U01`, server `acme`, addresses at `example.test`).

## Phase 1: Foundational (the model)

- [X] T001 Write the failing tests for `build`, `views`, `sections` and `drift` in tests/test_graph.py: a fixture config that sets every modeled key of A4 (people with and without fields, a channel in both lists and in channel_classes, servers, modes, classes, authors with and without mention, owner fields, slack and login handles, voice sources, repo reviewers, mixed case and duplicates) gives `views(build(config)) == sections(config)`; `drift` is empty, then names `outbound.work_channels` after that key changes; register-only edges and names of `previous` survive a rebuild; every edge endpoint with a colon is a node
- [X] T002 Write the failing tests for `load`, `save`, `sync` and `warn` in tests/test_graph.py: missing is None; a symlink, bad JSON, extra keys, wrong version, a node id without a kind, an unknown attribute, an edge with an unknown type or view each raise `ValueError` naming the fix; `sync` writes only when different and never overwrites a damaged file; `warn` prints the one warning line to stderr
- [X] T003 Write the failing tests for `find`, `related`, `line`, `cite` and `annotate` in tests/test_graph.py: `find` by node id, bare id, people key, name, `#name`, `@name`, MCP tool name and `tool:<s>/<t>`; `cite` on `C01 in outbound.external_channels as client` returns only the external edge of a channel also in work_channels; `cite` on a reason ending `outward.modes` with tool `mcp__acme__send` returns the connector's mode edge; `annotate` is idempotent and `annotate(template) == template`
- [X] T004 Implement `cli/wuwei/graph.py` per plan (NAME, TYPES, VIEWS, COMMENT, TABLES, build, sections, views, drift, load, save, sync, warn, find, related, cite, line, annotate) until T001 to T003 pass
- [X] T005 Write the failing register-or-view invariant test in tests/test_graph.py: for a table of outbound and outward guard calls (`outward.classify` and `guards/outward` `resolve` over channels, people, a DM, a connector with a mode, a connector default class, a thread), decisions and reasons are identical from the fixture config and from the same config with every modeled key replaced by `views(build(config))`; it passes once T004 is done (no guard change). If tests/test_invariants.py exists on the base when building, add the same row there and to design 9.2 (A9)

## Phase 2: US2, upgrade, template and doctor (P1)

- [X] T006 [US2] Write the failing upgrade tests in tests/test_workspace.py: an upgrade of a workspace whose config sets every modeled key writes `.wuwei/graph.json`, prints `Upgraded .wuwei/graph.json: <n> nodes and <m> edges from config.toml`, holds a node per people key, channel, connector, author address, login, mention, handle and voice audience, keeps every owner value; adds `COMMENT` above each modeled header once; a second upgrade prints `No workspace changes needed`; `--dry-run` writes nothing and prints `Would upgrade`; a damaged register prints the warning, is left as it was and the rest of the upgrade runs; a fresh `init` has the empty register
- [X] T007 [US2] Add `templates/workspace/graph.json` and the `COMMENT` lines above `[owner]`, `[voice.sources]`, `[outbound]` and `[shepherd.authors]` in templates/workspace/config.toml
- [X] T008 [US2] Implement the register step in `upgrade` in cli/wuwei/commands/init.py until T006 passes
- [X] T009 [US2] Write the failing doctor tests in tests/test_doctor.py: the `register` row is `ok` with counts after an upgrade and on a fresh init; `warn` naming `outbound.work_channels` after a hand edit, with fix `wuwei init --upgrade` and `apply='init-upgrade'`, then `ok` after the upgrade; `warn` (never `fail`) for a missing or damaged register; the template row lists no `graph.json` line
- [X] T010 [US2] Implement `_register` and the `upgrades` filter in cli/wuwei/commands/doctor.py until T009 passes

## Phase 3: US3, every write path (P1)

- [X] T011 [US3] Write the failing writer tests in tests/test_config_writer.py: a confirmed `config set outbound.work_channels '["C05"]'` leaves `channel:C05 class team (outbound.work_channels)` in the register and doctor's register row `ok`; a `--from-card` set and a `calibrate --answer` write do the same; a damaged register leaves `config.toml` written with the usual exit, the damaged file byte-identical and one stderr warning
- [X] T012 [US3] Call `graph.sync` (and `graph.warn` on failure) in `offer` in cli/wuwei/commands/config.py until T011 passes
- [X] T013 [US3] Write the failing learn tests in tests/test_outbound_learn.py: a card with `--channels` (C01) and `--thread` (C01, participants U01 and U02 at a company domain) answered `approve` gives the register the connector, channel and people nodes with their names, the view edges and one `member_of` edge per participant naming the card; under `learn = "auto"` the edge has no `card`; the card text and the `outbound.learned` payload are unchanged; a register that fails to sync after the write warns and `apply` still returns CLEAN
- [X] T014 [US3] Store `thread_channel` in `learn` and add the names and members in `apply` in cli/wuwei/commands/outbound.py until T013 passes
- [X] T015 [US3] Write the failing records floor test in tests/test_protect_state.py: Write, Edit and a Bash redirect to `.wuwei/graph.json` are refused under observe, guarded and strict with the hint naming `bin/wuwei config set`, the cards and `bin/wuwei init --upgrade`
- [X] T016 [US3] Add `graph.json` to `_protected_name` and `_hint` in cli/wuwei/guards/protect_state.py until T015 passes

## Phase 4: US1, `wuwei who` (P1)

- [X] T017 [US1] Write the failing tests in tests/test_who.py (new) for spec US1 scenarios 1 to 6: `who C01` text and `--json`; `who U01`; `who connector:acme` and `who mcp__acme__send_message` with mode draft; `who login:dev` through `shepherd.authors`; an unknown name exits 1 naming `bin/wuwei outbound learn`; no register exits 1 naming `bin/wuwei init --upgrade`; a damaged register exits 2; nothing is written (state and register unchanged)
- [X] T018 [US1] Implement cli/wuwei/commands/who.py and register it (`who` in `READ_ONLY` in cli/wuwei/commands/__init__.py, the Recovery group in cli/wuwei/__main__.py) until T017 and tests/test_cli_known_command.py pass

## Phase 5: US4, `wuwei why` names the edge (P2)

- [X] T019 [US4] Write the failing tests in tests/test_why.py for spec US4 scenarios 1 to 5: `why <draft id>` prints `held: ...` then `edge: channel:C01 class client (outbound.external_channels)`; `why last refusal` adds the same line after the `fix:` line; a mode hold names `connector:acme mode draft (outward.modes)`; an unknown destination prints `edge: not recorded`; an unknown draft id exits 1 naming `bin/wuwei drafts`; item, decision and target-key output unchanged
- [X] T020 [US4] Implement the draft target, `held` and the refusal edge lines in cli/wuwei/commands/why.py until T019 passes

## Phase 6: Docs and polish

- [X] T021 Write the failing docs test in tests/test_docs.py: configuration.md has the section `People, channels and tools` naming `bin/wuwei who` and `bin/wuwei init --upgrade`, and each modeled key's row links to it; reference.md lists `bin/wuwei who`
- [X] T022 Write docs/site/configuration.md and docs/site/reference.md until T021 passes
- [X] T023 Run `python -m pytest -q` from the repository root (in the background, output to a file); all pass. Check every changed file for em-dashes, emojis and absolute local paths

## Dependencies

T004 before every later task. T007 and T008 before T009 to T010. T012 before T013 to T014
(apply's first sync runs through `offer`). Phases 4 and 5 need T004 and a register from
T012 or T008. Tasks in different files within a phase may run in parallel only after
their test task has failed.
