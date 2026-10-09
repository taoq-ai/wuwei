# Implementation Plan: The fixture day for autonomous and supervised, and the invariant table checked against what landed

**Branch**: `530-posture-day` | **Spec**: `spec.md` | **Base**: main at or after 705250f

## Summary

Tests and one design table; no new runtime rule. Two fixture days on the existing `wuwei next`
walk prove #530's acceptance, one per setup answer, counting the cards the owner answered and
letting WUWEI merge. The design 9.2 table and `tests/test_invariants.py` get rows I19 to I21,
I3 and I8 checked against the built paths, the merge family moved from `OWNED` to `EXEMPT`,
the #529 walls re-noted to a follow-up, and a test that fails on an owner mark naming a merged
issue. Production code changes only for an FR-010 defect, plus one stale code comment.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. All in process: `tests/fakes/day.py` drives the CLI
through `wuwei.__main__.main` and every planner call through the PreToolUse hook; ports are
fakes (`fakes.code_host.Fake`, `fakes.vcs.Fake`, the chat `Recorder`); git runs locally under
`tmp_path`; the network is forbidden by the fixture.

## Constitution Check

- IV test first: every task is a test, or a table or fix whose failing test comes first. Pass.
- V ponytail: the walk loop is extracted once and shared, not copied; no harness, no fixture
  class, no helper module; invariant checks reuse `Rules`, `memo`, `READS` and the
  `tests/test_merge.py` fixtures. Pass.
- VII security: no new refusal under observe or guarded; nothing trusted becomes writable by a
  seat (the tests read CLI-written `decision_routes`, `decision_outcomes`, `drafts`, events).
  The merge-family refusals stay; only their table classification moves. Pass.
- Workflow: the walls #529 left and the stale orientation text are recorded under Deferred,
  not built silently. Pass.

## Step 0: the base (T001)

The worktree branch was cut at 327dd57. Confirm the base holds `tests/test_invariants.py`
with I1 to I18, `tests/test_path_day.py`, `specs/524-merge-grant`, `specs/530-setup-autonomy`
and an `interview.QUESTIONS` row `autonomy`. If not, stop and report that the worktree must be
brought to main (no commits are on the branch, so it fast-forwards); build nothing else.

## Changes

### `tests/test_path_day.py` (US1, US2; FR-001 to FR-006)

Reuse, do not copy: the `day` fixture body, `call`, `bash`, `launch`, `Day.execute`,
`Day.raise_pr`, `Day.data`, `Day.events`, `Day.directory`; `record` and `LEAD` from
`tests/test_decision_classes.py`; `CARD` from `tests/test_invariants.py`.

1. `prepare(day, skip=())`: the current fixture body (session env, calibration file, worktree
   stub, earlier-day `interview.json`), with the rows in `skip` left out of that file. The
   `day` fixture becomes `prepare(Day(..., solo=True))`. No behaviour change.
2. `walk(day, card, after=None, looks=1)`: the loop of
   `test_the_day_closes_walking_only_next` moved out unchanged, with two hooks:
   `card(day, action)` answers a `card` row (the existing test passes its current handler:
   record with the first option, then the PostToolUse, `asks += 1`), and
   `after(day, action)` runs after each action (the existing test passes its replayed merge).
   Returns the last action. The existing test keeps every assertion.
