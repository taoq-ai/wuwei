# Tasks: Heartbeat: the watch proves the system is alive and behaving

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Plan details (signatures, values,
messages) are in plan.md.

## Setup

- [X] T001 In `tests/conftest.py`, add an autouse fixture that monkeypatches `wuwei.heartbeat.beat` to `lambda root: 0`, with a comment that `tests/test_heartbeat.py` restores the real one. It fails today with `ModuleNotFoundError: wuwei.heartbeat`; create `cli/wuwei/heartbeat.py` with only its docstring, `PROBES`, `STATUS_LINE_BUDGET_MS`, `CODES` and a `beat(root)` stub returning 2 so the suite collects. Run the full suite once: it must stay green.

## Shared helpers (FR-010, FR-011, FR-012, FR-002, FR-009)

- [X] T002 In `tests/test_hooks.py`, add a failing in-process test: a PreToolUse refusal from a stub guard through the existing `plugin` fixture with `session_id` `wuwei-heartbeat` appends no `hook.refusal` event and still exits 2 with the deny JSON; the same payload with another `session_id` appends one. Fails today on the first assertion.
- [X] T003 In `cli/wuwei/commands/hook.py`, add `HEARTBEAT_SESSION`, the `record=True` parameter on `refuse`, and pass `record=payload.get('session_id') != HEARTBEAT_SESSION` from `run`. Nothing else changes.
- [X] T004 In `tests/test_hooks.py`, add a static test: no module under `cli/wuwei/guards/` and not `cli/wuwei/commands/hook.py` imports `heartbeat` (AST scan of `Import` and `ImportFrom`). Passes once written; it pins US4.2.
- [X] T005 In `tests/test_integrity.py`, add failing tests for `integrity.fresh` with `integrity.PLUGIN` monkeypatched to a temporary plugin directory and a seeded verdict (`fakes.integrity.seed`): clean when every file is older than `verdict.json`; exit 1 naming `cli/x.py` and `changed after the cached verdict` when that file's mtime is set newer with `os.utime`; `__pycache__/*.pyc` newer files ignored; a cached exit 2 returned unchanged; a verdict recording a `checkout` returns clean without walking (`os.walk` monkeypatched to raise). Fails today with `AttributeError: fresh`.
- [X] T006 In `cli/wuwei/integrity.py`, add `fresh(root)` as in plan.md. `cached`, `check` and `measure` do not change.
- [X] T007 In `tests/test_workspace.py` (home of the `config check` tests), add failing in-process tests for `wuwei.commands.config.missing`: empty for the default config; `['LINEAR_API_KEY']` with `adapters.tracker = "linear"` and no variable; `'SLACK_BOT_TOKEN or SLACK_USER_TOKEN'` and `'SLACK_OWNER_DM_CHANNEL'` for slack chat; `codex.command` for the codex runtime with no command; `control_plane.owner` for slack inbound without a pin. The existing `config check` tests there pin that its output does not change. Fails today with `AttributeError: missing`.
- [X] T008 In `cli/wuwei/commands/config.py`, extract `requirements(config)` from `run` and add `missing(config)`, as in plan.md. `run` keeps its output and exit codes.
- [X] T009 In `tests/test_adapters.py`, add failing tests for the fixed adapter loaded with `registry.watch_service()`: `probe([(('state', 'set'), '')], cwd)` raises `ValueError` and starts nothing (`subprocess.Popen` monkeypatched to raise if called); with `LAUNCHER` pointed at a temporary shell script that echoes to stderr and exits 3, `probe` returns `(3, '<first stderr line>', ms)` for an allowlisted call and runs `during` exactly once; a script that sleeps past a 1 s `timeout` returns `(None, 'timeout', ms)` and leaves no child running; `ping('http://example.test/x')` raises `ValueError` without opening a connection (`urllib.request.urlopen` monkeypatched to raise if called). Fails today with `AttributeError: probe`.
- [X] T010 In `adapters/watch_service.py`, add `LAUNCHER`, `PROBE_ARGS`, `probe` and `ping` as in plan.md (concurrent start, stdin closed at start, one shared deadline, kill on timeout). `call` does not change.

## Probes (US1, FR-001 to FR-004)

