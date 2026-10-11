# Implementation Plan: delete pace; the tier alone sets the process depth

**Branch**: `811-pace-out` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at main 221f1f2 (the worktree base). Verify each against the code before
editing; neighbouring pass parts touch the same files.

## Summary

Delete the pace module and command, the pace rows on the gate card, the pace adjustment in
`dispatch.tier`, the pace seat rule in `dispatch.launch_set`, the pace check list in
`fast_checks.commands`, the per-pace metric, report, retro and steward card, the config keys
`pace.default` and `repos.tests`, and every doc, charter and design spec passage that
describes them. What stays deterministic in code, unchanged:

- Tier: `dispatch.tier` from the diff (lines, trust, never-auto, FULL-pattern and binary
  paths), the FULL track, the lead flags, the repository floor, the docs-only rule and the
  lead tier. With pace gone the pace block at `dispatch.py:131-143` is removed and nothing
  else in the function changes.
- Depth: `dispatch.depth` returns the recorded tier (nothing writes `gates.depth` any more).
- CAP: `calibrate.host` (owner `cap`, `host.seats`, the memory rule, `budget.tokens_per_day`).
  `launch_set` uses `limits['cap']` and `limits['bound']` as given; the pace seat rule and
  the load hold go.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. No new module, key, event or file. Net deletion.
Run only touched test files: `python3 -m pytest -q <files>` from the repository root. CI runs
the suite.

## Constitution Check

- I stdlib only: nothing added.
- II exits: unchanged; no guard gains or loses an exit path except the planner allowance in
  `protect_state` for `plan set pace=<p>`, which goes with the command form (the allowance
  narrows to `_planner_ticket`).
- III one behaviour, one function: tier stays in `dispatch.tier`, CAP in `calibrate.host`,
  checks in `repos.<n>.fast_checks` read where they were read.
- IV test first: tasks.md puts a failing test before each behaviour change; pure deletions
  delete their tests with the code.
- V ponytail: `fast_checks.commands` collapses to the config list, so the function goes and
  its four callers read `repo['fast_checks']`.
- VII / Workflow invariant rule: the I15, I16 and I17 rows and their walk checks are removed
  with the rule they guard. Their two real checks stay covered: a pending required check is
  never green (`tests/test_merge.py::test_required_check_must_be_green`, conclusion `None`),
  and an untiered item and a gate reader run standard
  (`tests/test_process_depth.py::test_depth_reads_the_gate_tier_then_the_builder_prediction`).
- Design spec ownership: edits to the design spec are part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `pace.advise`, `pace.host_line`, `_last_suite`, `predict`, `_depth`, `_guard`, `FALLBACK_MINUTES` (advice on the gate) | (a) the planner and owner reason about how hard to push | nowhere |
| `pace.label`, gate rows `Approve at <pace>`, `plan approve --pace` | (a) an owner process choice on the gate card | the gate keeps `Approve` and `Change something` |
| `pace.current`, `plan set pace=<p>`, `plan.set_pace`, `pace.set` event, protect_state `_planner_pace_set` | (a) a mid-day process knob the planner turns | nowhere; the guard allowance narrows |
| `pace.adjust` (careful lifts light, fast lightens depth, guard code to full) | (a) a second tier input chosen per day | `dispatch.tier` alone; at steady (the default) it was a no-op, so the default tier is unchanged |
| `pace.seats` (careful CAP minus one, fast load hold) | (a) a second seat input chosen per day | `calibrate.host` CAP, used as given by `launch_set` |
| `fast_checks.commands` pace branches, `brief.checks_line`, `repos.tests` | (a) which local checks run depends on the day | `repos.<n>.fast_checks`; CI runs the suite |
| `commit_push.fast_evidence` | (b) push only after the fast checks pass at HEAD | kept; reads `repo['fast_checks']` |
| `metrics.by_pace`, `report.pace_lines`, `report.costly`, retro `## Pace`, `pace.propose_default`, `pace_card` | (a) comparing paces and proposing a default | nowhere; cycle time per tier (`## Cycle time`) and DORA stay |
| `calibrate.host` `load`, `per_seat_tokens`, `used_tokens` | (a) inputs only the advice and the fast hold read | the budget bound on CAP stays inside `calibrate.host` |
| `dispatch.depth` read of `gates.depth` | (a) only pace fast wrote it | the recorded tier |
| status line `pace <p>` and `held by load` tokens | (a) | nowhere |
| I15 `pace_rule`, I16, I17 `green_rule` walk checks | test of (a); I17's `merge.green` part is (b) | `test_merge.py::test_required_check_must_be_green` and `test_process_depth.py` already cover the (b) parts |