3. `ask(day, widget, label)`: the planner's card: `day.hook('PostToolUse',
   tool_name='AskUserQuestion', tool_input={'questions': [widget]}, tool_response={'answers':
   {widget['question']: label}})`, then `bash(day, widget['record'].replace('<label>',
   label))`. Asked before recorded, so `record_gate` sees the answer (#529).
4. `test_posture_day(tmp_path, monkeypatch, choice)`, parametrized `Autonomous`, `Supervised`:
   - `Day(tmp_path / 'workspace', monkeypatch)` (non-solo: `CREVIEW`, reviewers), then
     `prepare(day, skip={'autonomy'})`.
   - Config, edited from the test like `test_shadow_mode_records_force_push_and_keeps_records_refused`
     (string replace after `fast_checks` for repository keys, append for tables):
     `merge_deploys = false` on the repository, `[outbound] channel_classes = {C0CLIENT =
     "client"}`, `[deploy] workflows = ["deploy.yml"]`. Nothing that sets posture, umbrella,
     grants, merge tier or autonomy.
   - Card handler: label `choice` for the `autonomy` widget (read from its options); the
     first option for the `gate` widgets; for a `decision` row the allowing option of a grant
     card (`Allow today`) or the option the widget marks as the recommendation, else its
     first. Each answered card is appended
     to a list `(row state, header, label)`.
   - `after` handler, each step at most once:
     a. First time the item is `fix` or later: write `record(cls='retry', door='unsure',
        radius='item A')`, `record(radius='outside')` and `record(radius='item A',
        wants=LEAD)` as the next free `D-n` under `day.directory / 'decisions'`, run
        `wuwei decision route D-n` through `bash` for each, keep the three outputs.
     b. First `pr` row: ping through `bash` (`wuwei pr ping-check <ref>`, `wuwei pr ping
        <ref>`) unless `channel_posts` already has the ref; if the ping was held, `ask` its
        draft card with `Send now` and ping again. Then the reviewer approves at the head
        and the checks are green in the fake host (`reviews`, `checks`, `protection` with
        `squash: True`, `merge` returning `{accepted: True, sha: head}`, `history`), in the
        shape `tests/test_merge.py` `case` uses. Then the client message:
        `day.hook('PreToolUse', 2, tool_name='mcp__slack__post_message', tool_input={'channel':
        'C0CLIENT', 'text': 'The fix ships today.'})`, its draft id from the reason,
        `ask(day, widget, 'Send now')` with the widget from `wuwei drafts show <id> --widget`,
        then the same payload with expected 0.
     c. After WUWEI's `merge` call shows in `day.host.calls`: flip the host PR to merged and
        run `pr state`, as the existing test does after its replay. Under supervised, then
        the deploy: `day.hook('PreToolUse', 2, tool_name='Bash', tool_input={'command':
        'gh workflow run deploy.yml -R acme/widget'})`, `ask` the card from
        `wuwei decision show D-n --widget` with `Allow once`, the same payload with
        expected 0.
   - Assertions (US1 under `Autonomous`, US2 under `Supervised`):
     - both: `autonomy.mode` in `workspace.load_config(day.root)` equals the choice lowered;
       item `A` is `merged`; exactly one host `merge` call at the gated head; `day.closed` in
       events; every `hook.refusal` reason contains `specify first` or matches `CARD`.
     - autonomous: the answered card rows are `gate` and `calibrate` only, and the
       `calibrate` row held the autonomy widget only;
       `decision_routes` is `{}` (failure message lists each id with its `cisr` or grant
       action); `drafts` has one row whose channel is `C0CLIENT`; the three routes printed
       `mandate`; one `grant.used` with decision `merge.default_tier` and action `merge`, no
       `grant.asked`; `report.md` has `## Taken under mandate` with the Consequential id
       first and each line naming `decisions/D-n.md` and `reverse: bin/wuwei decide D-n`,
       and `## Grants` naming merges.
     - supervised: `grant.asked` events for actions `merge` and `deploy`;
       `decision_routes` holds the Consequential and the Exploratory record with that
       `cisr`; the client draft row exists; the deploy retry exited 0.
     - both under 60 seconds (`time.monotonic`).

### `tests/test_invariants.py` (US3; FR-007 to FR-009)

Extend part B's module; reuse `DIMENSIONS`, `Rules`, `memo`, `walk`, `READS`, `INVARIANTS`,
`BROKEN`, `OWNED`, `EXEMPT`, `test_table_matches_the_checks`.

- `OWNED`: delete the five `#524` rows; the five `#529` rows keep file and substring, note
  `'follow-up, specs/530-posture-day Deferred'`. Its comment stays "Walls a later item removes".
- `EXEMPT`: add the five merge-family rows (`guards/pr.py` with `merge policy`,
  `admin merge`, `PR approval`, `branch protection`, `a shepherd seat never merges`), note
  `'merge family: bin/wuwei merge is the path (#524); approval and override stay the owner's'`.
- `i3`: in the walk, per posture, the `--squash` and `--admin` merges are refused and the
  `--squash` reason names `wuwei merge`. `MERGE` stays imported only if still used.
- New `test_merge_only_at_the_gated_green_head(case, posture, grant, head)` reusing
  `case`, `granted_case`, `merged_calls`, `evidence`, `BASE`, `REF`, `SHA` from
  `tests/test_merge.py`: posture in observe, guarded, strict; grant in none, once, today
  (a seeded `grants` row `{action: merge, target: repo:example/project, answered: <grant>}`
  as `test_planned_pr_card_answered_today` seeds it), standing (`standing_merge`); head in
  gated, moved (gate files at `BASE`), red (`checks` conclusion `failure`). Assert
  `merged_calls(host) == [(REF, SHA)]` exactly when head is gated and grant is once or today,
  or standing below strict; otherwise no merge call and no `grant.used`.
- `Rules.record`: also `bin/wuwei config set cap 2 --from-card D-1` from the planner and a
  seat; `i8` expects it to match `decide` (planner passes exactly when the card was asked and
  the posture is not strict; a seat never passes).
