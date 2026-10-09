# Implementation Plan: No fast checks is a state, not a wall

**Branch**: `600-checks-none` | **Spec**: `specs/600-checks-none/spec.md` | **Issue**: #600

## Summary

Remove the one refusal (`build._repo`) below strict and let the existing empty-list path
run: `fast_checks.commands` already returns `[]`, `build check` already completes on zero
results and the push evidence rule already passes. Name the state where people read it
(builder brief, `build.started`, status, doctor). Teach calibration to detect three more
sources and turn its result into one CLI-written decision record per repository, taken
under the mandate in autonomous mode and asked on a card otherwise. Give decision records
two optional fields, `Value:` (a table of `KEY = TOML` per option) and `Previous:`, so a
config card carries a list and `config set --from-card D-n` reads it. A record that sets a
config key and records its previous value is two-way (`undo.measured` kind `config`) and,
without a better class, `approach`; `mandate` leaves config records to the owner (#529).

## Technical Context

Python 3.11 stdlib, pytest for tests. Touched modules: `cli/wuwei/commands/build.py`,
`cli/wuwei/brief.py`, `cli/wuwei/commands/status.py`, `cli/wuwei/commands/doctor.py`,
`cli/wuwei/calibrate.py`, `cli/wuwei/commands/calibrate.py`, `cli/wuwei/decision.py`,
`cli/wuwei/commands/decision.py`, `cli/wuwei/undo.py`, `cli/wuwei/commands/setup.py`,
`cli/wuwei/commands/config.py`; docs: `docs/specs/2026-09-24-wuwei-design.md` (5.2 Records,
9.2), `skills/wuwei-plan/SKILL.md`, `docs/site/configuration.md`, `docs/site/recovery.md`.
Tests (run only these): `tests/test_build_next.py`, `tests/test_dispatch.py`,
`tests/test_brief.py`, `tests/test_signal_status.py` (status full), `tests/test_doctor.py`,
`tests/test_calibrate.py`, `tests/test_card_confirms.py`, `tests/test_decision.py`,
`tests/test_undo.py`, `tests/test_commit_push.py`, `tests/test_invariants.py`,
`tests/test_docs.py`.

## Constitution Check

- I stdlib only: yes; detection reads files, no subprocess.
- II three-state exits: `calibrate --questions` exits 0, or 2 with the reason when the
  record, its outcome or the config write fails; a missing checkout skips that repository
  with a stderr line (no proposal is safe). `config set --from-card` keeps exit 1 for a
  mismatch, 0 for a write or a nothing-to-write answer.
- III one behaviour, one function: the none state is `fast_checks.commands(...) == []`
  everywhere it is shown; the config-record rule lives in `undo.config_write`; the Value
  rows are read by `decision.values`; the write is `setup.card_write`.
- IV test first: each task pair in `tasks.md` is test then implementation.
- V ponytail: no new state key, no new event kind, no new hook code, no new config key.
  Reuse `decision.write`, `decision.seat_outcome`, `decision.route_owner`,
  `decision.record_widget`, `setup.card_write`, `setup.assignment`, `configtext.dumps`,
  `watch.days`, `calibrate.profile`, `owner_outcome`, `grants._record` (extended with
  keyword defaults, the `pace.propose_default` precedent).
- VII security and #530: one refusal removed below strict, none added; strict keeps its
  refusal and is cleared only by an owner outcome in CLI-written day state. A
  seat-written config record never writes config without the owner's card answer (I8
  unchanged): `mandate` skips it and `_from_card` still requires `card_answered`. The
  calibrate mandate write uses values the CLI computed in the same process, never a
  value read back from a seat-writable file.
- #551: `calibrate --questions` returns the card (supervised) or a done line (autonomous);
  the strict refusal and the `config set` session hint name the exact command.

## Design

### 1. The wall (US1, FR-001, FR-002)

- `cli/wuwei/commands/build.py` `_repo(root, tree, config)`: replace the unconditional raise
  with: when `not repo['fast_checks']` and `workspace.posture(config)[0] == 'strict'` and
  `not calibrate.checks_answered(root, repo['name'])`, raise `ValueError(f"posture strict:
  {name} has no fast checks and no answer on its fast-checks card; ask it with wuwei
  calibrate --questions --repo {name}, then rerun bin/wuwei build next <item>")`.
  Otherwise return the repo.
- `next_action`: pass `{'checks': 'none configured'}` as `extra` to the `build.started`
  `_save` when `repo['fast_checks']` is empty. `commands` stays `repo['fast_checks']` (`[]`).
- Unchanged and pinned by tests: `fast_checks.commands`, `fast_checks.record`,
  `build.check`, `build.complete_checks`, `build.stopped`, `commit_push.fast_evidence`,
  `dispatch.launch_set`.