- [X] T011 Create `tests/test_heartbeat.py` with `BEAT = heartbeat.beat` at import, a workspace fixture (initialised `.wuwei`, seeded verdict, `integrity.PLUGIN` on a temporary plugin dir, `fakes.host.Fake` through `registry.load`), and a fake `registry.watch_service` as in plan.md. Add failing tests for `heartbeat.measure`: every probe `ok` in `PROBES` order with values (`exit 2`, `exit 0`, `exit 2`, `<n> ms`, ..., `<n> MiB`); the four launcher calls carry the allowlisted argv, `status --line` first, payload `session_id` `wuwei-heartbeat`, cwd `<root>/.wuwei`, and the Write targets today's `state.json`. Fails today with `AttributeError: measure`.
- [X] T012 In `tests/test_heartbeat.py`, add failing table tests, one per probe outcome: refused exit 0 is `failed` `exit 0`; allowed exit 2 is `failed` with the stderr line; launcher `None` is `unmeasured` `timeout`; adapter raising `OSError` makes the four launcher probes `unmeasured` and the rest still measured; status_line over `STATUS_LINE_BUDGET_MS` is `failed`; a lock held on `state.lock` by a second `open()` + `fcntl.flock` makes `state` `failed` naming `state.lock` within about 1 s; tampered plugin file makes `integrity` `failed` naming it; `adapters.tracker = "linear"` without its variable makes `config` `failed` `missing LINEAR_API_KEY`; a stale `listen: clock` makes `clocks` `failed` with `listen dead`; a registered stale planner is `failed` `idle <n>s` and no planner is `ok` `no planner`; host `Fake` below the floor is `failed`; `adapters.host = "none"` is `unmeasured` and appends no `adapter: none` event. Plus `heartbeat.health` over ok, failed and unmeasured mixes.
- [X] T013 In `cli/wuwei/heartbeat.py`, implement `measure`, the probe helpers and `health` as in plan.md, importing `HEARTBEAT_SESSION` from `wuwei.commands.hook`.

## The watch tick, drift, page text and ping (US1, US3, FR-005, FR-006, FR-009)

- [X] T014 In `tests/test_heartbeat.py`, add failing tests for `beat` (restore `BEAT` with `monkeypatch`): it appends exactly one `heartbeat: clock` event whose payload has `health`, `probes`, `drift`, `page`, `ping` and stores the same record at `watch.heartbeat`; returns 0, 1 and 2 for ok, degraded and unmeasured; a second beat with `refused` flipped to exit 0 lists `drift == ['refused']`, page `behaviour drift: heartbeat refused failed: exit 0`, and prints `heartbeat: behaviour drift: refused`; a failure without a prior ok has no drift prefix; the page names the first failed probe in table order; `measure` raising `ValueError` prints `heartbeat unmeasured:` and returns 2 without raising.
- [X] T015 In `tests/test_heartbeat.py`, add failing ping tests with `watch.ping_url = "https://hc.example.test/ping/SECRET-TOKEN?k=QUERYVALUE"`: all ok sends exactly one ping and records `sent`; any failed or unmeasured probe records `withheld` and sends none; the fake ping raising `OSError` records `failed`, prints `heartbeat ping failed: hc.example.test: OSError`, and neither `SECRET-TOKEN` nor `QUERYVALUE` appears in captured output, `events.jsonl` or `state.json`; an empty URL records `off`.
- [X] T016 In `cli/wuwei/heartbeat.py`, implement `beat` and `_ping` as in plan.md.
- [X] T017 In `tests/test_watch.py`, add `'heartbeat: clock'` to the `test_producer_events_reserved` parameters, and in `tests/test_heartbeat.py` a failing test that `watch.tick` (real `BEAT` restored) calls the heartbeat once per tick after the clock line and that its return includes the heartbeat code (degraded heartbeat makes `tick` return at least 1). The tick test fails today because `tick` never calls the heartbeat.
- [X] T018 In `cli/wuwei/watch.py` `tick`, add the two lines after the clock block (plan.md); in `cli/wuwei/commands/event.py` add `'heartbeat: clock': 'wuwei watch'` to `EVENT_PRODUCERS`; in `cli/wuwei/workspace.py` add `watch.ping_url` to `SCHEMA`.

## Status line, page and silence (US2, FR-007, FR-008)

