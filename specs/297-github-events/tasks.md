# Tasks: GitHub events reach the planner and the owner

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Plan details (signatures, texts, order)
are in plan.md.

## Precise summary in the event, the wake and the nudges (US1, FR-001 to FR-003)

- [X] T001 In `tests/test_watch.py`, add failing tests for `watch.facts` and `watch.summary`: two thread comments by `alice` on a thread with `path` `cli/x.py` plus check `test (3.11)` going to `failure` give exactly `PR example/project#7: 2 new review comments by alice on cli/x.py; check test (3.11) failed`; one table case each for `now watched`, `no longer owned`, `merged`, `new commits pushed (head bbbbbbb)`, `conflicts with its base`, `conflicts resolved`, `1 new comment by bob`, `approved by carol`, `changes requested by carol`, `check ci passed`, `review requested from dave`, and `updated (updated_at)`; a thread without `path` omits ` on `; no comment body appears in `facts`. Fails today with `AttributeError: facts`.
- [X] T002 In `cli/wuwei/watch.py`, add `facts` and `summary` as in plan.md.
- [X] T003 In `tests/test_watch.py`, extend `test_pr_poll_persisted_diff_wakes_once` (or add a sibling) so the `pr.changed` payload has a `summary` starting `PR example/project#7: `, the stdout line is `planner wake: <summary>`, `watch.saved(root)['facts']` holds the PR and no body text, and a second poll records nothing; add a failing test that after a `pr_actions.observe` failure (mergeable `None`, as in `tests/test_pr_ownership.py::test_poll_classification_failure_preserves_change_wake`) the stored facts match the stored snapshot's poll. Fails today: no `summary` key.
- [X] T004 In `cli/wuwei/watch.py` `poll`, compute and save facts and write the summaries as in plan.md.
- [X] T005 In `tests/test_listen.py`, add failing tests next to `test_wake_marker_merges_prs_and_inbox`: `mark_wake(..., summaries=['PR a: x'])` then `summaries=['PR a: y']` while unseen keeps both in order; after the wake is consumed a new mark keeps only the new line; 25 lines keep the last 20; `watch.wake` returns the summary lines first and the unchanged `planner wake (...)` line last; a summary-only mark with the same PRs is not dropped by the "already covered" early return; `test_pr_only_marker_is_unchanged` stays unchanged and passing. Fails today: `mark_wake` has no `summaries` parameter.
- [X] T006 In `cli/wuwei/watch.py`, update `mark_wake` and `wake` as in plan.md.
- [X] T007 In `tests/test_watch.py`, add a failing lifecycle test: after a summarised change, `lifecycle.stop` for the registered planner returns exit 1 with a message whose first line is the summary; `lifecycle.session_start` includes the summary. Passes once T004 and T006 are done; run it to confirm it failed before them only on the missing summary.
- [X] T008 In `tests/test_signal_status.py`, add failing tests over day events: a `pr.changed` with `summary` after an unrelated nudge makes `status.attention` return the `pr.changed` row first with the summary as reason; two `pr.changed` for the same PR give one row with the latest summary; a later `session: wake-seen` removes the row; an old-format `pr.changed` (no summary) gives reason `example/project#7 changed: checks`; `status.line(status.snapshot(day))` contains `prs 1 changed` and none after the wake is seen; existing line tests stay unchanged. Fails today: reason is `pr.changed` and the row never clears.
- [X] T009 In `cli/wuwei/commands/status.py`, update `scan`, `snapshot` and `line` as in plan.md.

## Conditional probe in the code host port (US2, FR-004)

- [X] T010 In `tests/test_adapters.py`, add `probe` with parameters `('ref', 'tags')` to the `code_host` rows of `CALLS`. `test_module_contracts` fails today: the registry and the adapters lack `probe`.
- [X] T011 In `cli/wuwei/registry.py` add `'probe': ('ref', 'tags')`; in `adapters/code_host/none.py` add `probe`; in `tests/fakes/code_host.py` add `probe`.
- [X] T012 In `tests/test_code_host.py`, add failing tests with a `subprocess.run` stub: with empty tags, three calls `gh api repos/example/project/pulls/7 --include --hostname github.com`, then `.../commits/<head>/check-runs?per_page=100 --include ...` and `.../statuses?per_page=100 --include ...`, each answering `HTTP/2.0 200 OK`, an `Etag: W/"..."` header, a blank line and JSON, give `modified: true` and all three tags plus `head`; with those tags and every call answering `HTTP/2.0 304 Not Modified` headers with exit 1, the argv carry `-H 'If-None-Match: W/"..."'` and the result is `modified: false` with the same tags; a 304 on the PR with a 200 on check runs is `modified: true`; a 304 for the PR with no stored `head` is exit 2; a nonzero exit without a 304 status line is exit 2 and prints no body; `_run(['api', 'repos/o/r/pulls/1', '--include', '-H', 'If-None-Match: "a"\nX: y'])` raises before spawn; `threads` returns `path` from a node that has it and `None` from one that does not. Fails today with `AttributeError: probe`.
- [X] T013 In `adapters/code_host/github.py`, change `_THREADS`, `threads`, `_run` and add `_conditional` and `probe` as in plan.md.