### 2. Naming the state (US1.3, US2, FR-003, FR-004)

- One constant `NONE = 'fast checks: none configured; CI and the gates are the evidence'`
  in `cli/wuwei/fast_checks.py` (the module every reader already imports).
- `cli/wuwei/brief.py` builder header (`brief.py:425-436`): compute
  `checks = fast_checks.commands(root, config, repo, tree)`; when empty append
  `'Fast checks: none configured; CI and the gates are the evidence. Write "checks: none
  configured" in the PR body.'` and skip `checks_line`; else today's lines.
- `cli/wuwei/commands/doctor.py:327-332`: the empty case becomes
  `_row('workspace', f'{name} fast_checks', 'ok', fast_checks.NONE)` (no fix, no apply).
- `cli/wuwei/commands/status.py` `snapshot` (non-line, config present):
  `result['checks_none'] = [repo['name'] for repo in config['repos'] if not repo['fast_checks']]`;
  `full(data)` adds one group `f'{name} {fast_checks.NONE}'` per name.

### 3. Detection (US3.5, FR-005)

- `cli/wuwei/calibrate.py` `toolchain`:
  - markdownlint: the first present of `.markdownlint.json`, `.markdownlint.jsonc`,
    `.markdownlint.yaml`, `.markdownlint.yml`, `.markdownlintrc` yields
    `_finding('fast_check', 'markdownlint .', name, 1)`; add `'markdownlint .'` to `LINT`.
  - latexmk: `.latexmkrc` or `latexmkrc` yields `_finding('fast_check', 'latexmk', name, 1)`.
  - Use `_present` for existence (it already refuses symlinks); `_read` only where the text
    is needed.
- Workflow fallback: `_workflow` records each job's single-line `run:` values as
  `job['runs'] = [(command, line)]` (a `run: |` block is skipped). In `toolchain`, only
  when no `fast_check` finding exists, for each workflow from `_workflows(checkout, found)`
  whose triggers include `pull_request` or `push`, take the runs of jobs whose name matches
  `(?i)test|check|lint` and whose command matches `TEST_STEP`, a regex for a test, check or
  lint verb (`pytest`, `test`, `check`, `lint`, `latexmk`, `markdownlint`) that does not
  start with an install or setup word (`pip`, `pip3`, `npm ci`, `npm install`, `apt`,
  `apt-get`, `brew`, `sudo`, `cd`, `echo`). `ponytail:` comment: line regex, an install
  step that names a test word is the ceiling; a YAML reader if a real repository needs it.
- `profile` keeps filtering every value through `SAFE` and the instruction-like rules.

### 4. The proposal (US3, FR-006)

In `cli/wuwei/calibrate.py`:

- `CHECKS = 'Which fast checks gate every change in repo:{repo}?'` and
  `NOTHING = 'no Makefile test, check or lint target, no pyproject.toml or package.json
  check, no latexmk or markdownlint configuration and no CI test step'`.
- `checks_record(root, name)`: newest `(day_dir, 'D-n')` on `watch.days(root)` whose
  record's `Question` equals `CHECKS.format(repo=name)` (read with `decision.evaluate`;
  unreadable records skipped), else None. `ponytail:` comment: live days only; an
  archived record is not read, so the repository is proposed again after its day is
  archived; a memory file is the upgrade.
- `checks_answered(root, name)`: `checks_record` found and
  `decision.answered(state.read_state(directory=day), ident)` is not None (owner outcome in
  CLI-written state).
- `checks_text(index, name, commands, sources)`: the record text, built with the shared
  record writer `grants._record` (`cli/wuwei/grants.py:58-85`, already used by
  `pace.propose_default`), extended with keyword-only `cls='other'`,
  `confidence='medium'`, `door='one-way'` and `extra=''` (text inserted before
  `Recommendation:`); the defaults keep every existing record byte-identical. Here:
  question `CHECKS`, `cls='approach'`, `confidence='high'`, `door='two-way'`, context
  naming the sources (`detected in Makefile:12`) or `NOTHING`, blast `repository <name>
  fast checks`, and `extra` holding the `Value:` table and
  `Previous: repos.<index>.fast_checks = []`. Rows:
  - detected: `A Detected` (Value `repos.<i>.fast_checks = <configtext.dumps(commands,
    inline=True)>`, score 9), `B None` (Value `[]`, score 4), `C Defer` (no Value, score 1);
    Recommendation A;
  - nothing: `A None` (Value `[]`, score 9), `B Defer` (no Value, score 1); Recommendation A.
  It must pass `decision.evaluate(text, lens_table(config))` (`approach` is not an
  engineering class, so no Lenses); titles stay under 40 characters without quotes.
