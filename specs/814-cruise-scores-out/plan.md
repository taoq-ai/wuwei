# Implementation Plan: delete cruise, calibration scores, budget classes and the shadow report

**Branch**: `b3-decision-framework` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at main ac5403f (the batch base). Batches 1 and 2 (#798 to #801, #808 to
#811) land first and the lead rebases. An edit marked "skip if already gone" touches code
those batches delete: do it only if the code is still there. This is part 9, the first part
of batch 3. Parts 10 (#815) and 11 (#816) are built after it on the same branch.

## Summary

Delete these modules and their command surface:

- cruise mode;
- the error budget per class;
- the Brier calibration;
- the shadow promotion;
- `wuwei shadow report`.

What stays deterministic in code:

- **Routing**: `decision route` (`commands/decision.py::decide`, `mandate`) decides from the
  door, blast radius, CISR class (`decision.cisr`, no `ambiguous` input) and
  `autonomy.mode`. Owner routes come back from `wuwei next` as `Decision D-n waits for your
  answer` (`commands/next.py:223-231`), unchanged.
- **Mandate text**: `brief.mandate` gets a fixed rule from `autonomy.mode` with the same
  output as today's defaults.
- **Class list**: `decision.CLASSES` becomes a plain tuple of the fourteen names.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. No new module, key, event or file. Net deletion.
Run only the touched test files: `python3 -m pytest -q <files>` from the repository root. CI
runs the suite.

## Constitution Check

- I stdlib: nothing added.
- II exits: `wuwei cruise` and `wuwei shadow` go whole. No guard gains or loses an exit path.
  The profile refusal rows for `decisions.cruise.*` go with the keys. A profile carrying them
  now fails on an unknown key instead.
- III one behaviour, one function: routing stays in `commands/decision.py::decide` and
  `mandate`. The mandate text stays in `brief.mandate`.
- IV test first: tasks.md puts a failing test before each behaviour change (stale
  `cruise.json` ignored, fixed mandate text, no cruise fields on a taken record). Pure
  deletions delete their tests with the code.
- V ponytail: the class table becomes a tuple, and `brief.mandate` becomes two constants.
- VII and the Workflow invariant rule: rows I11 to I14 of the 9.2 table and their walk checks
  go with the rules they guard. If #798 already replaced the table and the walk, there is
  nothing to do.
- Design spec ownership: the edits are part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Class levels L0 to L3, `cruise.level`, `running`, `memory/cruise.json`, kill switch, status `cruise` token | (a) the owner and seats reason about how much a class may do alone | `autonomy.mode` and the CISR class in `decision route`, as today |
| `cruise.rule` (rule, level, `undo_until`, items on a taken record), `Decided-by: cruise <class>@L<n>` | (a) it decorated records the mandate already took; it never gated the mandate | nowhere; the mandate writes `Decided-by: mandate` |
| `cruise.thin` and the route `thin` field | (a) nothing reads it | nowhere |
| Raise and weekly-sample cards (`cruise.propose`, `gate_widgets`, `_card`, `answered`, `cruise_cards`) | (a) gate cards about the process | nowhere |
| Error budget (`budget_classes.py`, `cruise.burn`, budget hold and restore) | (a) a score the steward reads to move levels | nowhere |
| Calibration (`calibration_scores.py`, `decision.uncalibrated`, `cisr(ambiguous=)`) | (a) a score that bends routing toward the owner | nowhere; a role's records route by their own fields, as before #559 |
| Shadow promotion (`cruise.shadow`, `review_shadows`, `decision_shadows`, `decision.shadow`) | (a) | nowhere |
| `promotion.cruise_level`, `calibration`, `cruise_shadow`, `_cruise_write` | (a) the writers of the above | nowhere |
| `brief.mandate` lists from levels | (a) the input goes; the text is a kept rule | fixed lists from `autonomy.mode` (same default output) |
| Profile refusals for `decisions.cruise.*` (`profiles.py:29-32`) | (b) a profile could not widen cruise | moot: an unknown key never widens anything |
| `wuwei shadow report` | (a) a reading aid for the observe trial | the day report `## Shadow` (`report.shadow_lines`, kept) |
| `cruise.window` and the window check in `decision undo` | (a) | the owner's `wuwei undo D-n` / `decision undo` stays without a window until part 10 deletes it |
| The digest and listener `rule` texts (`watch.py`, `listen.py`) | (a) | the digest lists `- D-n: option` |
| Design 9.2 rows I11 to I14 and I16's level part | tests of (a) | nowhere; I16's route part stays (`decision.route`) |

No (b) check is lost.

## Files to delete (8)

- `cli/wuwei/cruise.py`
- `cli/wuwei/calibration_scores.py`
- `cli/wuwei/budget_classes.py`
- `cli/wuwei/commands/cruise.py`
- `cli/wuwei/commands/shadow.py`
- `tests/test_cruise.py`. Every case exercises deleted code. Before deleting it, carry the
  supervised mandate assertion at `583-591` into `tests/test_brief.py` (T004).
  `test_closing_collects_a_cruise_park_disposition` (261) is covered by
  `test_decision_classes.py::test_a_mandate_park_keeps_its_disposition` (243).
- `tests/test_calibration_scores.py`. `test_role_field_and_the_payload` (65) pins `Role:`
  validation. Move only its lint assertion into `tests/test_decision.py` (T009).
- `tests/test_budget_classes.py`

## Files to edit, code (27)

### `cli/wuwei/decision.py`

- 7: replace the cruise import with a local tuple:
  `CLASSES = ('approach', 'retry', 'park', 'accept-residual', 'defer', 'scope-cut', 're-plan', 'dependency-bump', 'design', 'boundary', 'refactor', 'merge', 'message', 'other')`
  (the order of `cruise.CLASSES`). Drop CRUISE, level and running.
- 27: comment becomes "Design 5.8: the ambiguity threshold of cisr." `MARGIN` stays.
- 117: delete the `cruise = re.fullmatch(...)` line. In 121 the test becomes
  `if fields[key] not in allowed:`.
- 125-127: `Role:` validation stays. The comment drops "#559: the role whose confidence is
  scored".
- 390-398 `cisr`: drop the `ambiguous` parameter. 394 returns `'Routine'`. In 397, `clear` loses
  `not ambiguous and`. The docstring keeps only the #530 line.
- 401-404: delete `uncalibrated`.
- 412-440 `route_owner`:
  - drop the `thin` parameter;
  - delete 428 (`role = ...`);
  - 429 becomes `kind = cisr(fields, _scored(fields)[3])`;
  - 430: extra becomes `{'class': fields.get('Class'), 'at': ...}`;
  - delete 437-438 (`uncalibrated`).

### `cli/wuwei/commands/decision.py`

- 8: drop `uncalibrated` from the import.
- 75-78: becomes `route_owner(args.id, fields, root)`. Delete the cruise import and `thin`.
- 96: delete the #283 docstring line.
- 112: `kind = cisr(fields, scores)`.
- 115-117: `record = {**seat_outcome(fields, scores, by='mandate'), 'cisr': kind}`.
- 124: `by = 'mandate'` (inline it in 126 and 128).
- 129-132: delete the shadow block. If nothing else uses `sys`, drop the import; `run`
  uses it (364), so keep it.
- 153-162 (`show --widget`): delete the cruise import and the Keep/Undo card. Keep
  `return 0, '[]'` for every mandate row.
- 252-253: delete `cruise.answered`.
- 263-315 `undo` (kept one part longer):
  - 266: import only `sessions`.
  - 264-265 docstring: "Revert an answer the mandate took, after the owner's Undo, and ask
    the owner; where is given only by the DM listener."
  - 279-283: becomes one check, `if not isinstance(row, dict) or row.get('decided_by') != 'mandate': return 1, f'{args.id} was not taken under the mandate; reverse it with wuwei decide {args.id} <option>'`.
  - 291: `Undo the mandate answer.`
  - 304: drop `'thin': False`.
  - 308: drop `'rule': row['rule']`.
- 42: subparser help "Undo an answer the mandate took and ask the owner".

### `cli/wuwei/brief.py` (67-105 `mandate`)

- 69: the `decision` import stays (for `CLASSES`).
- 73-76 become:
  `assumed = config['autonomy']['mode'] == 'autonomous'`;
  `recorded = ['retry', 'park', 'accept-residual', 'merge'] if assumed else []`;
  `owner = [name for name in decision.CLASSES if name not in recorded and not (assumed and name == 'approach')]`.
- The text is unchanged.

### `cli/wuwei/workspace.py`

- 162-169: delete the `"cruise"` table; `decisions` keeps `wait_hours` and `lenses`.
- 754-766: delete the margin, budget_share and calibration_threshold checks and the levels
  loop.

### `cli/wuwei/promotion.py`

- 43-96: delete `cruise_level`, `calibration`, `cruise_shadow` and `_cruise_write`.
- Drop `uuid4` and `json` imports only if nothing else uses them; `promote` uses `json`, so
  keep it.

### `cli/wuwei/steward.py`

- 24-28: delete the budget, calibration and shadow steps.

### `cli/wuwei/plan.py`

- 276-277: delete the `cruise.propose` call. Part 11 deletes `grants.plan` at 274-275.

### `cli/wuwei/commands/plan.py`

- 75-79: drop `cruise` from the import and `*cruise.gate_widgets(root, config)` from the list.

### `cli/wuwei/report.py`

- 8: drop `calibration_scores` and `cruise` from the import.
- 187-189: delete `'## Calibration', *calibration_scores.lines(...)`, `''` and
  `'## Cruise shadow', *cruise.shadow_lines(root)`; the list continues with `''`,
  `'## Merged'`.
- Keep `shadow_lines` (30-54) and the `## Shadow` section (236-238).

### `cli/wuwei/retro.py`

- 154-155: delete the `## Calibration` section.

### `cli/wuwei/commands/status.py`

- 28-30 `SHADOW_NUDGE`: the last sentence becomes "The day report's ## Shadow section lists
  what would have been refused." `doctor.py:457` imports it.
- 230-237: delete the `decision.cruise` attention row. Then `datetime` at 233 may be unused
  locally; check.
- 258: the sort key keeps only `row['source'] != 'pr.changed'`.
- 362-364: delete the cruise label; keep 365 `checks_none`. Fix the comment.
- 525 and 530: delete the `cruise` group.

### `cli/wuwei/commands/why.py` (`decided`, 289-318)

- 290: docstring drops "level".
- 312: the early return drops the `level:` step.
- 315-318: delete `cruise = ...`. Return `steps + [(f'decided: {payload.get("option")} by {by}', at, [])]`.

### `cli/wuwei/watch.py` (digest, 133-147)

- The pending tuple drops `rule`, sorted by id.
- 140-143: the check keeps only the id and option patterns.
- 145-147: no `(rule)` suffix.

### `cli/wuwei/closing.py`

- 194: `fields['Decided-by'] == record['decided_by']`.

### `cli/wuwei/telemetry.py`

- 46: drop `'cruise'` from INNER.
- 176-177: `Counter(who for who in by if who in ('owner', 'seat'))`.
- `CLASSES` (34-35) stays; a test pins it to `decision.CLASSES`.

### `cli/wuwei/profiles.py`

- 29-32: delete the four `decisions.cruise.*` rows.
- 83-84: delete the levels branch of `_current`.

### `cli/wuwei/signal.py`

- 27: drop `'decision.notified'`, `'cruise.carded'` and `'decision.shadow'` from `SILENT`.

### `cli/wuwei/commands/event.py`

- 84: drop `'cruise.burn'`. Keep `calibration.drift`, which belongs to calibrate.
- 86: drop `'decision.notified'`.
- 87: drop `'cruise.carded'`.
- 89: drop `'decision.shadow'`.

### `cli/wuwei/state.py`

- 278: drop `'cruise_cards'`.
- 280: drop `'decision_shadows'`.

### `cli/wuwei/guards/protect_state.py`

- 389: drop `('memory', 'cruise.json')` from the protected tuple.

### `cli/wuwei/commands/next.py`

- 16: the observe text ends "...owner-only. The day report's ## Shadow section lists the
  would-be refusals."

### `cli/wuwei/undo.py`

- 150: the docstring becomes "wuwei undo: a D-n through decision undo, or a merge event."
  The whole file goes in part 10.

### Skip if already gone (batches 1 and 2)

- `cli/wuwei/commands/nudges.py:14-15` (#801): drop the `decision.cruise` and `cruise.burn`
  rows.
- `cli/wuwei/listen.py:83-97` (#810): delete the cruise notify loop, the only producer of
  `decision.notified`.
- `cli/wuwei/commands/__init__.py:5` (#800): drop `cruise budget`, `cruise calibration`,
  `cruise shadow` and `shadow report` from `READ_ONLY`.
- `cli/wuwei/__main__.py:32,34` (#800): drop `cruise` and `shadow` from GROUPS.

## Files to edit, charters and agents (1 plus generated)

- `charters/_common.md:27`:
  - "`Class:` (a design 5.8.1 class)" becomes "`Class:` (a design 5.8 class)".
  - Delete "`Role:` (your role, the charter name; your stated confidence is scored per
    role) and".
- `agents/*.md`: regenerate with `bin/wuwei agents build`. Never hand edit.

## Files to edit, docs (9)

### `docs/specs/2026-09-24-wuwei-design.md`

- 21 (G1): "decisions cruise mode does not answer" becomes "decisions the mandate does not
  take".
- 301 (4.6): drop the cruise merge-class sentence.
- 481-488 (5.2): the mandate is fixed by `autonomy.mode` (FR-003 lists).
- 553-557 (5.3): "approach while it runs at L2 or L3" becomes "approach under `autonomy.mode =
  autonomous`".
- 652-657 (5.4): "cruise mode routes" becomes "the mandate takes"; drop "decisions cruise
  mode answered".
- 768-776 (5.8):
  - "the owner or cruise mode answers" becomes "the owner or the mandate answers";
  - `Class:` names the list below;
  - delete the `Role:` "scored per role" clause, keeping `Role:` optional, one line.
- 798-802: `Decided-by:` is `seat`, `owner` or `mandate`. Delete "Routing by class ... cruise
  mode does not answer goes to the owner", keeping "When unsure, it is one-way."
- 808-810: "5.8.1 margin" and "5.8.1 classes" become "the margin (below)" and "the classes
  below".
- 850-853: metrics drop "share answered by cruise mode", "cruise answers the owner later
  reversed (each one demotes its class, 5.8.1)" and "the agreements 5.8.1 promotes from".
- 855-990: replace `#### 5.8.1 Cruise mode` with `#### 5.8.1 Decision classes (owner,
  2026-10-11, #814)`. It holds:
  - one sentence: "Classes are a fixed list; a new class is an amendment to this section";
  - the class table with the columns Class and Decides only (869-884 without Default and
    Ceiling);
  - the margin definition from 897-905, "the recommendation's weighted score minus the best
    other option's over 10 times the sum of the weights";
  - "Routing is fixed in code (5.8, decision classes); no class level, budget, calibration or
    shadow exists."
  - Keep the Novelty paragraph (991-1008) below it for part 10, minus "runs one level lower
    than its class level, never below L0 and never above the ceiling" (becomes "asks the
    owner once") and "with no cruise levels" and "the mandate form arrives with the cruise
    levels".
- 1044, 1048 (5.9): drop the L2 and L3 cruise answer tiers.
- 1310-1311, 1353-1354 (telemetry): drop the `cruise` count.
- 1337: delete "Cruise promotions stay the steward's".
- 1546-1547: "the message ceiling of cruise mode" becomes "the message rule (one-way)"; delete
  "cruise levels do not apply".
- 1831: delete the clause naming `memory/cruise.json` as a promote target.
- 9.2: delete rows I11 to I14 (2027-2030). I16 (2032) drops "cruise.level for every class".
  Skip if #798 replaced the table.

### `docs/site/concepts.md`

- 180: drop "`bin/wuwei shadow report` and".
- 426: the heading "Decision classes and cruise levels" becomes "Decision classes".
- 437-468: delete the cruise, error budget, calibration and shadow paragraphs.
- 470-474: the mandate is fixed by `autonomy.mode`.

### `docs/site/daily.md`

- 185-194: drop `bin/wuwei shadow report` and point to the report's `## Shadow` section.
- 440-476: delete `### Cruise answers`.

### `docs/site/reference.md`

- 19: delete the `bin/wuwei cruise` row.
- 65: delete the `bin/wuwei shadow` row.
- 426: drop "the cruise level" from `why D-n`.
- 22: `undo D-<n>` "reverts an answer the mandate took".

### `docs/site/configuration.md`

- 17: drop `[decisions.cruise]` and `[decisions.cruise.levels]`.
- 200-213: delete every `decisions.cruise.*` row.
- 216: the mandate paragraph states the fixed rule.
- 412: drop the `decisions.cruise` refusal clauses.

### `docs/site/recovery.md`

- 77: "the day report's `## Shadow` section lists what would have been refused".

### `docs/site/agent.md`

- 50 and 56: regenerate if `cli/wuwei/guide.py` still exists. After #800 deleted it, delete
  the `cruise` and `shadow` lines by hand.

### `README.md`

- 39: delete the cruise mode bullet.
- 77: delete the shadow report bullet.
- 115: rewrite principle 5 into its end state for this batch: "Reversibility is a rule, not a
  score: a two-way door inside the item is assumed and recorded, anything else reaches you as
  one named decision from `wuwei next`; when unsure, it is one-way." The link becomes
  `(docs/site/concepts.md#decision-classes)`. No #556 to #560 links, no novelty or undo text.
- 171: point to the day report's `## Shadow` section.
- 283-284: delete the Error budgets and Brier acknowledgements.

### `NOTICE`

- 110-118: delete the Error budgets and Brier score blocks.

## Files to edit, templates (1)

- `templates/workspace/config.toml:285-296`: delete the commented `[decisions.cruise]` block.

## Files to edit, tests (19)

- `tests/test_decision_classes.py`: new `test_stale_cruise_state_never_changes_a_route`.
  - Write a `memory/cruise.json` with `levels.park = 0` and calibration roles `['builder']`.
  - Route a Routine `park` record with `Role: builder`: `mandate`.
  - The payload has no `rule`, `level`, `undo_until` or `items`.
  - The record reads `Decided-by: mandate`.
  - The route rows of an owner-routed one-way record have no `thin` and no `uncalibrated`.
- `tests/test_decision.py`:
  - delete `test_class_levels` (964-976);
  - add `test_classes_are_the_fixed_list` (the 14-name tuple);
  - add `test_cruise_decided_by_reads_as_mandate_and_is_refused_on_write` (a stored
    `Decided-by: cruise park@L2` reads as `mandate`; lint refuses it);
  - add the Role lint assertion from `test_calibration_scores.py:65`.
- `tests/test_brief.py`:
  - delete `test_mandate_follows_class_levels` (454-459);
  - add `test_the_mandate_is_fixed_by_autonomy`: the supervised text from
    `test_cruise.py:583-591`, and a `[decisions.cruise.levels] approach = 1` config plus a
    `memory/cruise.json` leave the autonomous text equal to the default;
  - keep 443-452.
- `tests/test_plan.py`: delete `test_propose_writes_the_cruise_raise_card_the_gate_carries`
  (920 to its end).
- `tests/test_why.py`:
  - delete `test_decision_view_reads_class_and_cruise_level` (362-367);
  - 356: drop `level: not recorded`.
- `tests/test_report_retro.py`: 318 drop `## Calibration` and `## Cruise shadow`. Keep 344
  `test_report_shadow_section`.
- `tests/test_signal_status.py`:
  - 140: drop `cruise` from the snapshot keys;
  - 387-389: drop `decision.notified`, `cruise.carded`, `decision.shadow`, `cruise.burn`;
  - add a status-line case with a damaged `memory/cruise.json` (no `cruise` token, exit 0).
- `tests/test_state_allowlist.py`: delete rows 62 (`cruise_cards`), 142 (`decision.notified`)
  and 143 (`cruise.carded`).
- `tests/test_telemetry.py`: 79 and 97 drop the `cruise approach@L2` event and its count.
- `tests/test_calibrate.py:751-771`: delete `ON`, `LEVEL1` and every `decisions.cruise.*`
  parameter row; keep `guards.mode`.
- `tests/test_protect_state.py:607`: drop `.wuwei/memory/cruise.json`.
- `tests/test_workspace.py`:
  - 256-258: drop the `cruise` dict from the defaults;
  - delete `test_decisions_config` (1216-1226);
  - add `test_a_cruise_table_only_warns` (after #799: a `[decisions.cruise]` table loads with
    an unknown-key warning).
- `tests/test_shadow.py`:
  - delete `test_shadow_report_command` (65-88);
  - in `test_status_shows_posture_and_nudges_once` and
    `test_session_start_says_observe_is_on`, replace `bin/wuwei shadow report` with the new
    text;
  - keep the rest.
- `tests/test_next.py:347`: expect the new observe text.
- `tests/test_e2e_day.py:282`: replace `day.run('shadow', 'report')` with `report.shadow_lines`
  over the day directory.
- `tests/test_hooks.py:376,1090`: drop `wuwei.cruise` from the forbidden-module sets.
- `tests/test_undo.py`:
  - fixture `cruised` (288-298) becomes `taken`: "A park record taken under the mandate";
    delete the `undo_until` assert at 295;
  - in `test_a_seat_closed_or_missing_window_writes_nothing` (331-350), delete the closed
    window (339-340) and the missing window case (341-350), keep the seat case, and rename it
    `test_a_seat_writes_nothing`;
  - 439: delete the `cruise.json` assert;
  - rename `test_wuwei_undo_reverts_a_cruise_answer_and_records_the_exercise` to
    `..._a_mandate_answer_...`.
- `tests/test_docs.py`:
  - delete `test_cruise_mode_ships` (844-859);
  - 864: heading `Decision classes`;
  - 605 and 1137: drop the `decisions.cruise` phrases;
  - 1188: drop `error budget` and `Brier` from the NOTICE names;
  - 252: replace `shadow report` with the new README phrase.
  - Principle 5 of `PRINCIPLES` (146-149) and the `range(556, 561)` loops (175, 194-198)
    follow the rewritten principle: phrases `('rule', 'two-way', 'one named decision',
    'one-way')`, link `(docs/site/concepts.md#decision-classes)`, and the issue loops go.
    Skip any of these if #798 deleted the test.

### Skip if already gone (batches 1 and 2)

- `tests/test_invariants.py` (#798):
  - delete `budget_rule`, `i11`, `calibration_rule`, `i12`, `shadow_rule`, `i13`, `i14`
    (468-541) and their `INVARIANTS` (1548) and `READS` (1582) entries;
  - in `i16` (570-597) drop the cruise tuple;
  - in `i22` (750-769) `cruise.CLASSES` becomes `decision.CLASSES`.
- `tests/test_remote.py` (#810): delete `cruise_answer` (981-991) and
  `test_listen_sends_each_cruise_answer_once` (993-1001); 1013-1019 drop the cruise notify
  text.
- `tests/test_cli_known_command.py:55` (#800): drop `(['shadow', 'report'], True)`.
- `tests/test_nudge_hygiene.py:168-180` (#801): use `report.shadow_lines`.

## RETIRED at rebase

The base has no `workspace.RETIRED`. After #799 merges, the lead adds:

- `decisions.cruise` (the table, with `decisions.cruise.levels`).

Not retired here: `guards.shadow_days` and `guards.shadow_since` (spec Assumption 1;
posture part 15). The file `memory/cruise.json` is added to part 10's init file removal (see
specs/815-undo-novelty-out/plan.md).

## Risks for the builder

- Upgrade-day records: a stored `Decided-by: cruise ...` reads as `mandate` on every read
  path, so `wuwei close` measures it; lint, `decision.write` and the scanner pass
  `write=True` and refuse it.
- `tests/test_brief.py::test_builder_prompt_carries_the_mandate` pins the default lists. The
  fixed rule must reproduce them exactly, `approach` first in the supervised owner list.
- Telemetry: `telemetry.CLASSES` must equal `decision.CLASSES`
  (`tests/test_telemetry.py:134`). Keep the order.
- `decision undo` stays one more part without its window. Part 10 deletes it, and the doctor
  Keep/Undo card exclusion (`doctor.py:773-781`) with it.
- Shared files with parts 10 and 11 and with batches 1 and 2: `commands/decision.py`,
  `decision.py`, `report.py`, `status.py`, `event.py`, `signal.py`, `state.py`,
  `workspace.py`, `plan.py`, `commands/plan.py`, `protect_state.py`, the docs pages.