## The listener takes over PR polling (US2, FR-005, FR-006)

- [X] T014 In `tests/test_watch.py`, add failing tests: `watch.poll_prs` calls `poll` then `merge.poll` and saves `poll_at`; `watch.listening` is true with a `listen: clock` line within `listen.dead_seconds` and false with none or a stale one; `watch.tick` with `poll_at` due and a live listener does not call `poll` (monkeypatch it to fail), and does call it with no listener. Fails today with `AttributeError: poll_prs`.
- [X] T015 In `cli/wuwei/watch.py`, add `poll_prs` and `listening` and change `tick` as in plan.md.
- [X] T016 In `tests/test_listen.py`, add failing listener tests with the code host fake (one owned PR) wired through `registry.load`: (a) a first tick with `probe` returning `modified: true` runs one full read, writes `poll_at` and keeps the returned tags in the dict passed to `tick`; (b) a second tick, within 120 s and after the clock line, with `probe` returning `modified: false` leaves `events.jsonl` and `state.json` byte-identical and never calls `watch.poll` (monkeypatched to fail); (c) a probe returning exit 2 or `{'modified': 'yes'}` runs the full read; (d) `poll_at` older than `pr.poll_seconds` runs the full read even when not modified; (e) a full read returning 2 empties the tags dict and the tick returns 2; (f) a new review comment on the fake host with `probe` modified makes one tick record `pr.changed` with the summary, `lifecycle.stop` for the planner names it, and `status.attention` lists it first (issue acceptance 1, host side). Fails today: `tick` takes no tags and never probes.
- [X] T017 In `cli/wuwei/listen.py`, add `PROBE_SECONDS`, `prs`, the `tags` parameter and the new `run` delay as in plan.md.

## Owner DM (US5, FR-011)

- [X] T018 In `tests/test_listen.py`, add failing tests with `SLACK_OWNER_DM_CHANNEL=D1`, the real `remote.TRANSPORT` and a recording chat port behind `registry.load('chat', ...)` (as the `chat` fixture in `tests/test_remote.py` does, so the security check and the outward lint in `remote.dm` run): one summarised `pr.changed` gives one DM starting with the summary and one `pr.notified {pr, at}` event, and a second tick sends nothing; with autostart off and a conflicted episode the DM ends with `Shepherd autostart is off; nothing started.`; with `control_plane.content = "none"` the DM is `An update is waiting in the workspace.`; a summary naming `cli/wuwei/guards/deploy.py` sends `PR #7 changed; details are on the host.`; a transport exit 2 records nothing and the tick returns 2; without `SLACK_OWNER_DM_CHANNEL` or with `responder.enabled = false` nothing is sent. Also assert every fixed tail and the fallback line pass `outward.lint(..., to_owner=True)`. Fails today: the listener sends no PR DM.
- [X] T019 In `cli/wuwei/listen.py`, add `notify` and call it in the responder block as in plan.md.

## Seat marker: no merge, drafts only (US4, FR-009, FR-010)

- [X] T020 In `tests/test_merge.py`, add a failing test: with `WUWEI_SEAT_ROLE=shepherd` (monkeypatch.setenv), `merge.execute` on a PR the existing happy-path fixture clears returns exit 1 with `merge refused: a shepherd seat never merges`, the host fake records no `merge` call and no `merge.*` event is written; `main(['merge', REF])` exits 1; without the variable the existing happy path is unchanged. Fails today: the merge goes through.
- [X] T021 In `cli/wuwei/merge.py` `execute`, add the guard as in plan.md.
- [X] T022 In `tests/test_outward.py`, add a failing test: a text and context that `outward.classify` sends today (`ack.` on an owned PR thread, `kind='code_host'`, as an existing send case) returns `(1, 'draft')` with `WUWEI_SEAT_ROLE=shepherd`; the code host `comment` port wrapped by `registry.outward_operation` stores a draft and does not call the wrapped operation. Fails today: tier is send.
- [X] T023 In `cli/wuwei/outward.py` `classify`, add the marker check as in plan.md.
- [X] T024 In `tests/test_runtime.py`, add failing tests on `headless_case`: `variables={'WUWEI_SEAT_ROLE': 'shepherd'}` puts the variable in the `env` passed to `subprocess.run`; `variables={'PATH': 'x'}` and `variables={'WUWEI_SEAT_ROLE': 1}` return exit 2 without spawning. Fails today: unexpected keyword `variables`.
- [X] T025 In `adapters/runtime/claude.py` `headless`, add `variables` as in plan.md.

## Headless shepherd seat (US3, FR-007, FR-008, FR-012)