- `cli/wuwei/commands/calibrate.py` `_interview`, branch `args.questions is not None`:
  when `args.questions == []`, call `propose_checks(root, config, selected)` (new, in
  `cli/wuwei/calibrate.py`) before printing; it returns `(widgets, lines)`; print the
  widgets appended to `interview.widgets(...)` and the lines to stderr.
- `propose_checks`: for each `(index, repo)` with `repo['fast_checks'] == []` and no
  `checks_record`: resolve the checkout as `survey` does (missing: one stderr line, skip);
  `facts = profile(checkout, repo)['facts']['fast_checks']`; write the record with
  `decision.write`; then
  - autonomous (`config['autonomy']['mode'] == 'autonomous'`) and posture not strict:
    rewrite it with `decision.decided_record(text, 'A', 'mandate')`, record
    `decision.seat_outcome(fields, scores, by='mandate')` under `decision_outcomes[ident]`
    in one `state._write_state(..., kind='decision.decided', payload={'id': ident, ...})`
    (the `build._park` pattern), then, when the value differs from `[]`, write it with
    `setup.card_write(root, 'calibrate', change, [key], ident)` where `change` is
    `setup._settle(raw, [(('repos', index), 'fast_checks', commands)])`; line
    `calibrate: D-n taken under mandate (Routine): repos.<i>.fast_checks = <value>`;
  - otherwise `decision.route_owner(ident, fields, root)` and append
    `decision.record_widget(ident, fields, CONFIG_RECORD)` (from `commands/decision.py`).
- The digest lists the record through its Outcome line (unchanged `digest.build`).

### 5. Value rows (US4, FR-007, FR-008)

