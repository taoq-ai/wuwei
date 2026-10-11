# Implementation Plan: delete the telemetry proposals; telemetry and DORA stay

**Branch**: `809-telemetry-proposals-out` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

## Summary

Delete the five proposal rules, the `evidence` they read, the `telemetry proposals` action and
its card, the `presented` mark and event, and the `telemetry` row of `wuwei next`. Keep the
aggregate, every metric (DORA included), week files, preview, off, send, anonymous sharing and
the OpenTelemetry export. No file is deleted; 18 files change (7 code, 6 tests, 5 docs), of
which 4 are skipped if parts 3 to 5 already removed them. Every change deletes lines except
one new test.

Line numbers are at main `221f1f2`; verify each against the rebased tree (parts 3, 4 and 5
merge first).

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, event kind, state key or config
key. The watch sweep does slightly less work (no rule pass, no external-wait loop branch).

## Constitution Check

- I stdlib only: nothing imported.
- II exits: no exit changes; `telemetry proposals` now fails in argparse (exit 2), as any
  unknown action does.
- III one behaviour, one function: unchanged; `aggregate` stays the one producer of a week.
- IV test first: tasks change each behaviour test before its code (US1, US3); the proposal
  rule tests go with the rules.
- V ponytail: deletion only.
- VII security: the payload keys and `validate` do not change; legacy keys in a stored week
  never reach a payload because `payload` picks `KEYS` only.
- Design spec rule: #789 is the owner's instruction (owner, 2026-10-11), so 5.13 is amended
  to match, each edited passage marked. Workflow 9.2 invariant rule: no guard or decision
  rule changes.

## Units removed and why (rule of the pass)

| Unit | (a) or (b) | Where its job is now |
|---|---|---|
| `telemetry.proposals` (five rules: floor-raise, floor-lower, area-block, wait-hours, fast-checks) | (a) turns counts into process-tuning questions for the model to carry to the owner | none; the owner reads `metrics --week` or the OTLP export and runs `config set` when they choose |
| `evidence` in the aggregate (`verdict_items`, `external_wait_hours`) and the external-wait branch | (a) inputs only the rules read | none |
| `proposals` key in a final week (`week_file`) | (a) | none |
| `wuwei telemetry proposals [--widget]`, `_proposals` | (a) a card the planner asks about process | none |
| `presented` mark and `telemetry.presented` event | (a) once-only bookkeeping for that card | none |
| `next` row `telemetry` | (a) makes the loop offer a process card | none; `next` goes from calibrate to the rehearse/decision/build rows |
| guide widget entry, `WRITES` entry (if present) | (a) | none |

No (b) unit: no proposal stops a process error. Seat without a brief, gate head, verdict
format, round budget, raise and merge policy are untouched.

## RETIRED at rebase