No (b) check is lost.

## Files to delete (3)

- `cli/wuwei/pace.py`
- `cli/wuwei/commands/pace.py`
- `tests/test_pace.py` (tests only pace; it imports fixtures from other test files and is
  imported by none)

## Files to edit, code (22)

### `cli/wuwei/dispatch.py`

- `tier` (`131-143`): delete the `from wuwei import pace` block: the `guard` computation via
  `step_zero` (used only for pace), the `pace.current` read, `flagged`, and the
  `pace.adjust` call with `reasons += more`. Delete `if lighter != effective:
  record['depth'] = lighter` (`148-149`).
- `depth` (`171-175`): docstring drops "(#579, the pace)"; return
  `gates.get('tier') or (None if gate else row.get('depth')) or 'standard'`.
- `launch_set` (`436-437`): replace the pace import and `pace.seats` call with
  `cap, bound = limits['cap'], limits['bound']`. In `add` (`459-460`) delete the
  `if launches and hold:` branch so the chain starts at `if launches > free:`.

### `cli/wuwei/calibrate.py`

- `host` (`546-574`): `budget, costs = ..., {}` becomes `budget = ...`; drop both `costs = `
  assignments (`558`, `561`); drop the `getloadavg` block (`569-572`); the return drops
  `'load': load, **costs`. The budget bound on CAP and its text stay.

### `cli/wuwei/fast_checks.py`

- Delete `commands` (`35-56`). In `record` (`86`) iterate `repo['fast_checks']`. Drop the
  `shlex` import only if nothing else uses it (line 91 does: keep).

### `cli/wuwei/brief.py`

- Delete `checks_line` (`55-64`).
- Builder block (`500-514`): import only `fast_checks`; delete the `current, tests =` line and
  the `#600 fast pace` comment; the none-configured test becomes
  `if not repo.get('fast_checks'):`; delete the `elif line := checks_line(...)` branch.

### `cli/wuwei/commands/build.py`

- `start` (`170-171`): delete the `fast_checks` import line; `commands = list(repo['fast_checks'])`.
- `check` (`432-435`): comment becomes `# complete on the configured fast checks`;
  `commands = repo['fast_checks'] if repo else record['commands']`. The `fast_checks` import
  stays (`fast_checks.record`).

### `cli/wuwei/guards/commit_push.py`

- `fast_evidence` (`183-184`): import nothing; iterate `repo['fast_checks']`.

### `cli/wuwei/plan.py`

- `propose`: delete `268-270` (advice), `278` (`pace.propose_default`), and the
  `Pace: ... (recommended)` line plus `*data['pace_reasoning']` in the gate proposal block
  (`312`; keep the trailing `''`).
- `gate_widget` (`346-360`): delete the pace import, `advised` and `paces`; options become
  `[('Approve', approves + '.'), ('Change something', ...)]`; the record drops the `--pace`
  part.
- `approve`: drop the `pace_label=None` parameter, `382-385`, `pace=chosen` in the state
  update (`459`) and `'pace', 'recommended', 'wish'` from the `plan.approved` payload (`466`).
- Delete `set_pace` (`634-646`).

### `cli/wuwei/commands/plan.py`