- `cli/wuwei/decision.py`: `OPTIONAL += ('Value', 'Previous')`; add `'Previous'` to the
  one-line field check. `values(fields)`: `{option: cell}` from
  `table(fields['Value'], ['Option', 'Value'], 'Value')`, `{}` without the field.
  `config_keys(fields)`: `{key: value}` from `setup.assignment` of each Value cell and,
  for options without a Value row, of each title (#529); lazy import of
  `wuwei.commands.setup`. `_explained` (new-record lint): every Value row names an option
  id and `setup.assignment(cell)` is not None, else
  `ValueError('Value: row <id> must name an option and read <key> = <TOML value> with a declared key; ...')`;
  a `Previous` line, when present, must parse with `assignment`.
- `cli/wuwei/commands/decision.py`: `CONFIG_RECORD = 'wuwei config set --from-card {id}'`;
  `show --widget` uses it when `config_keys(fields)` is not empty.
- `cli/wuwei/commands/config.py`: `key` and `value` get `nargs='?'`.
- `cli/wuwei/commands/setup.py`:
  - `set_value`: with no `--from-card`, a missing key or value exits 2 with
    `config set: pass KEY VALUE, or --from-card D-n in the session`; `command` is built
    only from given parts. The session hint (no card) prints: write a decision whose
    options carry `Value:` rows `KEY = <value>` and the line
    `Previous: KEY = <configtext.dumps(current, inline=True)>`, route it, ask it with
    `bin/wuwei decision show D-n --widget`, then run `bin/wuwei config set --from-card D-n`.
  - `_from_card`: the answered option is the row whose title `card_answered`; its
    assignment is `assignment(values.get(id) or title)`. With KEY and VALUE given, they
    must equal it (else today's refusal). With an assignment: set `args.key`, `args.value`
    from it (value text after ` = `) and write through `card_write` as today. Without one
    (Defer, Keep): call `owner_outcome` only and print `No config.toml changes`, exit 0.
  - Unchanged: `assignment`, `card_write`, `_settle`, the strict refusal, I8's hook path.

### 6. Two-way config records (US5, FR-009, FR-010)

- `cli/wuwei/undo.py`: `config_write(fields)`: True when `decision.config_keys(fields)` is
  not empty and `fields.get('Previous')` parses with `assignment` to a key among them.
  - `measured`: first line `if config_write(fields): return 'config', None` with a comment:
    its undo is `config set` with the recorded previous value (#600), no rehearsal.
  - `correct`: after the routed or decided early return, and before the one-way early
    return: when `config_write(fields)` and (door != `two-way` or Class missing or `other`),
    rewrite the first `Reversibility:` line to `two-way`, the `Class:` line to `approach`
    when it is `other` (append `Class: approach` when missing), add
    `Notes: Reversibility corrected at <stamp>: a config write that records its previous
    value is undone by config set (#600).`, write atomically, and return the updated
    fields and the line `Reversibility: two-way, not <written>: ...`.
- `cli/wuwei/decision.py` `lint`: when `root` is given and `undo.config_write(fields)` and
  the door is not two-way, append the same line (report, never refuse).
- `cli/wuwei/commands/decision.py` `mandate`: after the routed/decided checks, `if
  config_keys(fields): return None` with the comment `#529: a config value is the owner's
  answer on its card`.

### 7. Invariants and docs (FR-011)

- Design 9.2 rows, `tests/test_invariants.py` checks, `INVARIANTS` and `READS` entries:
  - I25 `An empty fast-check list never refuses a launch below strict` | per posture,
    `build._repo` on a repository with `fast_checks = []`, no card answered | `(0,)` |
    #600; strict refuses naming the card until the owner answers it.
  - I26 `A config card with a list value records without a prompt below strict` | per
    posture, a routed card with a Value row `repos.0.fast_checks = ["make test"]` answered
    in the planner session, `config set --from-card D-1` with `integrity._host_confirm`
    raising | `(0,)` | #600; strict prints the host command.
  - I27 `A config record is never Strategic on its own` | for Class `other` and none x
    door one-way, two-way, unsure x confidence high and low, `undo.correct` then `cisr` on
    a record with Value rows and a Previous line | `()` | #600; a seat's better class
    stands.
  - I22 Notes: add `#600: a config write that records its previous value is two-way; its
    undo is config set with that value`.
- Design 5.2 Records (#529 paragraph): options carry `Value:` rows; the record command is
  `config set --from-card D-n`; a Keep or Defer answer records the outcome only.
- `skills/wuwei-plan/SKILL.md` line 16: the record command `wuwei config set --from-card
  D-n`; a config card's options carry `Value:` rows and a `Previous:` line.
- `docs/site/configuration.md:346` and `docs/site/recovery.md` (fast_checks entry, keeping
  `fast_checks = []` and `bin/wuwei config promote` for `test_docs`): `[]` means none
  configured, items build, CI and the gates are the evidence; the daily card proposes from
  the repository.

## What must not change

- `fast_checks.commands`, `fast_checks.record`, `commit_push.fast_evidence`, the PR guard,
  `protect_state` (I8: one `--from-card D-n` from the planner after a card answer).
- `build.complete_checks` and `build.check` on non-empty lists; the pace rules (#579).
- `config set KEY VALUE --from-card D-n` on #529 title cards; `assignment`; `card_write`.
- `undo.REGISTRY` and `undo.missing` (no `config` kind there, so doctor and `wuwei next`
  ask no rehearsal for it).
- `config promote` and `calibrate` without `--questions`.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/commands/build.py` | `_repo` strict-only refusal; `checks` on `build.started` |
| `cli/wuwei/fast_checks.py` | `NONE` constant |
| `cli/wuwei/brief.py` | none line in the builder header |
| `cli/wuwei/commands/status.py` | `checks_none` in `snapshot`, line in `full` |
| `cli/wuwei/commands/doctor.py` | `ok` row with `NONE` |
| `cli/wuwei/calibrate.py` | detectors, `_workflow` runs, `CHECKS`, `checks_record`, `checks_answered`, `checks_text`, `propose_checks` |
| `cli/wuwei/commands/calibrate.py` | `--questions` calls `propose_checks` |
| `cli/wuwei/decision.py` | `Value`, `Previous`, `values`, `config_keys`, lint lines |
| `cli/wuwei/commands/decision.py` | `CONFIG_RECORD`, `mandate` skip |
| `cli/wuwei/undo.py` | `config_write`, `measured`, `correct` |
| `cli/wuwei/commands/setup.py` | `set_value`, `_from_card` |
| `cli/wuwei/commands/config.py` | optional KEY and VALUE |
| `cli/wuwei/grants.py` | `_record` keyword defaults `cls`, `confidence`, `door`, `extra` |
| design spec, skill, site docs | as in section 7 |

## Builder notes (deviations found while implementing)

- `decision.values` is folded into `decision.config_keys`, which returns `{option: (key, value)}`
  from the Value rows, else the #529 titles; `setup.declared` checks the key for the lint.
- A card write replaces the value as the card shows it (`setup.write_value`), in both
  `config set --from-card D-n` forms: the merge path appended a list value to the current list,
  which I26 caught.
- The doctor row for an empty list is `ok`, so its `config-promote` fix had no producer left;
  the fix is retired (doctor `FIXES`, its preview and apply, `docs/site/reference.md`). The
  generic `doctor --fix` tests use the watch-install fix instead.
- A build with no checks completes at the builder's stop (zero checks to wait for), so T003 pins
  the stop path; `build check` is not reached.
- The builder brief's none line also needs "not fast pace with `repos.tests`": at fast pace the
  tests the diff touches run, and the brief is written before the diff exists.
- A symlinked lint config is refused through `_read` (it reports `skipped`); `_present` does not
  refuse symlinks.
- The T002 dispatch test lives in `tests/test_build_next.py`, whose `seat` fixture has the real
  build path.
