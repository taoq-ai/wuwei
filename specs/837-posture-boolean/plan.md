# Implementation Plan: posture becomes one boolean, guards.enforce; the traces recorder never refuses

**Branch**: `b5-guards` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at 703b40de, the batch base. This part is built first on the branch; part 16
(#838) follows it and deletes the outward tier table, drafts and learning cards.

## Summary

`security.posture`, `security.areas`, `guards.mode`, `guards.shadow_days` and
`guards.shadow_since` give way to one boolean, `guards.enforce` (default true). The hook blocks
every refusal when it is on. When it is off, the hook logs a refusal as `guard.would_refuse`
and lets the call pass, except the floor (records and the owner's edges), which blocks either
way. Every strict-only branch outside the hook takes its default branch, except two rows of the
pass plan's "Process control kept" table: a seat launch without a matching brief, and a bare
`gh pr create` for a recorded item. Both refuse when enforce is on. The traces recorder never
refuses. `init --upgrade` maps observe (and the older shadow mode) to `guards.enforce = false`,
then removes the retired keys.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion: one constant (`guards.FLOOR`) and one
helper (`guards.floor`) replace `AREAS`, `OWNER_ONLY`, `level`, `POSTURES`, `AREA_LEVELS`,
`FLOORS`, `posture` and `posture_source`. Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: an unreadable config still blocks every refusal (fail closed). The traces recorder's
  could-not-run becomes a warning and an event (the issue). Exit 2 elsewhere is unchanged.
- III: one switch, read in one place per guard path: the hook (`hook.enforce`); the guards that
  register a seat or pass with a note read `config['guards']['enforce']` directly.
- IV: red tests first for the hook table, the upgrade mapping, the traces recorder and the two
  table rows.
- V: about 300 lines of code and 1,500 lines of tests go.
- VII: amended (task T011). The floor stays, the posture names go.
- Design spec ownership: part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Postures, areas, levels, `security.areas` overrides, `posture_source`, the `posture:` line under each refusal | (a) the planner and the owner reason about which area at which level | one switch, no line |
| `FLOORS` config floor and its `config check` finding | (a) a setting that guards a setting | nowhere; there is no area to lower |
| `OWNER_ONLY`, `RECORDS_FLOOR`, `MERGE` as posture inputs | (b) records and the owner's edges never pass | `guards.FLOOR` and `guards.floor()`, read by the hook |
| `guards.mode` (deprecated), `shadow_days`, `shadow_since`, the doctor countdown | (a) | nowhere; doctor shows one `guards` row |
| Strict-only branches listed in the reader table as "default" | (a) a second behaviour per check | the default (guarded) branch |
| Seat launch with no brief line or a mismatched brief (warn under guarded) | (b) seat without a brief | refuses when enforce is on (table row) |
| `gh pr create` for a recorded item (refused only under strict) | (b) PR raised outside WUWEI | refuses when enforce is on (table row) |
| `pr raise --item` gate miss | (b) | refuses when enforce is on; logged and raised when off (as observe) |
| Traces recorder refusal under strict | (a) recording is not a gate | warning plus `traces.gap` or `traces.slow` |

No (b) check is lost.

## Every reader of posture areas and levels, and what it becomes

| Reader (file:line) | Today | Under one boolean |
| --- | --- | --- |
| `workspace.py:37-49` `POSTURES`, `AREAS`, `AREA_LEVELS`, `FLOORS` | the posture table | deleted |
| `workspace.py:71-72` `security.posture`, `security.areas` | schema | deleted; `security = {"required"}` |
| `workspace.py:159-160` `guards.mode`, `shadow_days`, `shadow_since` | schema | `guards = {"enforce": (bool, True)}` |
| `workspace.py:757-769` `shadow_since` and floor validation | config findings | deleted |
| `workspace.py:820-831` `posture()`, `posture_source()` | the resolver | deleted |
| `guards/__init__.py:35-82` `AREAS`, `OWNER_ONLY`, `level()` | per-check level and line | `FLOOR` and `floor(check, reason)` |
| `commands/hook.py:123,147,274-347` `posture()` | levels each refusal | `enforce()`: block if on or on the floor, else log |
| `guards/agent_launch.py:101-102` `_unbriefed` | refused only where seats block | refused when enforce is on, else an adhoc seat with the warning |
| `guards/agent_launch.py:130-132` `_adhoc` | untyped launch refused under strict | never refused (default); the `seat start --adhoc` label lookup stays |
| `guards/agent_launch.py:31-32` `check_mcp` docstring | "mcp posture" | reword |
| `mcp.py:320-344` `cached` | mcp level and observe note | enforce on: the guarded branch (`scanner.mcp.block` and unrun block); off: pass with note `(guards.enforce = false)`; the strict list expansion and `off` go |
| `mcp.py:500-501` `check` | `mcp = off` skips | branch deleted |
| `mcp.py:195` | comment | reword |
| `guards/pr.py:249-251` recorded item `gh pr create` | refused under strict, else warning | `return 1, hint` (the hook decides) |
| `shepherd.py:309-317` `raise_pr` gate miss | publish level | `if code == 1 and not config['guards']['enforce']`: record `guard.would_refuse` (no area, level, posture), warn, raise |
| `guards/commit_push.py:146-152` tag push | refused under strict | `continue` always (the deploy guard's Owner step card) |
| `commands/git_hook.py:14-15,58` worktree hooks | `STRICT` refusal | `STRICT` and the branch deleted; the warning stays |
| `commands/git_hook.py:98-101` pre-push missing check | refused under strict | warning always |
| `guards/protect_state.py:202-207` `check_scratch` | seats level | `return 1, reason` (the hook decides) |
| `guards/traces.py:98-104,176-178` `_strict` | refuses under strict | `_strict` deleted; `return 0, ''` |
| `guards/outward.py:207-230` `_unmatched` unknown tool | outward level | the warn branch only: record `outward.unknown_tool` once (no `posture` field) and pass; the block branch goes |
| `guards/lifecycle.py:58` | `orientation(row, posture, ...)` | `orientation(row, config['guards']['enforce'], ...)` |
| `commands/next.py:12-24` `POSTURES` | three orientation texts | `ENFORCE = {True: ..., False: ...}` (two sentences) |
| `commands/next.py:445,464` `orientation` | `posture` argument | `enforce` argument |
| `commands/next.py:160-161` | `init --shadow` in the observe posture | text: "with guards logging only" |
| `commands/config.py:99-112` | posture, areas and mcp block lines | one `Guards:` line; the `scanner.mcp.block` line without a posture |
| `commands/doctor.py:422-458` `SHADOW`, posture row | countdown and shadow fix | one `guards` row, ok in both settings |
| `commands/doctor.py:393-397` outbound tiers rows | strict text | the non-strict text (part 16 deletes the row) |
| `commands/status.py:237,346-347` | `posture` in JSON and the line | `enforce` in JSON; `observe` in the line when false |
| `commands/seat.py:60-64` seat stop | Owner step card under strict | branch deleted; the planner session check stays |
| `commands/init.py:32-34,41-44,71-78` `--posture`, `--shadow` | write the posture | `--posture` deleted; `--shadow` replaces `enforce = true` with `enforce = false` in the staged template |
| `commands/init.py:224-248` `_retired_mode` | `guards.mode` rewrite | replaced by `_enforce(raw, before)` (FR-007) |
| `commands/init.py:213` `_today_tier` | reads the old `security.posture` | unchanged: reads the file being migrated (`before`), the allowed exception |
| `commands/why.py:238-239` | `posture:` line | deleted |
| `commands/event.py:26` | "shadow mode" producer text | `wuwei hook (guards.enforce = false) or wuwei pr raise` |
| `commands/outbound.py:83-87` `tiers` | marks rows ignored under strict | the mark goes (part 16 deletes the command) |
| `commands/outbound.py:546-548` `learn` | strict forces the card | `strict` term deleted (part 16 deletes the command) |
| `outward.py:571` `decide` | strict ignores owner send rows to clients | `strict` term deleted (part 16 deletes `decide`) |
| `outward.py:822-830` `check_lint` internal word | refused under strict | branch deleted; `word` computation goes with it |
| `drafts.py:208-213` card order | strict recommends keep | `strict` term deleted (part 16 deletes the module) |
| `drafts.py:321,327` approve | strict always prompts | `strict` term deleted; the non-strict path stays until part 16 |
| `tracker.py:97-107` missing ticket reason | host-terminal text under strict | the card text only |
| `tracker.py:128-135` `_held` | host-terminal text under strict | the card text only |
| `tracker.py:351-355` `creates_labels` | not under strict | `not outward._external_tracker(config)` |
| `plan.py:428,542` ticket creation | skipped under strict | the condition drops the posture term |
| `sessions.py:38-48` `gate_topics` | strict asks nothing | branch deleted; docstring trimmed |
| `scanner.py:60-80,123,130` `_trace_response` | strict pages an unknown session | the `posture` parameter goes; unknown sessions note `traces.unmatched` without a `posture` field |
| `brief.py:569-583` counterpart reference | refused under strict | `strict` deleted; the error is skipped as below strict |
| `specmode.py:196` `mode` | advisory under observe | `or not config['guards']['enforce']` |
| `signal.py:48-49` | warn by `posture` field | `guard.would_refuse` silent, `traces.unmatched` warn |
| `telemetry.py:214,380,407,410` | `workspace.posture(config)[0]` | `'guarded' if config['guards']['enforce'] else 'observe'` (one helper line); the record shape, `AREAS` and `POSTURES` stay (owner: telemetry untouched) |
| `report.py:12,154-156` `## Shadow` | lists `guard.would_refuse` | unchanged |
| `shell.py:700` | comment "in every posture" | reword |

## The hook after the change (`commands/hook.py`)

```python
def enforce(payload, refusals, root, warned=None):
    """Per refusal: blocks when guards.enforce is on or the refusal is on the floor; else
    records guard.would_refuse and lets the call through (#837). Unreadable config: blocks."""
```

- Read `config['guards']['enforce']`; on any error return every refusal enforced (as today).
- Keep the `UNPARSED`, `WORKSPACE_ROOT` and `UNKNOWN_GIT` once-per-call warn, and the opaque
  Bash publish UNRUN warning, in their below-strict form (no `name == 'strict'` term).
- Else `if on or floor(check, reason)`: enforce with the reason alone. Else append
  `guard.would_refuse` with `guard`, `reason`, `exit`, `target`, `session`, `item`, and the
  launch warning to `warned`. A failed record enforces, as today.
- The draft line (`a draft is one card away`), the publish line, the owner-only line and the
  records floor line go: reasons carry no posture line.

`guards/__init__.py`:

```python
# Blocks whatever guards.enforce says (constitution VII): records written by the workflow,
# and the owner's merge, approve, admin, deploy and held-send edges.
FLOOR = frozenset({'answers', 'lifecycle', 'verdict', 'deploy', 'protect_state.check_file',
                   'protect_state.check_bash', 'outward.check_tier'})

def floor(check, reason):
    module = check.__module__.rsplit('.', 1)[-1]
    return (module in FLOOR or f'{module}.{getattr(check, "__name__", "")}' in FLOOR
            or reason.startswith(MERGE + RECORDS_FLOOR))
```

Comments on `MERGE`, `RECORDS_FLOOR` and `OWNER_ONLY` (lines 44-62) are rewritten to name the
floor.

## init --upgrade (`commands/init.py`)

- `_retired_mode` is replaced by `_enforce(raw, before)`, called where it is called today (406)
  with `tomllib.loads(text)` as `before`, because `_unread_keys` has already removed the
  retired keys from `raw`:
  - `was = 'security.posture = "observe"'` when `before['security']['posture'] == 'observe'`,
    else `'guards.mode = "shadow"'` when `before['guards']['mode'] == 'shadow'`, else nothing;
  - skip when `'enforce' in before.get('guards', {})` (the owner's value stays);
  - otherwise `raw = config.write_value(raw, 'guards.enforce', False)` and return
    `[f'guards.enforce = false (was {was})']`.
- `workspace.RETIRED` names the five keys, so `_unread_keys` removes them with
  `remove <key> (no longer read)`, honouring `--dry-run` and `integrity.newer_template`.
- Edge: under `integrity.newer_template` nothing is pruned and `_enforce` still writes the
  mapping; `load_config` warns the old keys as unknown, which is the #799 behaviour.

## RETIRED

`workspace.RETIRED` gains `'security.posture'`, `'security.areas'`, `'guards.mode'`,
`'guards.shadow_days'`, `'guards.shadow_since'`.

## Files to delete (1)

- `tests/test_posture.py`: its posture-only cases go. Its hook-chain cases (one reason, most
  specific first, integrity last, SessionStart unchanged, reads pass, opaque warnings and the
  records floor, the warned launch shown to the session) and the `fixed` helper move to a new
  `tests/test_enforce.py` (T001), and `tests/test_invariants.py` imports `fixed` from there.

## Files to edit, code (35)

`cli/wuwei/workspace.py`, `guards/__init__.py`, `commands/hook.py`, `guards/agent_launch.py`,
`guards/pr.py`, `guards/commit_push.py`, `guards/protect_state.py`, `guards/traces.py`,
`guards/outward.py`, `guards/lifecycle.py`, `mcp.py`, `shepherd.py`, `commands/git_hook.py`,
`commands/next.py`, `commands/config.py`, `commands/doctor.py`, `commands/status.py`,
`commands/seat.py`, `commands/init.py`, `commands/why.py`, `commands/event.py`,
`commands/outbound.py`, `outward.py`, `drafts.py`, `tracker.py`, `plan.py`, `sessions.py`,
`scanner.py`, `brief.py`, `specmode.py`, `signal.py`, `telemetry.py`, `shell.py` (comment),
`templates/workspace/config.toml`, and `tests/test_reasons.py` (LEFT rows). What each changes
is in the reader table.

`templates/workspace/config.toml`:

- `[security]` keeps `required = true` and loses the posture comment block, `posture` and the
  `[security.areas]` comment (275-283).
- `[guards]` becomes `enforce = true # false logs what the guards would refuse and lets the call
  through; records, merges, deploys and held sends still refuse. init --shadow starts here.`
  (285-287).
- The `scanner.mcp.block` comment (136-138) and the `outbound.learn` comment (211) drop the
  posture words.

`tests/test_reasons.py` LEFT: delete the three `tracker.py` rows tagged 16
(`drafts approve {draft} in a host terminal`, `ticket=<id> in a host terminal`,
`drafts approve {draft_id} in a host terminal`); their strict-only texts go here.

## Files to edit, governance and docs (5)

- `.specify/memory/constitution.md` VII: replace the Autonomy sentence with: "Autonomy (owner,
  2026-10-05, #530; one switch, 2026-10-11, #837): a guard refusal names the plain form the seat
  runs itself or the card that asks the owner. With `guards.enforce = false` a guard logs what
  it would refuse and lets the call through, with one floor: records are written by the
  workflow and answered by the owner, and merge, approval, admin, deploy and held outward sends
  stay the owner's." Keep the merge-policy sentence. Version 2.2.0, Last Amended 2026-10-11,
  dated amendment line in the commit message.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 4.1 rows 171-173: drop "under strict" and "below strict" clauses; launch and recorded-item
    `gh pr create` refuse; missing fast check warns;
  - 4.1 / 4.2.1 line 230 and 4.3 line 254: drop the strict sentences;
  - 4.5 lines 269-271: the opaque command warns ("below strict" goes);
  - 5.9 line 744, 5.10 lines 763-764 (`guards.enforce = false` runs strict as advisory),
    5.11 line 1214, 7 lines 1416-1419 and 1428 (the MCP gate blocks at `scanner.mcp.block`
    with enforce on);
  - 5.13 lines 919, 985, 996, 1027: `config.posture` reports `guarded` or `observe` from
    `guards.enforce` (the field stays for stored weeks);
  - 9.1 lines 1534-1562: replace the posture block, the area table and the floors with
    "Enforcement (owner, 2026-10-11, #837)": the switch, the floor list, the warn-once cases;
    line 1572 drops "under strict" and "under every posture";
  - 9.2 lines 1589, 1592: PR raise refuses a bare `gh pr create` for a recorded item; the
    no-wall note names `guards.enforce`.
- `docs/site/configuration.md` (a test forces it): the table index (11) drops
  `[security.areas]`; rows 44-49 become one `guards.enforce` row and `security.required` stays;
  row 50 drops the strict clause; row 103 says `guards.enforce = false`; 432-441 drop the
  posture default text.
- `docs/site/reference.md:31`: `init` row names `--shadow` (`guards.enforce = false`), not
  `--posture`.

Deferred to part 24 (docs only, no test forces them): the posture sections and lines of
`docs/site/security.md` (40-82, 86), `concepts.md` (155-163, 208, 231-233), `daily.md` (30,
96-102, 137, 228, 269, 275, 319, 341), `reference.md` (60, 193, 208, 218, 231, 261, 290, 298,
300, 374-392), `recovery.md`, `adapters.md` (100, 114-115), `index.md` (43, 46) and
`README.md` (32, 34, 67, 107, 112, 153, 162, 192, 194). charters, agents, skills, hooks.json,
`.github` and `scripts/` carry no posture text.

## Files to edit, tests (about 48)

Every per-file posture writer (`[security] posture = ...`, `[security.areas]`, `guards.mode`)
becomes `[guards]\nenforce = false` where the case is the observe one, or is dropped where the
case is the default. Cases that only exist to pin strict-only behaviour are deleted with that
behaviour; cases that pin a guarded default stay unchanged.

- New `tests/test_enforce.py` (T001): the hook table over one refusal per guard module for
  enforce true and false; the floor cases; the moved hook-chain cases; the default is true.
- `tests/test_hooks.py` 1192-1495: `shadow_mode` and `set_posture` become one `enforce(root,
  value)` helper; `warns` no longer patches `guards.AREAS`; delete
  `test_posture_levels_at_the_hook`, `test_missing_reviewer_refusal_carries_no_posture_line`,
  `test_held_draft_posture_line_names_the_card`; keep the shadow-mode cases as enforce = false;
  the unparsed and unknown git cases expect a warning in both settings.
- `tests/test_invariants.py`: `test_reason_corpus_has_no_wall` loops `enforce in (True,
  False)`, calls `hook.enforce`, and drops the `posture: records =` line check; import `fixed`
  from `test_enforce`.
- `tests/test_parser_warns.py`: parametrize on `enforce` (True, False) instead of `POSTURES`;
  the strict expectations (opaque refused) go; floor cases block in both.
- `tests/test_shadow.py`: `test_status_shows_posture` becomes `enforce` cases (JSON `enforce`,
  ` · observe` in the line); `test_session_start_says_observe_is_on` reads the enforce = false
  sentence; the `## Shadow` and retired-command cases stay.
- `tests/test_workspace.py`: `test_init_posture` (98) becomes `--shadow` writes enforce = false
  and `--posture` is unknown; `test_config_defaults_and_independence` (224) drops `areas`;
  `test_guards_mode` (436) and the shadow upgrade cases (1320, 1386, 1393, 1406) become the
  `_enforce` mapping cases of US2; `test_upgrade_from_a_seat_under_strict_creates_no_label`
  (1462) is deleted with the strict term in `creates_labels`.
- `tests/test_config_transition.py`: the observe and shadow mapping cases with `--dry-run`
  (US2); `test_tool_calls_pass_in_every_posture` (84) loops enforce.
- `tests/test_doctor.py`: `test_workspace_calibration_and_shadow` (452) and
  `test_workspace_retired_shadow_mode` (489) become the `guards` row cases; the
  `test_fix_applies_only_the_allow_list` shadow fix (887) goes; `test_init_shadow_without_workspace`
  (1078) stays; `test_outbound_tier_rows` (1245) drops the strict case.
- `tests/test_mcp.py`: `test_strict_blocks_critical_and_high` (378) and the `off` cases
  (`test_posture_block_table` 957 rows for strict and off, `test_mcp_off_is_not_checked` 995)
  go; guarded cases become enforce on, observe cases enforce off.
- `tests/test_agent_launch.py`: `set_posture` (700) becomes `enforce`; the brief-line and brief
  mismatch cases refuse by default (US4.1, US4.2); `test_strict_refuses_unrecorded_untyped_launch`
  (757) goes; `test_unbriefed_typed_launch_registers_an_adhoc_seat` (958) runs with enforce =
  false; `test_strict_refuses_an_unbriefed_typed_launch` (983) becomes the default case.
- `tests/test_pr_guards.py`: `test_create_for_a_recorded_item_is_refused_under_strict` (806)
  becomes the default case; the observe chained create case (853) uses enforce = false and
  still refuses on the floor for a merge.
- `tests/test_traces.py` (801-960): every below-strict warning case runs with the default; the
  `refuses_only_under_strict` and `unreadable_config_keeps_the_refusal` cases become "never
  refuses" (US3).
- `tests/test_traces_seats_only.py`: `make(posture=...)` becomes `make(enforce=...)`;
  `test_shadow_mode_is_observe` (89) goes; strict page rows go.
- `tests/test_tracker.py`: `config()` (12) drops `guards.mode` and `security`; `STRICT` and its
  cases (27, 199) go; `test_creates_labels_by_posture_and_owner` (435) keeps the external cases.
- `tests/test_commit_push.py` (853-921), `tests/test_git_hook.py` (73-94),
  `tests/test_fast_checks.py` (29-31), `tests/test_worktree_command.py` (334): strict cases go;
  the warning cases stay.
- `tests/test_headless_shepherd.py` (367-393), `tests/test_handback.py` (363-383),
  `tests/test_card_confirms.py` (27-28, 89), `tests/test_owner_edits.py` (39-128),
  `tests/test_drafts.py` (129-816), `tests/test_outbound_learn.py` (58-628),
  `tests/test_outbound.py` (516-528), `tests/test_outward.py` (590, 1147-1228, 1658-1672,
  2002-2013): strict cases go; observe cases use enforce = false.
- `tests/test_shepherd.py` (955-985): `gate_miss` takes `enforce`.
- `tests/test_protect_state.py` (797-1009): `_posture` becomes `enforce`; the scratch case
  refuses by default and logs with enforce = false.
- `tests/test_path_day.py` (196) `test_posture_day` becomes `test_enforce_day` (True, False),
  and `tests/test_dev_cycle.py:23` names the new test.
- `tests/test_e2e_day.py` (252): the shadow case writes enforce = false.
- `tests/test_brief.py` (458, 808), `tests/test_build_next.py` (502-545),
  `tests/test_dispatch.py` (1598-1635, 2359-2378), `tests/test_plan.py` (681-762),
  `tests/test_intraday_intake.py` (302-352), `tests/test_deploy.py` (545),
  `tests/test_spec_mode.py` (142-147, 417), `tests/test_scope_first.py` (193),
  `tests/test_seat_command_forms.py` (45-108), `tests/test_watch.py` (866): strict cases go,
  observe cases use enforce = false, the rest drop the posture lines.
- `tests/test_next.py` (92-465): orientation asserts the two sentences.
- `tests/test_signal_status.py` (346, 741, 786, 885): `enforce` key, ` · observe`.
- `tests/test_why.py` (324-334): the posture line case goes.
- `tests/test_telemetry.py` (131-135, 488-502): `telemetry.AREAS == workspace.AREAS` and the
  `POSTURES` pin go (the source is gone); the span attribute reads the mapped label.
- `tests/test_answers.py:109`: the `guards.AREAS` pin becomes `'answers' in guards.FLOOR`.
- `tests/test_profiles.py:33-34`: the lint blocks by default; drop the strict writer.

## Risks

- New blocks for workspaces on the guarded default (spec Assumption 2): seat launch refusals,
  the outward lint, scratch, and a bare `gh pr create` for a recorded item. They name their
  accepted form; `next` and `pr raise` already route around them.
- Strict users lose the strict-only refusals (Assumption 3). The floor and the table rows keep
  the process checks.
- Many tests write posture configs by hand. The builder converts them file by file and runs
  each touched file; CI runs the suite.
- Part 16 deletes most of `drafts.py`, `outbound.py` and `outward.py` next; keep this part's
  edits there to the posture reads only.

## Handoff to part 16

- `outward.check_tier` is on the floor. Part 16's allowlist check replaces it and keeps the
  floor key under its new name.
- The `drafts.py` LEFT row stays (its non-strict terminal path remains until part 16).