- [X] T026 In `tests/test_sessions.py`, add a failing test that `sessions.record(..., role='shepherd')` is accepted and `sessions.rows` reports role `shepherd`. Fails today with `ValueError: session role must be one of`.
- [X] T027 In `cli/wuwei/sessions.py`, add `shepherd` to `ROLES`.
- [X] T028 In `tests/test_workspace.py`, add a failing test that `load_config` gives `shepherd.autostart` `False` by default and accepts `true`. Fails today: unknown key.
- [X] T029 In `cli/wuwei/workspace.py` add the schema key; in `templates/workspace/config.toml` add the commented `autostart = false` line.
- [X] T030 In `tests/test_shepherd.py`, add failing unit tests for `shepherd.pending` and `shepherd.headless` (plumbing in plan.md): `pending` lists a `conflicted` episode, skips `approved` and `waiting`, a parked PR and an episode with a `shepherd.dispatched` event today; `headless` on the conflicted episode writes `shepherd.dispatched` first, logs one `brief written` for role `shepherd` whose body contains `wuwei pr act example/project#7 --run`, `--complete` and `Never run wuwei merge`, calls the fake runtime's `dispatch` then `headless` once with the prompt starting `WUWEI brief: `, the `shepherd` tool list from `agents/allowlist.json` and `variables={'WUWEI_SEAT_ROLE': 'shepherd'}`, leaves the seat `stopped`, registers the returned session with role `shepherd`, and writes one `shepherd.finished` with exit 0 and a planner wake whose summary is `PR example/project#7: shepherd conflicted: turn ended (exit 0, session <8 hex>)`; free memory below the floor makes `headless` return 1 with no runtime `headless` call and `shepherd.finished` exit 1 naming the floor; a PR with no linked item returns 2 with the reason and no brief; the `ci_red`, `threads_unanswered` and `review_stale` bodies name their `wuwei pr act` commands. Fails today with `AttributeError: pending`.
- [X] T031 In `cli/wuwei/shepherd.py`, add `HEADLESS`, `pending`, `headless` and `_finish` as in plan.md.
- [X] T032 In `tests/test_listen.py`, add the listener acceptance tests (issue acceptance 2): with `shepherd.autostart = true`, a conflicted owned PR linked to an item with a worktree and the fake runtime injected (monkeypatch `registry.load` for `runtime`), two ticks dispatch exactly once, the session is in the registry with role `shepherd`, and the planner's next `lifecycle.stop` message names the shepherd result; with autostart off no `brief written`, no runtime call and no `shepherd.dispatched`; with `responder.enabled = false` nothing is dispatched. Fails today: the listener never dispatches.
- [X] T033 In `cli/wuwei/listen.py` `tick`, add the `pending` read and the one-per-tick dispatch as in plan.md.
- [X] T034 In `tests/test_watch.py` add `shepherd.dispatched`, `shepherd.finished` and `pr.notified` to `test_producer_events_reserved`, and in `tests/test_signal_status.py` add their expected tiers to `test_emitted_kinds_have_intended_tiers` (`shepherd.finished` silent with exit 0, nudge with exit 1). Fails today for the tiers (the kinds default to nudge).
- [X] T035 In `cli/wuwei/signal.py` and `cli/wuwei/commands/event.py`, apply the changes in plan.md.

## Docs (US6, FR-013)

- [X] T036 In `tests/test_docs.py`, add a failing test: `docs/site/configuration.md` documents `` `shepherd.autostart` `` and says `30 s` in the `pr.poll_seconds` row; `docs/site/daily.md` mentions `prs 1 changed` or `prs <n> changed`, `next turn` and `PR monitor`; `docs/site/remote.md` mentions `If-None-Match`, `shepherd.autostart`, `details are on the host` and `no webhooks`; extend `test_shepherd_settings_are_visible_in_template_and_site` with `autostart` (template value `false`).
- [X] T037 Write the docs changes listed in plan.md (`docs/site/configuration.md`, `docs/site/daily.md`, `docs/site/remote.md`), keeping every string `test_remote_runbook_matches_the_code` and `test_every_template_config_key_is_documented` check.

## Finish

- [X] T038 Run `python -m pytest -q` from the repository root; everything passes (listener and watch tests that count events may need the new backstop full read accounted for; fix the code, not the assertion, unless the assertion counted a write this feature removes or adds by design, and record that in plan.md). Check every changed file for em-dashes, emojis and absolute local paths and remove any.

## Review fixes

- [X] T039 (F1) In `tests/test_pr_guards.py` add a hook-level test that runs `WUWEI_SEAT_ROLE= bin/wuwei merge x#1` and `env -u WUWEI_SEAT_ROLE bin/wuwei merge x#1` under `WUWEI_SEAT_ROLE=shepherd` and asserts deny; then in `cli/wuwei/guards/pr.py` deny, under the shepherd role, any command or script that mentions `merge` or `WUWEI_SEAT_ROLE`, or runs `env`/`unset` on a `WUWEI_` variable. Document the hook enforcement in `docs/site/remote.md`.
- [X] T040 (F2) Reword the `docs/site/remote.md` autostart line: a refused launch is not retried until the PR state changes.
