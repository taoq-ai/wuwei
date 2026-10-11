# Implementation Plan: delete the undo door, undo rehearsal and novelty

**Branch**: `b3-decision-framework` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at main ac5403f, the batch base. Batches 1 and 2 (#798 to #801, #808 to
#811) land first and the lead rebases. An edit marked "skip if already gone" touches code
those batches delete: make it only if the code is still there.

This is part 10. It assumes part 9 (#814) is done on this branch. Part 9 already:

- deleted cruise, the undo window and `undo_until`;
- reduced `commands/decision.py::undo` to a mandate-row check;
- deleted the Keep/Undo widget in `decision show`;
- edited `undo.py:150` (docstring);
- rewrote README principle 5 without novelty or undo;
- moved the Novelty paragraph of the design spec under the new 5.8.1 Decision classes.

This part no longer touches any of that. Line numbers in `commands/decision.py` shift after
part 9; locate by function name.

## Summary

Delete measured reversibility (#557), the undo commands, the rehearsal ledger, the merge
undo journal and the seen set (#556).

What stays deterministic in code:

- **Routing.** `decision route` routes on the written door (`decision.route`, `cisr`,
  `mandate`). One-way, Strategic, tied and owner-written records go to the owner, and
  `wuwei next` returns each as `Decision D-n waits for your answer`.
- **Merge recovery.** A red base after a merge still opens the revert PR, trips the breaker
  and pages: `merge.revert` (645-655) and `merge.monitor` (701-711).
- **Owner reversal.** The owner reverses a taken record with `wuwei decide D-n <option>`,
  which writes `decision.reversed`.

## Technical Context

- Stdlib-only Python 3.11+; pytest is dev-only.
- One new tuple: the retired memory files in `commands/init.py`.
- Run only the touched test files: `python3 -m pytest -q <files>`. CI runs the suite.

## Constitution Check

- **I.** Nothing added.
- **II.** `wuwei undo` and `decision undo` go whole. No guard gains or loses an exit path. The
  deploy guard and the outward guard lose only the novelty branch (`grants.gate`,
  `outward.check`), which only ever turned a pass into a card.
- **III.** Routing stays in `commands/decision.py::decide` and `mandate`.
- **IV.** tasks.md writes the red tests first: the written door stands, a new target routes
  like a known one, no rehearse row, init removes the files.
- **V.** Net deletion. The file removal is one tuple and one loop in `init.upgrade`.
- **VII and the Workflow invariant rule.** I22, I23 and I33 go with the rules they guard.
  Skip if #798 removed the walk.
- **Design spec ownership.** The edits are part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `undo.measured`, `undo.correct`, the lint correction line, `REGISTRY`, `KIND` | (a) the CLI second-guesses the written door from a ledger | the written door; charters keep "when unsure, it is one-way" |
| `undo.config_write`, `two_way`, `CONFIG` (#600) | (a) changes only the card text of a config record (config records never reach the mandate, #529) | nowhere |
| `wuwei undo rehearse`, `rehearsals.json`, `undo.rehearsed`, `next` row `rehearse`, doctor row, init line, git `rehearse_revert` | (a) a process chore the loop asked the planner to run | nowhere |
| `wuwei undo D-n`, `decision undo` | (a) a second reversal path for mandate answers | `wuwei decide D-n <option>` (the owner's answer) |
| `wuwei undo <event id>` (`undo._merge`) | (a) an owner convenience over `merge.revert` | the red-base watch keeps `merge.revert`; the owner reverts by hand otherwise |
| Merge undo journal (`merge.undo`, `undo.jsonl`) | (a) write-only, no reader | nowhere |
| `merge.revert`, `merge.monitor` red path, `revert_pr` adapters | (b) a red base gets its revert PR, breaker and page | kept unchanged |
| `novelty.*`, `targets.json`, route `novel`, deploy and outward first-time branches, `why` target keys, report `First time today` | (a) the CLI and model reason about which target is new | nowhere; outbound tiers (4.9), the deploy guard and the merge policy gate the actions |
| Report `Undone today` and `Cannot be undone` | (a) | nowhere |
| `protect_state` hints and paths for `targets.json`, `rehearsals.json`, `undo.jsonl` | (b) only for files that are gone | nothing left to protect; `ledger.jsonl` stays protected |
| Design 9.2 I22, I23, I33 | tests of (a) | nowhere |

No (b) check is lost.

## Files to delete (5)

- `cli/wuwei/undo.py`
- `cli/wuwei/commands/undo.py`
- `cli/wuwei/novelty.py`
- `tests/test_undo.py`. Every case covers deleted code. That includes the #600 cases at
  545-613, the decision rehearsal and the merge-event undo. `merge.revert` keeps its own test
  in `tests/test_merge.py:995-1005`.
- `tests/test_novelty.py`. Part 11 then has no grants fixtures to replace here.

## Files to edit, code (21)

### `cli/wuwei/commands/decision.py` (locate by name; part 9 shifted lines)

- Imports (base 7): drop `novelty`.
- Subparser `undo` (base 42-45): delete it. Delete the `undo(args) if ...` branch of `run`
  (base 363).
- `decide` (base 59-61): delete the `undo.correct` call and `said`. Returns at base 68, 73 and
  79 drop `+ said`.
- `mandate` (base 105-108): delete the novelty card.
- `show` (base 167-169): delete the `First time for` suffix.
- `owner_outcome` (base 254-259): delete the `novelty.clear` loop and its condition.
- `undo` (base 263-315, part 9's version): delete the function.
- `template` (base 331): the Context line becomes "Replace with the evidence file and reason
  for deciding."

### `cli/wuwei/decision.py`

- `lint` (289-297): delete the #557 block (`said`, `door`, the `if root is not None` branch).
  The `root` parameter is unused, so the signature becomes `lint(text, lenses=LENSES)`.
  `lint_file` (365) calls `lint(text, lens_table(...))` when root is set.
- `route_owner` (427, 434-436): delete the novelty import and the `novel` field.

### `cli/wuwei/grants.py` (part 11 deletes the file; keep it green here)

- 104: the docstring drops "standing=False leaves the [grants] lines out (#556: a novel
  target)".
- 162-166: delete the novelty block. 168: `active(config, data, name, found)`.

### `cli/wuwei/outward.py`

- 804-815: delete the #556 first-time channel block.

### `cli/wuwei/drafts.py`

- 331-335: delete `novelty.clear` on approve. Drop `re` only if it becomes unused.

### `cli/wuwei/commands/why.py`

- 7: drop `novelty`.
- 41: drop `novelty.KEY` from the target patterns.
- 56-57: delete the target-key branch.
- 304-306: delete the `novel:` step.

### `cli/wuwei/report.py`

- 8: drop `novelty` and `undo`.
- 184: delete.
- 186-187: delete `## First time today`, `## Undone today` and `## Cannot be undone`.

### `cli/wuwei/commands/init.py`

- 393-394 and 430-431: delete the seen-set seed and its print.
- 442-446: delete `Undo not rehearsed`.
- New: `RETIRED_FILES = ('memory/rehearsals.json', 'memory/rehearsals.lock', 'memory/targets.json', 'memory/targets.lock', 'memory/cruise.json')`.
  In `upgrade`, for each path under `.wuwei` that exists and is a regular file, not a
  symlink, unlink it unless `--dry-run`. Print `{prefix} .wuwei/<path>: remove (no longer
  read)` once per file. Count it as a change like the other upgrade lines.

### `cli/wuwei/commands/doctor.py`

- 397: `return rows`.
- 400-412: delete `_undo`.
- 773-781 (`_unrecorded`): drop the Keep and Undo card-topic exclusion and its docstring
  clause. The undo card is gone.

### `cli/wuwei/commands/next.py`

- 214-222: delete the `rehearse` row. Part 9 left its tuple as is.

### `cli/wuwei/commands/event.py` and `cli/wuwei/signal.py`

- `event.py:102`: drop `undo.rehearsed` and `undo.done`. Keep 62 (`decision.reversed`).
- `signal.py:27`: drop `undo.rehearsed` and `undo.done` from `SILENT`.

### `cli/wuwei/registry.py`

- 63: drop `'rehearse_revert': ('path',)`.

### `adapters/vcs/git.py`

- 62-63: delete the rehearsal `case` in `_run`.
- 815-834: delete `_scratch` and `rehearse_revert`.

### `cli/wuwei/guards/protect_state.py`

- 402: drop `'undo.jsonl'`.
- 404: keep only `('memory', 'ledger.jsonl')`.
- 435-440: delete both hints.

### `cli/wuwei/merge.py`

- 462-468: delete `undo` (the journal).
- 523 and 681: delete the calls.
- 646: the docstring drops "and #557 wuwei undo".
- Keep `revert` and the `monitor` red path.

### Skip if already gone (batches 1 and 2)

- `cli/wuwei/commands/__init__.py:15,34` (#800): drop `decision undo` and `undo`.
- `cli/wuwei/__main__.py:28` (#800): drop `undo` from GROUPS.
- `cli/wuwei/remote.py:19,34,94-95,305-311` (#810): drop the `undo D-n` verb, `UNDONE` and
  the regex alternative.

## Files to edit, charters and agents

None. The charters hold no undo, rehearsal or novelty text. `_common.md:28` keeps "when
unsure, write it as one-way". No agent rebuild is needed.

## Files to edit, docs (6)

### `docs/specs/2026-09-24-wuwei-design.md`

- 336-338 and 356 (4.6): drop "and an undo-log entry whose undo is the revert PR" and
  "undo-logged". Keep the revert PR.
- 822-835 (5.8): delete "Measured reversibility (owner, 2026-10-08, #557)".
- The Novelty paragraph part 9 kept (base 991-1008): delete it.
- 9.2 rows I22, I23 and I33 (2038, 2039, 2049): delete. Skip if #798 replaced the table.

### `docs/site/concepts.md`

- 102-105: delete `### Novel`.
- 493-503: delete `## Measured reversibility`.

### `docs/site/daily.md`

- 420-431: delete the novelty and measured-undo paragraphs.

### `docs/site/reference.md`

- 22: drop `undo D-<n>` from the decision row.
- 79: delete the `bin/wuwei undo` row.
- 114: delete the novelty sentences.
- 116: delete the "Measured reversibility" paragraph.
- 416: drop the target-key form of `why`.

### `docs/site/agent.md`

- 29: if `guide.py` still exists, regenerate. After #800, delete the `undo` line by hand.

### `README.md`

- Check only: part 9 rewrote principle 5. Line 200 (release rehearsal) stays.

## Files to edit, tests (16)

- `tests/conftest.py:37-44`: delete the autouse `rehearsed_undo` fixture.
- `tests/test_decision_classes.py`, two new tests:
  - `test_the_written_door_stands`: no ledger, two-way `approach` record, `mandate`, record
    unchanged, no correction line.
  - `test_a_new_target_routes_like_a_known_one`: a Routine record naming `repo:acme/new`
    routes `mandate`, and no `memory/targets.json` exists.
- In the same file, 235: the comment drops "#557: other has no undo".
- `tests/test_decision.py`: new `test_lint_prints_no_door_correction`. A two-way `message`
  record lints with one OK line.
- `tests/test_next.py`:
  - delete `test_unrehearsed_undos_are_run_rows_before_the_cards` (778-797);
  - add `test_no_rehearse_row`: after the gate, with no ledger, no row has state `rehearse`.
- `tests/test_doctor.py`:
  - 315: drop `undo rehearsals`;
  - 616-625: drop the Keep and Undo card lines in `test_answered_cards_row`;
  - delete `test_undo_rehearsals_row` (1424-1437).
- `tests/test_workspace.py`:
  - 1321 and 1338: drop the `Undo not rehearsed` filter;
  - new `test_upgrade_removes_retired_memory_files`. Seed the five files, run `init
    --upgrade --dry-run` (files kept, `Would` lines), then `init --upgrade` (files gone, one
    line each).
- `tests/test_protect_state.py`: delete `test_seen_set_is_cli_owned` (1109-1120) and
  `test_rehearsal_ledger_is_cli_owned` (1135-1146).
- `tests/test_report_retro.py`:
  - 318: drop the three sections;
  - delete `test_report_lists_what_was_undone_and_what_cannot_be` (482-507).
- `tests/test_merge.py`:
  - 420-431: drop the `undo.jsonl` asserts and rename
    `test_merge_pins_head_and_writes_evidence`;
  - 578: drop the journal assert;
  - delete `test_fail_before_external_merge_if_undo_cannot_be_written` (718-720) and
    `test_undo_file_is_protected` (842-844);
  - 996: edit the comment.
- `tests/test_vcs.py`: delete `test_rehearse_revert_on_a_scratch_repository` (494-505).
- `tests/test_adapters.py:83`: delete the `rehearse_revert` row.
- `tests/test_signal_status.py:388`: drop `undo.rehearsed` and `undo.done`.
- `tests/test_outward.py`: delete the `familiar` helper (1426-1430) and its calls (1531, 2024).
- `tests/test_hooks.py:1090`: drop `wuwei.novelty`.
- `tests/test_calibrate.py:1320,1328`: drop the `undo.config_write` asserts. The card stays
  a Routine value card.
- `tests/test_docs.py`:
  - 30: drop `('Novel', r'novel')` from GLOSSARY;
  - 148: drop `novel` and `undo` from the principle phrases, if part 9 left them.
  - Skip if #798 deleted the test.

### Skip if already gone

- `tests/test_invariants.py` (#798): delete `i22`, `i23` and `i33` with their `INVARIANTS`,
  `READS` and `BROKEN` entries (750-785, 969-990, 1550, 1584, 1695-1698, 1712-1713).
- `tests/test_remote.py` (#810): delete `test_owner_dm_undo_runs_the_undo` (1004-1010) and
  the `UNDONE` part of 1013-1019.
- `tests/test_cli_known_command.py` (#800): nothing to edit, since its sets derive from the
  registry.

## RETIRED at rebase

- Config keys: none. Measured reversibility and novelty have no config key.
  `decisions.cruise.undo_minutes` went with the table in part 9.
- Files: the five memory files above. `init --upgrade` removes them through `RETIRED_FILES`
  in this part. If #799's `workspace.RETIRED` grows a file form later, the lead may fold the
  tuple into it.

## Risks for the builder

- The conftest fixture hid the ledger from every test. With it gone, look for any test that
  routed `merge`, `message`, `other` or class-less records and expected `owner` because of
  the correction. Known cases are in `tests/test_decision_classes.py` and
  `tests/test_decision.py`. Run both files fully.
- `decision.lint` loses `root`. Grep for callers passing three arguments: `lint_file` (365)
  and the PostToolUse lint path.
- `outward.check` gets shorter in the autonomous chat path. The tier table still decides
  after it, and `tests/test_outward.py` covers it.
- `merge.monitor` must still call `revert` and trip the breaker on a red base. Run
  `tests/test_merge.py` fully.
- Shared files with parts 9 and 11: `commands/decision.py`, `decision.py`, `report.py`,
  `grants.py`, `doctor.py`, `init.py`, `event.py`, `signal.py`.
