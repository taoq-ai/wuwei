# Implementation Plan: delete the setup interview, profiles and calibration cards; the host measure moves into dispatch

**Branch**: `b4-setup-records` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at 9639dd8, the batch base (batches 1 to 3 and #831 applied). This is part 12,
the first of batch 4. Parts 13 (#833) and 14 (#834) follow on this branch and assume this part
is done.

## Summary

Delete `wuwei setup`, `wuwei calibrate`, the owner interview, calibration profiles and the
fast-checks card. Move the config edit frame from `commands/setup.py` into
`commands/config.py`. Move the host measure (`calibrate.host`) into `dispatch.py` unchanged.
`wuwei next` gates the day only on a workspace and a repository, and never names a host
terminal. The repository survey stays behind `config promote`.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion, plus one function move and one
module merge. Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: the host measure keeps its unmeasured fallback (exit-free, never clean). `config
  promote` keeps its 0, 1 and 2 exits.
- III: CAP and the seat ceiling stay one function (`dispatch.host`) with its tests. Config
  writes stay one frame (`commands/config.py:_edit` and `offer`).
- IV: tasks.md writes the red tests first for the `next` rows, the strict build and the
  doctor rows. The host tests move first and must stay green.
- V: about 2,500 lines of code and 2,800 lines of tests go.
- VII: no guard changes. No owner step loses its card: `config set`, `add-repo` and
  `promote` keep `sessions.needs_owner`.
- Design spec ownership: the edits are part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| `calibrate.host`, `processes`, `SEAT_MIB`, `_gb` | (b) CAP and the seat ceiling: `next` never offers a launch past CAP, and the launch guard refuses one | moved unchanged into `dispatch.py` as `dispatch.host` (the pass plan table row "CAP and host seats") |
| `wuwei setup` (discover, interview, measure prompt, proposal, Slack, status line, allowlist, watch offer, `ending`) | (a) a host-terminal flow the model relays and the owner answers on stdin | `init`, `config add-repo`, `config set`, `config promote`, each on its Owner step card where it writes config |
| The interview (`interview.py`, `calibrate --interview/--questions/--answer`, the `calibrate` row in `next`, the doctor `interview` row, the `init --upgrade` count) | (a) the model reasons about which questions are open and relays them daily | `config set <key> <value>` on its card, when the owner wants a value |
| Calibration profiles (`profiles.py`, `calibrate export/import`, `templates/profiles/`, the doctor `profile` row) | (a) | nowhere |
| The fast-checks card (`propose_checks`, `checks_*`, `_record`, `CHECKS`, `NOTHING`) and the strict refusal in `build._repo` | (a) a card the model writes and the owner answers before a build | `config promote` proposes detected checks; no fast checks is a state, and CI and the gates are the evidence (#600) |
| `.wuwei/calibration.json` gating `next` | (a) the drift baseline used as a day gate | `doctor` warns `never applied`, fix `wuwei config promote` |
| `calibrate` (survey, `report`, `charter_proposals`, `commit_style`, `bot_authors`) | (a) the owner-facing report and charter blocks of a deleted command | the survey and drift stay behind `config promote` and the steward |
| `interview.reask` (retro `## Owner preferences`) | (a) | nowhere; the retro proposal and promotion path is unchanged |
| `brief.mandate` trust-surface line from the interview block | (a) | nowhere; the mandate keeps the deploy-deny line |
| `init.allow`, `allow_rules`, `ALLOW`, `init.status_line` | (a) convenience writers setup and the allowlist answer called | `init` still prints the status line JSON |
| `specmode.detect`, `docs.detect`, `docs.LINKS` | (a) setup's engine and docs suggestions | nowhere |

No (b) check is lost. The one (b) unit, the host measure, moves unchanged.

## Files to delete (7)

- `cli/wuwei/commands/setup.py` (the kept functions move first, see `commands/config.py`)
- `cli/wuwei/commands/calibrate.py`
- `cli/wuwei/interview.py`
- `cli/wuwei/profiles.py`
- `templates/profiles/cli-tool.json`
- `templates/profiles/python-library.json` (and the then empty `templates/profiles/`)
- `tests/test_interview.py`

## Files to edit, code (23)

### `cli/wuwei/commands/config.py`

- Move from `commands/setup.py`, unchanged: `KEY`, `IDENTITY`, `_edit`, `card_write`,
  `_settle`, `_parts`, `write_value`, `effective`, `changed`, `merged`, `_choice`,
  `assignment`, `declared`, `_from_card`, `set_value`, `repo_tables` and `add_repo`. Add the
  imports they need (`difflib`, `json`, `re`, `tomllib`, `Namespace`, `calibrate`,
  `references`). `register` drops `from wuwei.commands import setup` and binds `set_value` and
  `add_repo` directly; `show` uses `effective` directly.
- `set_value`: the `--from-card` path stays as moved (part 14 deletes it).
- `proposal(root, raw, base, config, results, extra=(), keys=None)` becomes
  `proposal(root, raw, config, results)`: no `interview`, `profiles`, `extra`, `keys`,
  `skipped` or `missing`. Text: `calibrate.propose(raw, results)`; summary: the diff,
  `Config differs; edit by hand`, `Flagged`, `CI only` and the snapshot lines.
- `promote`: delete the `--keys` branch and the `--keys` argument (the mutually exclusive group
  becomes one `--measure` argument). Call `proposal(root, raw, config, results)`.
- `read` docstring unchanged.

### `cli/wuwei/calibrate.py`

- Delete: `CONVENTIONAL`, `SCOPE`, `commit_style`, `SEAT_MIB`, `_gb`, `processes`, `host`
  (moved), `charter_proposals`, `CHECKS`, `NOTHING`, `_record`, `checks_text`,
  `checks_record`, `checks_answered`, `propose_checks`, `bot_authors`, `kept`, `SECTIONS`,
  `LABELS`, `_label`, `report`.
- `survey(root, config, selected, *, measure=False)`: drop `style`, the vcs port and
  `result['style']`; drop `result['bots']`.
- `propose(raw, results)`: drop `settings` and the `settle` pass after `apply`.
- `UNMEASURED` (153): `run bin/wuwei config promote --measure`.
- Drop the imports that become unused (`Counter`; `os` if no other user; `statistics` stays
  for `baseline`).
- Keep: detectors, `instruction_like`, `SAFE`, `classify`, `NEAR`, `_workflows`,
  `_workflow`, `profile`, `deploys`, `drift_facts`, `baseline`, `_table`, `_labelled`,
  `_empty_list`, `proposal`, `apply`, `NO_REPOS`, `_port`, `measure_checks`, `survey`,
  `proposed`, `ci_only`, `grows`, `settle`, `propose`, `approved`, `drift`, `COMMENT`,
  `LAYOUT`.

### `cli/wuwei/dispatch.py`

- Add `SEAT_MIB`, `_gb`, `processes` and `host` from `calibrate.py:502-592`, unchanged, after
  `ROLES`. Inside `host` drop `from wuwei.dispatch import ROLES` (module scope now). Add
  `import os` and `import statistics`. The unmeasured text (`run bin/wuwei calibrate again`)
  becomes `run bin/wuwei doctor, then retry`.
- 507-511 and 958-960: `host(...)` instead of `calibrate.host(...)`; drop the imports.

### `cli/wuwei/plan.py`

- 254-256: `from wuwei.dispatch import host` and `host(root, config, policy=...)`.

### `cli/wuwei/commands/plan.py`

- 66-67: `from wuwei.dispatch import host`; `host(root, workspace.load_config(root))['cap']`.

### `cli/wuwei/guards/agent_launch.py`

- 289-290: `from wuwei.dispatch import host  # lazy: hook path (#346); #528: derived at launch`
  and `host(...)`.

### `cli/wuwei/commands/next.py`

- `THEN`: delete `'calibrate'`. Add `'setup': 'Ask the owner which repositories WUWEI works on
  (owner/repo, path, default branch); run the command for each, which asks its Owner step
  card; then run wuwei next.'`
- `step` 165-178: the `no-workspace` row becomes
  `_row('no-workspace', 'No WUWEI workspace here; create one in the observe posture in the project directory.', 'bin/wuwei init --shadow')`.
  The calibration comment and condition go. The `setup` row becomes
  `if not config['repos']: return _row('setup', 'No repository is configured yet.', 'wuwei config add-repo --name <owner/repo> --path <path> --branch <branch>', then=THEN['setup'])`.
- 215-217: delete the `calibrate` row.
- Drop `import json` only if no other use remains.

### `cli/wuwei/commands/doctor.py`

- `_host` 239: `"not set globally; repositories set their own"` for both branches (the
  `root is None` text names setup).
- `_workspace` 276: the fix becomes `bin/wuwei init --shadow in the directory that holds your
  repositories`.
- `_calibration` (438-487): import only `calibrate` and `watch`. The never-applied fix is
  `wuwei config promote`. The drift row fix is `wuwei config promote`, with no `apply`.
  Delete the `interview` and `profile` rows. Telemetry row: value
  `sharing not chosen yet`, fix
  `bin/wuwei config set telemetry.share '"anonymous"' (or "attributed" or "off")`. Check the
  person-facing lint: no "the owner".
- `_pr_flow` 577-579: the `shepherd.authors` fix drops `bin/wuwei setup (maps your git email
  and the bot authors), or `; it starts `add "<email>" = {login = ...} under [shepherd.authors]`.
- Delete `_calibrate` (917-920) and the `calibrate` FIXES entry (943-945).

### `cli/wuwei/commands/init.py`

- 258-262: `from wuwei.commands.config import write_value`.
- 89: `_status_line(executable)` unconditionally (`status_line` was only setup's argument).
- Delete `ALLOW`, `allow_rules`, `allow` and `status_line` (127-171). Keep `settings`
  (`run` uses it at 53).
- 549-556: delete the unanswered-questions block.

### `cli/wuwei/commands/build.py`

- `_repo` 108-115: delete the strict fast-checks refusal, its comment and the `calibrate`
  import.

### `cli/wuwei/brief.py`

- `mandate` 119-143: drop `from wuwei.interview import BLOCK`, `lead`, `risk` and the
  `Trust surface:` sentence. Keep the deploy-deny sentence.

### `cli/wuwei/retro.py`

- 155-156: delete the `## Owner preferences` lines.

### `cli/wuwei/decision.py`

- 128: `from wuwei.commands.agents import ROLES`.
- 162, 273: import `assignment` and `declared` from `wuwei.commands.config`.

### `cli/wuwei/tracker.py`

- Add `ABSOLUTE` (moved from `profiles.py:41`, with its ponytail comment). 138, 175, 274, 307:
  use the local `ABSOLUTE`; drop the `profiles` imports.
- Docstrings 349 and 391: "init --upgrade" without "setup and".

### `cli/wuwei/commands/note.py`

- 29, 39: `from wuwei.tracker import ABSOLUTE` (part 13 deletes the module).

### `cli/wuwei/commands/telemetry.py`, `cli/wuwei/drafts.py`, `cli/wuwei/commands/outbound.py`

- Import from `wuwei.commands.config` instead of `setup` (`set_value`; `_settle`, `_edit`;
  `merged`, `_settle`, `_edit`).

### `cli/wuwei/commands/event.py`

- 91: `'config.set': 'wuwei config set --from-card'` (part 14 handles `--from-card`).

### `cli/wuwei/guards/protect_state.py`

- 89: drop `'interview.json'` and `'profile.json'` from the protected day files.

### `cli/wuwei/specmode.py`, `cli/wuwei/docs.py`

- Delete `specmode.detect` (403-406), `docs.LINKS` and `docs.detect` (366-381).

### `templates/workspace/config.toml`

- 6: `init and init --upgrade set it`.
- 229: drop `Setup proposes it.`
- 305: `init --shadow starts here`.

## Files to edit, tests (21)

- `tests/test_calibrate.py`:
  - Move to `tests/test_dispatch.py` (with the `ports` and `workspace_root` fixtures, or
    import them from `test_calibrate`), calling `dispatch.host` and `dispatch.processes`:
    `test_host_derives_cap_and_seats`, `test_host_seat_ceiling_holds_one_gate_on_a_two_core_host`,
    `test_host_falls_back_when_a_past_day_log_is_damaged` (expect the new unmeasured text),
    `test_token_budget_bounds_cap`, `test_runtime_rule`, `test_subagent_seats_never_read_memory`,
    `test_memory_rule_takes_the_median_of_five`, and the helper above 1121.
  - Delete with the code: `test_commit_style`, `test_charter_proposals_use_only_paths_phrases_and_commands`,
    `test_charter_proposal_lands_through_promote`, every test that runs `wuwei calibrate` or
    `commands.calibrate` (452-596 and 1209, 1379), every profile test (768-1107),
    `test_record_defaults_are_unchanged`, `test_checks_text_is_a_routine_value_card`,
    `test_checks_record_and_answered`. Where a deleted command test is the only cover of a
    survey behaviour `config promote` keeps (the `Flagged` line, the `CI only` line), port it
    to `config promote` instead.
  - `test_survey_keeps_bot_authors`: rename `test_survey_reads_the_pr_baseline`; drop the
    `bots` assertions and `style=False`.
  - The `config promote` tests (597-678): drop `--keys` cases; keep the rest.
- `tests/test_dispatch.py`: receives the host tests above.
- `tests/test_setup.py`: `git mv` to `tests/test_config_set.py`. Keep 1-210 and 1154-1244
  (config set, add-repo, list set, config show). Delete every setup, discovery, identity,
  Slack, status line and `ending` test (270-1153). The module fixture imports
  `wuwei.commands.config`.
- `tests/test_config_writer.py` 172, 242, 250: import from `wuwei.commands.config`.
- `tests/test_card_confirms.py`: delete phase 2 (117-260), the fast-checks card cases
  (503-560) and `test_calibrate_answer_without_the_session_id` (609). 300: import from
  `wuwei.commands.config`. 427: expect `wuwei config set --from-card`.
- `tests/test_next.py`: `calibrated` writes only the repository (no calibration.json needed);
  `approved` drops `seen(root, 'calibrate')`. Rewrite `test_setup_rows` (US2.2, US2.3) and
  `test_setup_row_outside_workspace` (US2.1) red first. 186-196: drop the `calibrate` card step.
  Delete `test_unanswered_setup_questions_are_asked_on_any_day`.
- `tests/test_doctor.py`: 128-133 helper goes. 190: FIXES without `calibrate`. 301:
  `init --shadow`. 312-313: drop `interview` and `profile`. 463-468: the drift fix is
  `wuwei config promote` and `apply` is absent. Delete 488-500. 504-508: the new telemetry
  value and fix. 814: the `shepherd.authors` fix starts `add "<email>"`. 1050-1096: use
  `watch-install` where `calibrate` was. 1168-1179: the new fix and identity texts. 1183, 1192:
  drop the `setup.ending` line.
- `tests/test_build_next.py` 548-554: replace with `test_strict_builds_without_fast_checks`
  (US4.5), red first.
- `tests/test_brief.py` 467: `test_mandate_names_deploy_deny`; drop the interview block and the
  trust-surface assertion.
- `tests/test_hooks.py` 438: the set is `{"wuwei.calibrate"}`.
- `tests/test_reasons.py`: `PERSON_MODULES = ('commands/doctor.py', 'commands/config.py')`
  (the moved owner-edit text stays person-facing; fix any config.py text the lint then flags by
  saying "you"). Delete the LEFT rows for part 12 (324-330).
- `tests/test_tone.py`: drop the `interview` import, the `interview.QUESTIONS` loop in `_cards`
  and the interview card in `test_three_fixture_cards_read_at_the_rule`. Re-measure the
  `cards` budget; never raise it. If the rate rises above 3.1 after the removal, rewrite the
  offending card text, not the budget.
- `tests/test_outward.py` 956: drop `'interview.py'`.
- `tests/test_profiles.py` 294-295: delete the `profiles.PRIVATE` test.
- `tests/test_protect_state.py` 721-722: delete `test_interview_answers_are_protected`.
- `tests/test_workspace.py` 1656-1673: delete the unanswered-count case; 1692-1728: delete the
  `allow_rules` and `allow` cases.
- `tests/test_path_day.py`: `prepare` drops the interview.json fixture; `test_posture_day`
  writes the autonomy answer's keys into config per `choice` (Autonomous: `security.posture =
  "observe"`, `outbound.default_tier = "send"`, `outbound.learn = "auto"`,
  `autonomy.mode = "autonomous"`; Supervised: `"guarded"`, `"ask"`, `"card"`,
  `"supervised"`) and drops the `calibrate` card branch; the answered states assert becomes
  `['gate']`. 339-345: drop the interview.json write.
- `tests/test_parallel_dispatch.py` 87: drop the `calibrate` loop; 150: drop the
  `'calibrate' in row` assertion (the sentence it pins is deleted).
- `tests/test_report_retro.py` 45: drop the `## Owner preferences` assertion.
- `tests/test_spec_mode.py` 343-349 and `tests/test_docs_system.py` 514-515: delete the
  `detect` cases.

## Files to edit, governance and docs (13)

- `skills/wuwei-plan/SKILL.md` 16: the last two sentences become "A config value the owner
  changes (CAP, `host.seats` or any other key): run `wuwei config set <key> <value>`; it asks
  its Owner step card." Drop the `Value:` rows, `Previous:` and "Never run config set without a
  card" sentences.
- `skills/wuwei-retro/SKILL.md` 10 and `skills/wuwei-consolidate/SKILL.md` 10: drop
  `or wuwei calibrate --questions` from the widget list.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 474: "generated from `autonomy.mode`" (drop the interview answers); 478: drop "the
    interview's trust-surface areas and".
  - 487-501: drop `calibrate --answer` for an interview card; the last two sentences end at
    "CI and the gates are the evidence."
  - 506: unchanged ("calibration" is `config promote --measure`, still a background command).
  - 1022-1028: "`wuwei doctor` looks for each engine ..."; drop the setup and interview
    sentence and the `wuwei calibrate` sentence (the survey still reads the constitution).
  - 1045-1047: "Set by the owner with `bin/wuwei config set telemetry.share` or by `wuwei
    telemetry off`." Drop the profile sentence. 1211: "turning sharing on is the owner's
    (`config set`)". Delete the "Interview." paragraph 1215-1222.
  - 1251, 1375-1382, 1402, 1498-1500: drop the setup and interview clauses (the tracker,
    docs and doctor sentences stay).
- `docs/site/reference.md`: delete the `calibrate` (14) and `setup` (55, 439) rows; 220: drop
  calibration interview and profiles from the doctor list (keep calibration); 246: drop
  setup; 265: delete the `calibrate` fix row. `config` row (16): `promote`, `set`, `add-repo`
  ask on a card.
- `docs/site/configuration.md`: 3 (config set and add-repo ask on a card, no host terminal),
  27 (drop the `bin/wuwei calibrate` sentence), 28, 48, 50 (`init --shadow`), 58, 70
  (`config promote --measure`), 124, 172, 201, 403. 301-331 Calibration: `config promote`
  runs the survey and asks its card; drop setup and `bin/wuwei calibrate`. Delete Owner
  interview (333-363) and Calibration profiles (365-377).
- `docs/site/daily.md` section 2 (46-195): replace the setup walkthrough with: `bin/wuwei init
  --shadow` in the project directory; then in the session the planner runs `config add-repo`
  for each repository and `config promote`, each asking its Owner step card; then
  `bin/wuwei doctor`. 22-40: the same `init --shadow` line, without a host terminal.
- `docs/site/index.md` 38-52, `docs/site/concepts.md` 34, 80, 94, 415,
  `docs/site/recovery.md` 55-64 (`config promote --measure`), `docs/site/security.md` 78,
  `docs/site/adapters.md` 97: drop setup, the interview and `bin/wuwei calibrate`.
- `README.md` 31-32, 58-67, 154-164, 196: `init --shadow` and `config promote`; no interview,
  no host terminal for setup.

No charter names these units; no agent rebuild is needed.

## RETIRED

None. The base has `workspace.RETIRED`; this part retires no key or table. No workspace file
is retired: the day files age out with the archive.

## Handoff

- Part 13 (#833): `commands/note.py` imports `ABSOLUTE` from `tracker`; delete the import with
  the module. `skills/wuwei-consolidate` was edited here and goes in part 13.
- Part 14 (#834): `card_write`, `_from_card`, `assignment` and `declared` now live in
  `commands/config.py`; delete them there with `--from-card`. `decision.py` imports `ROLES`
  from `commands.agents`. The wuwei-plan skill sentence on config values is already rewritten.

## Risks

- `tests/test_tone.py` `cards` budget: the interview texts leave the class. Re-measure; if the
  rate rises, fix card text, never the budget.
- `test_path_day` encodes the autonomy answer as config; check the derived posture and
  outbound values match the deleted choice exactly, or the day walk changes meaning.
- `next` no longer waits for `calibration.json`. A workspace that never ran `config promote`
  plans with the fast checks it has; `doctor` names the step.
- The allowlist writer goes. A new workspace gets permission prompts until the owner adds
  rules; this is a convenience loss, not a guard loss.
