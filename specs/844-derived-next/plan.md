# Implementation Plan: derived next; every ready launch, due duty or one owner decision; state.json becomes a cache

**Branch**: `b8-derived-next` | **Date**: 2026-10-11 | **Spec**: `specs/844-derived-next/spec.md`

**Input**: the spec; the #789 pass plan ("Process control kept", "Batch 8 care", "Outward
duties"); `tests/test_loop.py` (commit b34f15a3); the code at 703b40de; the batch 5 and 6
specs (`specs/837-posture-boolean`, `specs/838-outward-allowlist`,
`specs/839-edges-exact-argv` on their branches) and the batch 7 issues (#840 to #843).

## Summary

Three moves, in this order, each behind its own red tests:

1. **The log is the truth, state.json the cache.** `_write_state` appends a patch with its
   event before it writes the cache; `read_state` folds the patches (FR-001 to FR-003). This
   alone makes the deletion test pass and keeps the 444 fixture writes in the suite working.
2. **The world corrects the log.** `derive.py` reads the worktree HEAD from files, the verdict
   files and the cached PR listing, and overlays them (FR-004, FR-006, FR-013, FR-014). This
   closes #669 and #729.
3. **next returns the set.** `derive.offers` is the one pure decision table; `next.step`
   returns launches, duties and at most one decision; `next.run` resolves the prompts through
   the existing resolvers; duties are configured and recorded; `close` waits on them (FR-005,
   FR-007 to FR-012, FR-015).

## Technical Context

Python 3.11+, stdlib only at runtime; pytest for tests. Run only touched test files locally,
with explicit paths; CI runs the suite. Hook latency budget (#346): `next.step` runs on
SessionStart; the fold parses the day log once per read, and the cache skips it when the log
did not grow.

## Constitution Check

- I stdlib only: yes (no new dependency; the HEAD reader and listing are file reads, the
  refresh uses the existing code-host adapter).
- II three-state exits: `next` keeps CLEAN, FINDINGS, UNRUN; a malformed log row is DAMAGED,
  exit 2, as `brief.events` does today.
- III one behaviour, one function, one test: the decision table is one function with one row
  test each in `tests/test_derive.py`.
- IV test first: every task below starts with a red test; `tests/test_loop.py` is already red
  (strict xfail) for the nine gaps.
- V simplicity: one new module and one small command; the resolvers are reused, not
  rewritten; the phase record is kept and corrected rather than recomputed (spec
  Assumption 2).
- VII security: no guard loosens; the raise check tightens (FR-014); duty sends pass the
  outward allowlist (#838).

## Process control: what each changed unit was

| Unit | Kind | Where its job goes |
|---|---|---|
| `next.step` one row and the `rows` queue without prompts | (a) made the planner walk the day one row at a time and guess the rest | `derive.offers`: every launch with its prompt |
| `next.run` eight-step settle loop, `build next` `done`/`park`, `dispatch next` `escalate`/`parked` reaching the planner | (a) dead ends | resolved inside the derivation; never returned |
| `state.read_state` reading `state.json` as truth; the snapshot refusal | (b) refused a damaged day | the log is the truth; a malformed log row refuses with DAMAGED (exit 2) |
| `_validate` lifecycle checks, `_move`'s `_check_transition` | (b) stopped a writer jumping phases | the decision table never offers an out-of-order step (gate before the builder stops, raise without a pass at head, merge without the policy, fix past the cap); `pr raise --item` and `merge.check` still refuse |
| `next`'s `doctor` row from watch and heartbeat health | (a) made the planner run a health check mid-day | doctor stays a command; part 23 deletes the heartbeat |
| `next`'s `mcp` and `docs` rows | (a) | gone with parts 18 and 19 (dependency) |
| `gate_check` exemption for a gate not re-checked after a fix round | (b) loosened: allowed a raise on an older head | tightened: every gate passes at the current HEAD (FR-014) |
| `dispatch.launch_set` own item walk | (b) CAP and host seats | kept for CAP and `host.seats`; its entries come from `derive.offers` |

No (b) unit is deleted without its job named.

## Modules this part replaces, and what part 23 then deletes

Replaced here (rewritten in place or made redundant):

- `commands/next.py` `step`, `resolve`, `run` (rewritten); `_seen`'s close and merge bits
  move into `derive.offers`.
- `dispatch.launch_set` (rewritten over `derive.offers`).
- `state.read_state`'s file read, the snapshot refusal, `_validate`'s lifecycle checks
  (rewritten).
- `watch.poll_prs` and `merge.poll` as the source of PR state for the loop (replaced by the
  listing; still running until part 23).
- `merge.monitor`'s automatic tracker `done` (replaced by the `tracker` duty).
- `obligations.evaluate` as the close gate for pings and replies (replaced by the `ping` and
  `shepherd` duties; still read by `pr act --reply` until part 23).
- `shepherd.overnight` and the headless loop (replaced by the `shepherd` duty, a normal seat).
- `commands/status.scan`'s watch and heartbeat health as a `next` row (dropped from `next`).

Part 23 then deletes:

- `cli/wuwei/watch.py` except its record helpers (`records`, `_rows`, `_day_rows`, `days`,
  `ERRORS`), and `cli/wuwei/commands/watch.py`;
- `cli/wuwei/heartbeat.py`, `cli/wuwei/commands/heartbeat.py`;
- `cli/wuwei/shepherd.py` lines from `owning_day` to the end (the headless shepherd) and
  `cli/wuwei/commands/shepherd.py`; `plan.propose`'s overnight lines;
- the session registry in `cli/wuwei/sessions.py` (`touch`, `record`, `rows`, `claim`,
  `claim_item`, `export`, `rotation`, `stale_seconds`; the Owner step card API stays) and
  `cli/wuwei/commands/sessions.py`;
- `cli/wuwei/obligations.py` (reply posting moves to `pr_actions`), `cli/wuwei/closing.py`
  (close reads duties and the retro check), the `obligations` and `watch` subcommands of
  `cli/wuwei/commands/sweep.py` (`classes` stays);
- `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS` moves to `commands/why.py`),
  `cli/wuwei/commands/state.py`;
- in `cli/wuwei/state.py`: the cache write, `SNAPSHOT`, `recover`, `STATE_PRODUCERS`,
  `_protected`, `write_state`, `set_state`, `get_state`, `transition`, `_move`, `PHASES`,
  `_check_transition`;
- `cli/wuwei/commands/git_hook.py`, `cli/wuwei/commands/fast_checks.py` (the
  `fast_checks.py` module stays), `cli/wuwei/commands/runtime.py`;
- the state-file branch of `guards/protect_state.py`, `guards/stop.py`, the PreCompact and
  Stop branches of `guards/lifecycle.py`, the PreCompact and Stop entries of
  `hooks/hooks.json`, and the `state recover` hint in `exits.py`.

It keeps the 5.6 metrics report reads.

## Files to create (3)

- `cli/wuwei/derive.py`: `head(path)`, `listing(root)`, `refresh(root, config)`,
  `overlay(data, root, config)`, `offers(data, root, config)`, `duties(data, root, config)`.
  - `head`: `<worktree>/.git` holds `gitdir: <dir>`; `<dir>/HEAD` holds a sha or
    `ref: <name>`; resolve the ref in `<commondir>/<name>` (commondir from `<dir>/commondir`,
    relative to `<dir>`) or in `<commondir>/packed-refs`. Return the 40 or 64 hex sha, or
    None when any link is missing (the worktree is gone). `# ponytail:` reftable not read;
    the vcs adapter's `worktrees` off the hook path is the upgrade.
  - `listing`: `prs.json` in the day directory, `{"fetched_at": iso, "pulls": [{ref, state,
    head, draft, checks, labels, activity_at}]}`; absent reads as empty with age infinite.
  - `refresh`: one `pulls(repo)` call per configured repository through the code-host port;
    writes `prs.json` atomically; on exit 1 or 2 keeps the old file and returns the reason.
  - `overlay`: on the folded data, per approved item: listing merged sets `phase='merged'`,
    `status='done'`; listing closed sets a derived disposition `parked` with reason
    `PR closed on the host`; a recorded worktree whose `head` is None marks
    `worktree_gone=True`; a received verdict whose recorded head is not a prefix of the
    worktree HEAD, or whose file no longer parses to the recorded verdict and Head, is moved
    out of the round's key into `stale_verdicts`; a PARK verdict at head with no
    `plan.resumed` after its receipt sets the derived disposition `parked`. Legacy
    `escalated` reads as `parked`.
  - `offers`: the decision table of the spec, in plan order, pure; returns
    `{launches, duties, decision, rows}` with `{kind, item, command}` per launch and the
    card fields for the decision (from `sessions.owner_card`, which only formats). Precedence
    of the verdict rows copies `dispatch.next_step`. Rounds come from
    `dispatch.rounds_used`; the cap from `dispatch.max_rounds`. CAP from the folded `cap`.
    `depends_on` from `dispatch.candidate`.
  - `duties`: the duty table of the spec over `[duties] on`, the listing and the
    `duty.recorded` events (plus `pr.review_posted` for `ping` and `tracker.call` with
    action `done` and exit 0 for `tracker`, so a duty done through its own command counts).
- `cli/wuwei/commands/duty.py`: `wuwei duty <item|day> <duty> --evidence <text>`; refuses an
  unknown duty or item (exit 1, naming `wuwei next`); appends `duty.recorded {item, duty,
  evidence}`. Registered by the existing command discovery in `__main__.py`.
  Depends on part 20: if #842 lands a duty record command, reuse it and drop this file.
- `tests/test_derive.py`: the HEAD reader (loose ref, packed ref, detached, gone), the
  listing (absent, stale, refresh failure keeps the file), each overlay, one test per row of
  the decision table, one per duty row, purity (no write, no subprocess).

## Files to edit, code (27, plus `guards/pr.py` if part 17 has not landed)

### `cli/wuwei/state.py`

- `_write_state`: compute `patch` against the folded `previous`: changed top-level keys, and
  for `items`, `builds`, `seats`, `gate_verdicts`, `tickets` only the changed entries
  (`{key: {entry: value}}`, a removed entry as `null`). Append the event (with `patch`,
  `prs_seen`, `phase_changes`) first, then write `state.json` with `"log_size"` set to the
  log's byte size after the append. Drop the `SNAPSHOT` write.
- `read_state(root, directory)`: when `state.json` exists and its `log_size` equals the log's
  size, use it; else fold: start from `DAY_DEFAULTS`, apply each event's `patch` in order
  (dict entries merge one level, `null` removes). An old day with no patch in its log and a
  `state.json` uses that file once and appends `state.migrated` with the whole state as its
  patch. Then `derive.overlay`. A malformed row raises `ValueError(... DAMAGED)`.
- `_fold(directory)`: the fold without overlays. `_write_state` bases its update and its
  patch on `_fold`, never on the overlaid view, so a derived fact (merged on the host,
  `stale_verdicts`, a derived park) is never written back into the log; the cache holds the
  raw fold too. Readers get the overlaid view from `read_state`.
- `_validate`: keep the `_defaults` type checks, `cap >= 1`, the status and phase vocabulary,
  and the no-removal checks of items and PRs; drop `_check_transition`, the `resume_phase`
  checks and "new items start at planned".
- `_move`: drop the `_check_transition` call; keep the `fix_rounds` reset at raise and
  `status='done'` at merged.
- `day_started(directory)`: True when the day log holds a patch (or, for an old day,
  `state.json` exists). Replaces every `state.json` existence check below.

### `cli/wuwei/derive.py` (new, above)

### `cli/wuwei/commands/next.py`

- `step(root, ran=())`: keep the day rows before the gate (`no-workspace`, `setup`,
  `session`, `lead`, `wait` for the lead, `propose`, `gate`) without the `pr-flow` and `mcp`
  rows (part 18 deletes `mcp`; the `pr-flow` row was a check the planner had to run, (a),
  `doctor --section pr-flow` stays a command and `plan propose` still measures it). After
  the gate: `derive.offers` plus stuck seats as `stop` launches and seat findings as a `build`
  launch of `plan add --from-finding` (kind `build`, so they never hide work). A non-empty set
  returns `{'state': 'set', ...}`. An empty set falls to the day rows: steward (unchanged
  rule, #617, #624), `wait` (running seats, held items), `close`, `retro`, `promote`,
  `retro-applied`, `report`, `closed`; none of these while a duty is due.
- `resolve(row, root)`: for the set, resolve each launch through its resolver (`build` to
  `build.next_action` or `dispatch._start` commands, `gates` and `fix` (gate) to
  `dispatch.next_step`, `raise` to `_shepherd`, `fix` (PR), `pr` and `merge` to their
  command); a resolver that answers a different kind is skipped this call and named in `why`
  (the derivation will see its record next call). No loop.
- `run`: refresh the listing when stale and an item has a PR (`derive.refresh`); record
  `next.action` once with every named command.
- `THEN['set']`: "Do every launch and every duty now: run each command in order, pass every
  launch and continue to Agent in the background in one message, ask the decision's card with
  AskUserQuestion when there is one; then run wuwei next." `LOOP` says the same in one line.
- Drop `THEN['done']`, `THEN['pr-flow']`, `THEN['mcp']`, `_carry`'s `state.json` check (use
  `state.day_started`), `_record`'s `state.json` check, the `docs` row (part 19), and the
  `status.scan` doctor row. `orientation` keeps its shape; its posture line follows part 15.
- `TERMINAL` stays (`merged`, `parked`, `escalated`) for readers.

### `cli/wuwei/dispatch.py`

- `next_step`: for the round's roles, `missing` includes roles whose record sits in
  `stale_verdicts` (FR-006); after a fix round (`delta`), `rechecks` is true for every gate
  of the set; a passing gate's delta prompt is `_delta_feedback(first, light=True, head)` (the
  light re-read). Keep the cap, PARK, ESCALATE and Blocked: cards as they are (#834). Drop
  the docs exemption call (part 19).
- `receive`: when the round's key holds a record in `stale_verdicts`, accept the new receipt
  and replace it (no "already received").
- `launch_set`: entries from `derive.offers(...)['launches']`, each resolved as today
  (`next_step`, `build.next_action`, `_start`); keep `host()` for `cap` and the free
  `host.seats` and the `cap.derived` record; the gate-waits rule stays.
- `tracker_call`: on `done` with exit 0 also append `duty.recorded {item, duty: tracker}`
  (only when part 20 did not already).

### `cli/wuwei/commands/build.py` (read, not edited)

No change: its records fold; `transition` calls become harmless without the check. Its
`done` and `park` answers no longer reach the planner because `next` does not call it for a
finished or parked build.

### `cli/wuwei/pr_actions.py`

- `act`, `_fix`: at the round cap park the item in code with the cap reason (`plan.park`,
  reason `round cap N reached: PR checks red ...`) and print `plan resume`'s Owner step card
  (exit 1), instead of the `open_fix` ValueError; refresh the listing after any act that
  changes the PR.
- `observe`: an item whose listing row is merged is merged (it already moves the phase; the
  overlay makes it hold without the watch).
- Line 251 existence check: `state.day_started`.

### `cli/wuwei/merge.py`

- `execute`: refresh the listing after a merge or a policy block.
- After part 17: `gate_check` and `_recorded_gates` (moved here from `guards/pr.py`): every
  gate of the set passes at the current HEAD; drop `role in rechecked or not rechecked`.
  Before part 17 lands, the same edit is in `guards/pr.py` (dependency, see Handoff).

### `cli/wuwei/shepherd.py`

- `raise_pr`: refresh the listing after the PR is recorded.
- `post_review_request`: on a post, append `duty.recorded {item, duty: ping, evidence: url}`.
- Line 435 existence check: `state.day_started`.

### `cli/wuwei/closing.py`

- `unresolved`: one finding per due duty from `derive.duties`, naming its record command;
  the merged-item tracker check of `tracker.strict_close` becomes the `tracker` duty (same
  rule, one place).

### `cli/wuwei/commands/close.py`

- Line 57 existence check: `state.day_started`.

### `cli/wuwei/workspace.py`, `templates/workspace/config.toml`

- `SCHEMA['duties'] = {'on': (list, [], ...)}` with the allowed names `ping`, `shepherd`,
  `tracker`, `summary`; a `[duties]` block in the template with a one-line comment per duty.

### `cli/wuwei/commands/init.py`

- `init` and `init --upgrade` write `duties.on` from the configured channels (FR-009) when
  the key is absent, and print `Upgraded config.toml: duties.on = [...]`; `--dry-run` prints
  `Would ...`.

### `cli/wuwei/registry.py`, `adapters/code_host/github.py`, `adapters/code_host/none.py`

- Port `pulls: ('repo',)`. GitHub: one `gh pr list --repo <repo> --state all --limit 100
  --json number,state,headRefOid,isDraft,statusCheckRollup,labels,latestReviews,comments,author`
  call; map checks to `pending`, `red`, `green`, `activity_at` to the newest review or comment
  by a login other than the author. None: `record_none(..., measurement=True)`.

### Existence checks on `state.json` (replace with `state.day_started`)

`cli/wuwei/sessions.py:175`, `cli/wuwei/plan.py:289,408`, `cli/wuwei/metrics.py:559`,
`cli/wuwei/brief.py:171` (`read_day`), `cli/wuwei/obligations.py:190,298`,
`cli/wuwei/verdict.py:310`, `cli/wuwei/tracker.py:44`, `cli/wuwei/watch.py:649`,
`cli/wuwei/report.py:99`, `cli/wuwei/commands/report.py:16`,
`cli/wuwei/guards/agent_launch.py:99,120,361`, `cli/wuwei/guards/stop.py:34`. In
`cli/wuwei/commands/why.py` the evidence path `state.json` (lines 65, 152, 160, 163, 191,
202) becomes `events.jsonl`. `cli/wuwei/heartbeat.py` and the records guard keep naming
`state.json` (a write to it is still refused until part 23).

### Batch 7 dependencies (already gone when this lands; verify at rebase)

- `next.py` `mcp` row and `mcp.widget` on the gate card: part 18.
- `next.py` `docs` row, `dispatch.next_step` `docs.exempt`, `dispatch.receive` docs
  obligation: part 19.
- `tracker.check` walls in `next_step`, `build.next_action`, `agent_launch`: part 20.
- `plan.propose` discovery intake and `rank`: part 21.

## Files to edit, tests

- `tests/test_loop.py` (the characterisation; the rewrite owns `materialise` and `answer`):
  - `materialise`: write no `state.json`. Write the same records through
    `state._write_state(..., reserved=False)` with today's producer kinds: `plan.session`
    (`planner_session_id`), `plan.approved` (items with their fields and `gates` tier record,
    `approved_items`, `gate_approved`, `cap`), `plan.disposed` for a parked plan row,
    `worktree.adopted` (`items[name].worktree = 'trees/<name>'`), `seat launched` and
    `seat stopped` (the seats), `build.started` (the builds with `fix_rounds`),
    `gate.received` (the receipts), `pr.raised` (`items[name].pr`, `raised_prs`). Add the
    worktree world: `trees/<name>/.git` holding `gitdir: <root>/project/.git/worktrees/<name>`
    and that directory's `HEAD` holding `HEAD` padded to 40 hex and `commondir` holding
    `../..`. Write `prs.json` as `{"fetched_at": NOW, "pulls": [{"ref", "state": "merged" if
    merged else "open", "checks": the world's pending, red or green, "labels":
    ["owner-merge"] when owner_merge, "head"}]}`. Duty events unchanged.
  - `configure`: add `[duties]\non = ["ping", "tracker"]`.
  - `answer`: one call to `next_command.step(root)`; a set maps to
    `[(launch['kind'], launch['item']) ...] + [(duty['duty'], duty['item']) ...] +
    [('owner', decision['item'])]`; a day row to `[(row['state'], row.get('item', ''))]`. The
    helpers `gate` and `offer` go; `covered` becomes plain membership (the `pr act` stand-in
    is gone because `fix` and `merge` are their own kinds).
  - Remove the nine `xfail(strict=True)` markers.
  - `test_614`: `step` writes nothing, so resolve the offer with
    `next_command.resolve(next_command.step(root), root)` and assert its `fix` launch is a
    `continue` whose prompt names `gate-quality-item-1.md`; the `THEN['continue']` check
    stays.
  - `test_729_an_owner_merge_row_ends_when_the_pr_merges`: the first answer is
    `[('owner', 'item-1')]` (spec Assumption 5); the rest is unchanged.
  - `test_666`: unchanged (`rows` lists `verdicts` then `pr`).
- `tests/test_next.py` (45 tests): rows after the gate move to the set shape; tests of the
  `pr-flow`, `mcp`, `docs` and `doctor` rows go with the rows; tests of the settle loop go.
- `tests/test_dispatch.py`: `launch_set` over offers; stale receipt replaced; every gate
  re-checks after a fix round (the delta-only tests change their expectation: stricter).
- `tests/test_state.py`: patch on write, fold, cache hit and miss, deletion, migration of an
  old day, malformed row is DAMAGED; the illegal-transition tests go with the check, and the
  snapshot-refusal test goes with the refusal.
- `tests/test_pr_guards.py` or `tests/test_merge.py` (after part 17): raise refused when a
  passing gate's Head is older than HEAD.
- `tests/test_close_branches.py`: an open duty is a close finding.
- `tests/test_config_transition.py`, `tests/test_workspace.py`: `duties.on` default and
  upgrade line.
- `tests/test_pr_actions.py`: the cap park on red checks; refresh after act.
- `tests/test_shepherd.py`: ping records the duty.
- Fixtures that write `state.json` directly switch to `state._write_state` (same data):
  `tests/test_agent_launch.py`, `tests/test_adapters.py`, `tests/test_build.py`,
  `tests/test_brief.py`, `tests/test_headless_e2e.py`, `tests/test_hooks.py`,
  `tests/test_plan.py`, `tests/test_protect_state.py`, `tests/test_memory.py`,
  `tests/test_next.py`, `tests/test_why.py`, `tests/test_outward.py`,
  `tests/test_pr_guards.py`, `tests/test_sessions.py`, `tests/test_signal_status.py`,
  `tests/test_spec_mode.py`, `tests/test_stop.py`, `tests/test_telemetry.py`,
  `tests/test_tracker.py`, `tests/test_workspace.py`.
- Readers of `next` output: `tests/test_parallel_dispatch.py`, `tests/test_path_day.py`,
  `tests/test_e2e_day.py` (the scripted day; it must pass before this ships),
  `tests/test_handback.py`, `tests/test_sessions.py`, `tests/test_posture.py`,
  `tests/test_metrics.py`, `tests/test_shell.py`.
- `tests/test_reasons.py`, `tests/test_tone.py`: run; no new owner text sends anyone to a
  terminal.

## Files to edit, governance and docs (8, plus the generated agents)

- `docs/specs/2026-09-24-wuwei-design.md` 5.2 (the loop returns the set; duties), 5.3
  (strict pass at head; a passing gate re-reads after a fix round; at the cap and on red
  checks at the cap the owner decides on one card), and the state passages that call
  `state.json` the truth: marked (owner, 2026-10-11, #789 part 22).
- `charters/planner.md` lines 6 and 18; then `bin/wuwei agents build` (never edit
  `agents/*.md` by hand).
- `charters/shepherd.md`: the shepherd duty seat replies to every open thread and records the
  duty.
- `skills/wuwei-plan/SKILL.md` line 8, `skills/wuwei-report/SKILL.md` line 8: "do every
  launch and duty it returns, ask its decision".
- `docs/site/configuration.md`: `[duties]` (forced by `test_every_template_config_key_is_documented`).
- `docs/site/reference.md`: the `duty` command (forced by
  `test_reference_lists_every_cli_command`).
- `CHANGELOG.md` is release-please's; no edit.

## RETIRED

None. The base has `workspace.RETIRED` (#799); this part retires no key.

## Handoff

- Rebase onto batches 5 to 7. Check: `guards/pr.py` gone and `gate_check` in `merge.py`
  (part 17; else apply FR-014 in `guards/pr.py`); no `mcp`, `docs`, discovery or `rank`
  references left in the files above (parts 18, 19, 21); part 20's tracker duty and its
  record (reuse it; FR-010 then adds only `ping`, `shepherd`, `summary`); `outward.allow`
  (part 16) governs the duty sends, so the duty prompts name the configured tool, never a
  workaround.
- Two independent fresh reviews (Batch 8 care): one general, one only trying to break the
  fold and the overlays (event order, a lost cache write, a torn last line, two writers, an
  old day, a listing older than the records).
- Ship alone after `tests/test_e2e_day.py` (the scripted day) passes.

## Risks

- **Fixture churn.** 20 test files seed `state.json` by hand; each switches to the writer.
  The phase they seed stays (the record is kept), so assertions should hold.
- **Event log size.** Patches grow `events.jsonl`; `items` entries are written whole per
  change. The cache avoids the fold on most reads; measure the SessionStart path against the
  #346 budget in `tests/test_hooks.py` latency cases.
- **Redaction.** `_append_jsonl` redacts known secret values in every row; a secret inside a
  recorded value would fold back redacted. No state key should hold one; the fold test adds a
  case with a configured secret value to prove none does.
- **Two decision tables.** `derive.offers` and `dispatch.next_step` must agree on precedence;
  `resolve` names a disagreement instead of looping, and one test per verdict row runs both.
- **HEAD reader.** Reftable repositories read as no HEAD (named in `why`); linked worktrees
  only (the main checkout is never an item worktree).
- **Listing lag.** Between a host change and the next refresh (up to `pr.poll_seconds`) the
  records rule; WUWEI's own raise, act and merge refresh at once.