None. Proposals have no config key; every `[telemetry]` key stays. Nothing to add to
`workspace.RETIRED` (absent on this base, added by #799).

## Files to delete

None.

## Files to edit

### Code

1. `cli/wuwei/telemetry.py`
   - 1-2 module docstring: drop "its proposals," ("the weekly aggregate off the hook path,
     the shared payload and the owner's OpenTelemetry export").
   - 101 `aggregate` docstring: "Every 5.13 metric of one week." (drop the evidence clause).
   - 179-190: `routed, waits = {}, []`; delete `zone = workspace.zone(config)`; store
     `routed[payload['id']] = _time(row['ts'])`; `at = routed.pop(payload['id'])`; delete the
     `outside`/`external` lines. `owner_wait_hours` is unchanged. `decision` stays imported
     (`naming`, `answered`); `workspace` stays (`posture`).
   - 218-219: delete the `'evidence': {...}` entry of the returned dict.
   - 263-275 `week_file`: docstring "Compute one week: final before the current week; keeps
     shared, ready and otlp."; delete the `if found['final']: found['proposals'] = ...` lines;
     carry tuple `('shared', 'ready', 'otlp')`.
   - 289-325: delete `proposals`.
   - 329 `payload` docstring: "never final or marks" (drop evidence and proposals; a legacy
     file may still hold them and they are still excluded).
   - Keep `latest_final` (285-286): preview and send read it.
2. `cli/wuwei/commands/telemetry.py`
   - 1 docstring: "preview what leaves, turn sharing off, send an attributed week."
   - 13 help: `'weekly usage counts: preview, off, send'`.
   - 20-21: delete the `proposals` parser and `--widget`.
   - 29: drop `'proposals': _proposals` from the action map.
   - 107-125: delete `_proposals`. `json` stays (preview).
3. `cli/wuwei/commands/next.py` 211-213: delete the `telemetry` row.
4. `cli/wuwei/signal.py` 29: drop `'telemetry.presented'` from `SILENT`.
5. `cli/wuwei/commands/event.py` 94: drop `'presented'` from the telemetry tuple.
6. `cli/wuwei/guide.py` 17 (skip if part 3 deleted the file): drop
   `'telemetry proposals --widget'` from `WIDGETS`.
7. `cli/wuwei/commands/__init__.py` 31 (skip if part 3 deleted `WRITES`): drop
   `'telemetry proposals'`.

### Tests

8. `tests/test_telemetry.py`
   - 1 docstring: drop "proposals".
   - 112: replace the `evidence` assertion with `assert 'evidence' not in found`.
   - 152-167 `test_week_file_writes_final_weeks_with_proposals_and_keeps_marks`: rename
     `test_week_file_writes_final_weeks_and_keeps_marks`; seeded previous file keeps
     `'presented': True` as a legacy key; assert `'proposals' not in final`, the kept marks
     `(final['shared'], final['ready']) == ('anonymous', True)` and `'presented' not in final`.
   - 250-256 `week()`, 259 `REPO` (read only by the two proposal tests), 262-297 `test_three_proposal_fixtures` and
     `test_each_rule_at_and_below_its_threshold`: delete.
   - 300-307 `final_week`: build the dict inline (`week`, `final: True`, `schema`,
     `versions`, `config`, `metrics` with `days`, `warnings`, `escaped_by_tier`,
     `fix_rounds_per_item`), no `evidence`, no `proposals`.
   - 310-325 `test_proposals_command_lists_then_presents_once`: replace with
     `test_a_stored_week_with_proposals_still_loads` (US1 scenario 2, US3): save a final week
     with legacy `proposals`, `evidence`, `presented`; `load_week` returns it;
     `validate(payload(found, token='a' * 32))` passes and holds none of the legacy keys;
     `main(['telemetry', 'preview'])` exits 0 and its output has no `proposals`;
     `main(['telemetry', 'proposals'])` raises `SystemExit` with code 2.
9. `tests/test_next.py`
   - 55: `seen(root, 'calibrate')`.
   - 197-205: replace the telemetry comment and `('telemetry', 'pass') in ...` with
     `assert 'telemetry' not in {row['state'] for row in passed}` over every `next.action`
     payload (all of them, not only passes), keeping the decision assertions.
   - 812 comment: "the list is []: the row passes in the same call".
10. `tests/test_signal_status.py` 879: `TELEMETRY = ('skipped', 'unsent', 'shared', 'ready',
    'off')`; 884 comment "all five". The tier names follow part 4 at rebase.
11. `tests/test_handback.py` 269: `for name in ('calibrate',):` or a single append.
12. `tests/test_parallel_dispatch.py` 87: `while step['state'] == 'calibrate':`.
13. `tests/test_docs.py` 1410-1412 (skip if part 3 removed them): drop the guide import and
    the `telemetry proposals --widget` assertion; keep the security, reference, concepts and
    configuration checks.

### Docs

14. `docs/site/reference.md` 76: drop "; `proposals [--widget]` lists or presents a final
    week's proposals once".
15. `docs/site/configuration.md` 220: drop "A finalised week can propose a config change,
    asked once at the next morning gate; nothing applies on its own."; 224: "`false` stops
    the aggregate, sharing and the OpenTelemetry export."
16. `docs/site/agent.md` 71 (skip if part 3 removed the generated block): drop
    "`wuwei telemetry proposals --widget`, " so the block equals `guide.text()`.
17. `docs/specs/2026-09-24-wuwei-design.md` 5.13, each edit marked "(owner, 2026-10-11, #789)":
    1225-1227 two layers ("the signals the CLI already records and a weekly aggregate computed
    off the hook path"); 1230 drop "the proposals,"; 1279 drop ", with its proposals";
    1325-1342 replace the Proposals paragraph, rule table and the presentation paragraph with
    one line: "Proposals: deleted (owner, 2026-10-11, #789); nothing is derived from a week.";
    1349 "never anything else in the file"; 1384 "the aggregate continues while `enabled`".
18. `.specify/memory/constitution.md` 69-71: delete "What it derives is a proposal the owner
    applies, never applied on its own (design 5.13)."; bump the version one patch above the
    rebased value and set Last Amended 2026-10-11 (the lead adds the dated amendment line to
    the commit message).

### Searched, no change

Charters, skills, `agents/`, `hooks/`, `templates/` (config template has no proposal text),
`.github/workflows` (`telemetry-label.yml` serves `send`, kept), `scripts/telemetry-worker`
(validates the payload only), `scripts/headless_e2e.py`, `evals/`, README, `docs/site`
security, concepts and daily pages, `cli/wuwei/commands/board.py` and `dashboard.py` (part 5
deletes them; neither reads proposals). Historical specs under `specs/` stay. CHANGELOG is
generated.

## Risks

- Rebase order: parts 3 (#800), 4 (#801) and 5 (#808) merge first. Items 6, 7, 13 and 16
  vanish if part 3 landed; item 10's tier for `ready` may read `warn` after part 4.
- `latest_final` must stay: deleting it with `_proposals` breaks preview and send.
- `tests/test_dora.py` imports `write_day` from `tests/test_telemetry.py`: keep that helper.
- `tests/test_hooks.py` pins the hook-path import set; `next.py` imports nothing new.