- New `i19` (#526), `READS (0, 1, 5)`: for audience team, client and public, seed
  `outbound_threads = {'C0TEAM/1.2': ['p-<audience>']}` in the day state, classify
  `Tests passed.` to `C0TEAM` with `thread_ts = '1.2'` through the port (mode `adapter`),
  memoized by `('thread', posture, audience, umbrella)`, and remove the seed. Below strict:
  team is `send`; client and public are `draft` with exit 1. Owner and company: `None`.
- New `i20` (#528), `READS ()`, memoized once per `Rules`: `calibrate.host(root, config,
  free=...)` with `os.cpu_count` patched over the grid of spec US3.4 (free values built
  from the floor `host.free_memory_mb` and the `seat_mib` the first call returns, never an
  assumed 1024), config from
  `workspace.load_config(root, raw=...)` with `cap` and `[budget] tokens_per_day`. Expected:
  owner cap 3 gives 3; cap 0 gives 1, 1 and `min(8, cores)` (host fit); a budget never gives
  more than the same case without it.
- New `i21` (#533), `READS (0, 1, 3)`: the `OUTBOUND` config plus `[outward] patterns =
  ["zz-internal"]` (topic none, umbrella send, mode adapter); text `Tests passed zz-internal.`.
  For kind tracker, docs or other: `outward.check_lint` exit 0 and `classify` equal to the
  same text without the word, in every posture. For chat, team or company: `check_lint` exit
  0 below strict and 1 under strict, never held. For chat, client or public, with owner rows that send to `C0CLIENT` and
  `C0PUB` added to that config (so the text without the word sends): `classify` with the
  word is `draft` and its reason names the word. Owner: `None`.
- New `i22` (#557), `READS ()`, memoized: for every class in `cruise.CLASSES` and no class,
  with `undo.ledger` returning no kind and every `undo.REGISTRY` kind, `undo.measured` on
  `{'Class': cls, 'Context': 'repo:example/project'}` returns reason None only when the kind
  is registered and in the ledger, never for `message`; `protect_state.check_file` refuses a
  seat's Write to `.wuwei/memory/rehearsals.json`.
- New `i23` (#556), `READS ()`, memoized: a two-way retry record naming
  `repo:fixture-org/never-seen` saved as `D-60` under the world's decisions directory, with
  `[autonomy] mode = "autonomous"`; `wuwei decision route D-60` prints `owner` first and
  names the key; a seat's Write to `.wuwei/memory/targets.json` is refused.
- New `i24` (#552), `READS ()`: `graph.drift(graph.build(config), config) == []` for the
  `OUTBOUND` config with connector modes.
- `pace_rule` (I15) adds `dispatch.depth({}) == 'standard'` and
  `dispatch.depth({'depth': 'light'}, gate=True) == 'standard'` (#567).
- `INVARIANTS` and `READS` gain I19 to I24; `BROKEN` gains one entry per new row (a
  client thread row that sends, `calibrate.host` returning cap 1, the lint reading tracker
  writes).
- New `test_no_stale_owner_marks()`: every `#(\d+)` in an `OWNED` note and in the I1 row's
  `Owned:` clause of design 9.2 has no `specs/<n zero-padded to 3>-*` under `ROOT`.

### `docs/specs/2026-09-24-wuwei-design.md` (section 9.2)

- I1 notes: "Owned: config and integrity re-confirmation through the card record (the
  follow-up in `specs/530-posture-day`, Deferred). Exempt: the merge family (a session merge
  names `bin/wuwei merge`, #524; approval, `--admin`, branch protection and a shepherd merge
  stay the owner's), the heartbeat probe, ..." (rest unchanged).
- I3: "Checked by: per posture, the `pr` guard refuses a session `gh pr merge` and `--admin`
  naming `bin/wuwei merge`; per posture x grant x head, `merge.execute` merges only at the
  gated, green head with a matching grant". Notes: "#524; a grant lifts only auto-merge
  eligibility and pacing, never a 4.6 precondition".
- I8: "Checked by" adds `bin/wuwei config set cap 2 --from-card D-1`; notes "#529".
- I15 notes add `#567`.
- New rows I19 to I24 after I18, one line each, in the style of I1 to I18 (spec US3.3 to
  US3.8), notes `#526`, `#528`, `#533`, `#557`, `#556`, `#552`.

### `cli/wuwei/guards/__init__.py` (comment only)

- Line 59: "#530: owner-only until #524 makes merging grantable; listed in design 9.2."
  becomes "#530, #524: a session merge goes through bin/wuwei merge; approval and override
  stay the owner's (design 9.2, I1 exempt)." The tuple and its use do not change.

### Production code (FR-010 only)

None planned. A defect a day exposes is fixed at the shared spot only when it is a few lines,
with its failing day step as the test; anything larger goes to Deferred in `spec.md`.

## What must not change

- `tests/fakes/day.py` (no edits); the assertions of `test_the_day_closes_walking_only_next`
  and every test in `tests/test_e2e_day.py`, `tests/test_merge.py`.
- `hook.posture`, `MERGE`, `OWNER_ONLY`, every guard reason text and every grant, merge or
  decision rule (FR-011), except an FR-010 fix.
- Invariants I1, I2, I4 to I7, I9 to I18 and their checks; `DIMENSIONS`; `CASES`.
- Part C's interview rows and keys; #524's merge conditions.

## Risks

- The walk's CPU budget: I19 adds at most 18 classify calls, I21 at most 60 lint and
  classify pairs, I20 one grid of 24 `host` calls. If over 1.0 s, narrow I21 to the kinds
  it distinguishes (chat and one non-chat kind) before anything else.
- The fake host shapes for a WUWEI merge in the `Day` fixture may need more results than
  `tests/test_merge.py` lists (`history`, `files`); the builder copies the keys
  `merge.check` reads, never weakens a merge condition.
- The review ping may not be a `wuwei next` action; the driver runs the same commands
  `test_scripted_day` runs. If `next` never reaches the ping, that is a #551 path gap for
  Deferred, not built here.