- Delete `approve.add_argument('--pace', ...)` (`28`).
- `set` parser (`42-47`): help drops "or the day: pace=<p>"; `item` help is "The item id";
  `assignment` loses `nargs='?'` (required).
- Delete the `set ... pace=` branch (`83-84`); the error text (`99`) drops
  ", or bin/wuwei plan set pace=careful|steady|fast"; `approve` call (`106`) drops
  `pace_label=args.pace`.

### `cli/wuwei/guards/protect_state.py`

- Delete `_planner_pace_set` (`183-186`). At `314-317` the comment keeps only the #636 line
  and the test reads `(not xargs and _planner_ticket(action) and edits[1] and not _strict(cwd))`.
  Pass part 3 may delete this whole owner-verb block first; then nothing remains here.

### Small reference removals

- `cli/wuwei/state.py:279`: delete the `'pace'` and `'pace_card'` producer entries.
- `cli/wuwei/signal.py:32`: drop `'pace.set', 'pace.carded'` from `SILENT`.
- `cli/wuwei/commands/event.py:88`: delete the `pace.set` and `pace.carded` producer entries.
- `cli/wuwei/commands/status.py`: `snapshot` drops `'pace': data.get('pace')` (`321`);
  `_groups` drops the pace token (`475-476`) and the `held by load` token (`477-478`; only the
  pace seat rule set bound `load`).
- `cli/wuwei/metrics.py`: `cycles` drops `paces`, `fresh` and the `#579` lines (`422`, `425`,
  `443-444`) and the `'pace'` row field (`446`); delete `by_pace` (`463-479`); drop
  `event_metrics['by_pace']` (`850`).
- `cli/wuwei/report.py`: delete `costly` and `pace_lines` (`121-142`) and the
  `## Pace` line (`196`); drop the `json` import only if unused afterwards.
- `cli/wuwei/retro.py:106-109`: import only `report`; delete the `card` line and the
  `## Pace` block.
- `cli/wuwei/workspace.py`: delete `"tests": (str, "")` from `repos` (`72`) and the `"pace"`
  table (`98`).
- `cli/wuwei/commands/setup.py:163-164`: the `_choice` docstring example becomes
  `(prioritisation.framework = rice)`.
- `cli/wuwei/commands/next.py:57`: drop " (the pace, #579)".
- `cli/wuwei/commands/__init__.py:7`: drop `'pace'` from `READ_ONLY`.
- `cli/wuwei/__main__.py:32`: drop `pace` from the owner group.
- `cli/wuwei/budget_classes.py:59`: "the window's pace" becomes "the window's rate".

## Files to edit, charters and agents (2)

- `charters/lead.md:13`: "List the files it will touch as `paths` (repository-relative
  strings); the pace advice reads them for guard code." becomes "... (repository-relative
  strings)."
- `agents/lead.md`: regenerated with `bin/wuwei agents build`, never by hand.

## Files to edit, docs (6)

- `docs/site/concepts.md`: delete `### Pace` (`52-56`); `393` drop "or pace careful" from the
  list that keeps three gates; `451` "the window's pace" becomes "the window's rate".
- `docs/site/daily.md:207-224`: the record command loses `--pace "<label>"`; delete the pace
  paragraphs and the example block (`210-224`).
- `docs/site/reference.md`: delete the `bin/wuwei pace` row (`54`) and the
  `plan set pace=` row (`56`); `100` the `paths` sentence becomes "An optional `paths`, a
  list of repository-relative file paths, lets the CLI name the item's repository when it
  exists in exactly one."
- `docs/site/configuration.md`: `12` drop `[pace]`; delete the `repos.tests` row (`70`) and
  the `pace.default` row (`136`); `365` drop ", careful pace still runs `repos.tests`".