- [X] T019 In `tests/test_signal_status.py`, add `'heartbeat: clock': 'silent'` to the expected tiers in `test_emitted_kinds_have_intended_tiers`, and failing status tests over hand-written day events (use the `day` helper): with a fresh `watch: clock` and a heartbeat `ok` line, `status --line` contains `health ok` and `pages 0`; with a `degraded` line whose page is `heartbeat integrity failed: ...`, the line shows `health degraded`, `pages 1`, and `nudges` returns one row with source `heartbeat` and that reason; a later `ok` line clears the page; a heartbeat line with a stale watch clock gives `health unmeasured` and no heartbeat page; a malformed payload (health `fine`) gives `health unmeasured`; no heartbeat line gives no `health` part and `status --json` `health` null; `test_status_line_and_json_share_snapshot` and the other existing line tests keep passing unchanged.
- [X] T020 In `cli/wuwei/signal.py` add `'heartbeat: clock'` to `SILENT`; in `cli/wuwei/commands/status.py` update `scan`, `snapshot` and `line` as in plan.md (one pass, fourth return value).

## Acceptance through the real launcher (US2.2, US2.3, US1.1)

- [X] T021 In `tests/test_heartbeat.py`, add the real-launcher smoke test (plan.md, Test plumbing): on a healthy seeded workspace every probe is `ok` and `heartbeat` (the command, via `wuwei.__main__.main(['heartbeat'])`) exits 0 printing one line per probe; the events file is byte-identical before and after (no `hook.refusal`, no `heartbeat: clock`) and no ping is sent.
- [X] T022 In `tests/test_heartbeat.py`, add the tamper acceptance test through the real launcher: after one ok `beat`, set a copied plugin file's mtime newer than the verdict, `beat` again: `integrity` is `failed` naming the file, `status.line(status.snapshot(day))` has `health degraded` and `pages 1`, `status.attention` has one `heartbeat` page naming `integrity`, the fake ping (only `ping` faked, `probe` real) was called once for the first beat and not for the second; reseed the verdict, `beat` a third time: page gone, `health ok`.
- [X] T023 In `tests/test_heartbeat.py`, add the mutation acceptance test: the plugin copy with `discover = lambda: []` appended to `cli/wuwei/commands/hook.py`; `beat` records `refused` `failed` `exit 0`, the page is `heartbeat refused failed: exit 0`, `state_write` is also failed, and no ping is sent.
- [X] T024 Make T021 to T023 pass by fixing only the code they expose in `adapters/watch_service.py` or `cli/wuwei/heartbeat.py`; record any fix in plan.md.

## On-demand command (US1, FR-004)

- [X] T025 In `tests/test_heartbeat.py`, add failing in-process tests for `main(['heartbeat'])` with the fake adapter: prints `<name>: <result> <value>` for all ten probes in order; exits 1 when one probe failed and 2 when one is unmeasured and none failed; writes no `state.json` and no event; outside a workspace exits 2. Fails today because the command does not exist.
- [X] T026 Create `cli/wuwei/commands/heartbeat.py` as in plan.md.

## Latency (US4.1)

- [X] T027 In `tests/test_hooks.py`, add `test_heartbeat_latency` using the `seeded_workspace` fixture: real launcher (the seeded plugin copy, `registry.watch_service` returning the adapter module with `LAUNCHER` on the copy), ping off, restore the real `heartbeat.beat`, run `heartbeat.beat(root)` 20 times (60 with `WUWEI_BENCH=1`), compute wall and CPU (self plus children `getrusage`) p95, and call `assert_latency_budget('heartbeat tick', cpu_ms, wall_ms, capsys, wall_budget=200, runs=runs)`. Run it with `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency` on the Mac and record the printed line in plan.md. If it is over 200 ms, move work into `during` or out of the tick, not the budget.

## Docs (FR-001, FR-009)

- [X] T028 In `tests/test_docs.py`, add a failing test: every name in `heartbeat.PROBES` appears in backticks in `docs/site/reference.md` under a `## Heartbeat` heading, together with `heartbeat: clock`, `health degraded`, `behaviour drift` and `watch.ping_url`; `docs/site/configuration.md` documents `` `watch.ping_url` ``; `docs/site/remote.md` no longer says `no external dead-man ping`.
- [X] T029 Write the docs and template changes listed in plan.md (`docs/site/reference.md`, `docs/site/configuration.md`, `docs/site/remote.md`, `templates/workspace/config.toml`).

## Finish

- [X] T030 Run `python -m pytest -q` from the repository root; everything passes. Check every changed file for em-dashes, emojis and absolute local paths and remove any.