- `docs/site/agent.md:56`: drop `pace,` from the read-only list.
- `docs/specs/2026-09-24-wuwei-design.md`: replace the Pace paragraph and table (`521-542`)
  with "Process depth (owner, 2026-10-11, #811): the tier alone sets it (#280, #567) and CAP
  alone sets the seats (#528); no day value adjusts either."; delete the per-pace bullet in
  5.6 (`704-708`); delete 9.2 rows I15, I16, I17 (`2031-2033`); in row I43 (`2060`) replace
  "(I15)" with "(`dispatch.tier` raises a flagged item to standard)".

## Files to edit, tests (14)

- `tests/test_dispatch.py`: new test (stale `pace: fast` leaves the tier record unchanged and
  without `depth`).
- `tests/test_parallel_dispatch.py`: new tests (stale `pace: careful` keeps CAP; stale
  `pace: fast` on a saturated load average holds nothing; status line shows no pace token).
- `tests/test_process_depth.py`: one assertion that `gates.depth` is not read.
- `tests/test_plan.py`: gate widget options and record (`156`, `395`, `420`, `440`, `445`,
  `448`); delete the pace tests at `938-1003` except `test_candidate_paths_are_validated`
  (drop the `# #579` header comment); add `--pace` and `plan set pace=fast` refusals and
  `wuwei pace` invalid choice; assert the proposal and plan carry no pace.
- `tests/test_build_next.py:523-534`: delete
  `test_empty_fast_checks_at_careful_pace_still_run_the_tests`; add the stale-careful case
  to the none-configured test.
- `tests/test_brief.py:623-640`: parametrize on `checks,none` only (`'[]'` none, `'["make test"]'`
  not); assert no `Checks:` line.
- `tests/test_commit_push.py:906-912`: drop the pace parametrization and state write.
- `tests/test_calibrate.py:1373-1380`: import without `pace`; assert
  `(limits['cap'], limits['bound']) == (6, 'host.seats')` and `'load' not in limits`.
- `tests/test_signal_status.py:387`: drop the two pace kinds.
- `tests/test_workspace.py:225`: drop `'pace': {'default': 'steady'}`; add the unknown-key
  warning case for `[pace]` and `repos.tests`.
- `tests/test_docs.py:26`: drop `('Pace', r'paces?')` from `GLOSSARY`.
- `tests/test_invariants.py`: delete `pace_rule`, `i15`, `i16`, `green_rule`, `i17`
  (`543-619`), their `INVARIANTS` and `READS` entries (`1504`, `1534`) and
  `test_a_pace_that_lowers_a_tier_is_caught` (`1682-1690`). Drop imports that become unused.
  If pass part 1 has already deleted the walk, skip this file.
- `tests/test_report_retro.py`: `47-49` (the retro text) assert `## Tickets seats filed` <
  DORA < `## Gate verdicts` and `'## Pace' not in text`; `318` drop `'## Pace'`; `332` assert DORA follows `## Cycle time` and
  `'## Pace' not in full`.

## RETIRED at rebase

The base has no `workspace.RETIRED` (#799 not merged). The lead adds after #799 merges:

- `pace` (the table; it holds `pace.default`)
- `repos.tests` (a key inside each `[[repos]]` entry; check that #799's removal handles a key
  in an array of tables, else the generic unknown-key removal of pass part 2 covers it)

## Risks for the builder

- Strict workspaces: until #799 or pass part 2 lands, a config that still holds `[pace]` or
  `repos.tests` raises on load under strict (`workspace.py:812-815`). Merge after one of them,
  or say so in the PR.
- Shared files with parts 3, 4, 5, 7 (parallel builds): `commands/__init__.py`,
  `__main__.py`, `protect_state.py`, `status.py`, `signal.py`, `event.py`, `state.py`,
  `workspace.py`, `docs/site/*`. Rebase carefully; keep each other's deletions.
- `tests/test_invariants.py` and the 9.2 table: pass part 1 deletes them wholesale; if it
  merged first, do only the 5.2 and 5.6 design spec edits.
- Do not add a pace string to `signal.SILENT` to silence old events (spec Assumption 5).
