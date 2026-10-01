# Implementation Plan: an owner interview that turns personal preferences into configuration and charter overrides

**Branch**: `279-owner-interview` | **Spec**: `specs/279-owner-interview/spec.md`

## Summary

One new core module, `cli/wuwei/interview.py`, holds the question table and everything
that reads it: validation, the terminal loop, the widgets, recording, the charter and voice
proposals, the config settings and the retro re-ask. `wuwei calibrate` gains three
mutually exclusive flags (`--interview`, `--questions`, `--answer`). Config answers land
only through the existing owner action `wuwei config promote`, which folds them into the
calibration proposal through one new calibrate function, `settle`, and a one-line
generalisation of `calibrate.apply`. Charter and voice answers land only through
`wuwei promote` as ordinary proposals. The retro gets one section from `interview.reask`.
No new config key, charter, owner action, port, event kind or guard.

## Technical Context

Python 3.11+, stdlib only at runtime (`json`, `re`, `tomllib`, `zoneinfo`, `datetime`).
pytest for tests. No subprocess, no port call: the interview reads and writes workspace
files only.

## Constitution Check

- I Stdlib only: yes (`zoneinfo.available_timezones()` for time zones).
- II Three-state exits: `--interview`, `--answer`, `--questions` exit 0 done, 2 could not
  run (no tty, unknown id, invalid answer, unknown repository, unreadable
  `interview.json`, end of input). `config promote` keeps 0 applied, 1 declined, 2 could
  not run; an invalid `interview.json` is 2. The retro section says `unmeasured: <reason>`
  rather than `none` when a day state cannot be read.
- III One behaviour, one function: the question set exists only in
  `interview.QUESTIONS`; answers resolve only in `interview.effects`; config placement
  only in `calibrate.settle` and `calibrate.apply`; proposals land only through
  `promotion.promote`; config only through `config promote`.
- IV Test first: every task pair in `tasks.md` is test then code.
- V Ponytail: one module of plain functions and one tuple of dicts, no classes. Reuse
  `calibrate.apply`, `_labelled`, `_table`, `SAFE`, `instruction_like`, `NO_REPOS`,
  `integrity.HOST_TERMINAL`, `merge.quiet`, `voice.parse_profile`, `decision.evaluate`,
  `decision.table`, `decision.answered`, `state.read_state(directory=)`, `watch.days`,
  `workspace.atomic_write`, `workspace.day_dir`, the proposal JSON format and the
  `check_question` guard as they are.
- VII Security: config changes need the owner's digest on `/dev/tty`; the interview never
  proposes `merge_deploys` and never removes a `deploy.deny` pattern; free text is
  charset-checked and instruction-scanned before it reaches a charter; `interview.json` is
  a protected day file written only by the CLI and re-validated on every read.

## Design

### 1. `cli/wuwei/interview.py` (new)

Constants:

- `BLOCK = '## Owner preferences (interview)\n'`
- `ROLES = ('planner', 'shepherd', 'lead')`
- `REASK_AFTER, REASK_DAYS = 3, 7`
- `MERGE_QUESTION = re.compile(r'Merge (?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#[0-9]+\?')`
- `EXECUTABLE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]*')` (the `load_config` deny rule,
  `cli/wuwei/workspace.py:409`; import nothing private, the pattern is one line)

`QUESTIONS`: a tuple of dicts `{'id', 'scope', 'header', 'question', 'choices', 'free'}`.
`choices` is a tuple of `(label, description, effects)`; `free` is `None` or
`(parser, hint)` where `parser(text) -> effects` raises `ValueError`. Effects is a dict
whose keys are a dotted config key (`repos.` prefix means each answered repository),
a role in `ROLES` (one fixed sentence) or `voice` (a list of never phrases). An empty dict
means "no change". The table, in order (headers are at most 12 characters):

| id | scope | header | question | choices: label (effects) | free text |
|---|---|---|---|---|---|
| merge | repo | Merges | How much merge autonomy for {repo}? | Owner merges (`repos.merge.auto` false); Auto, 30 min soak (auto true, `soak_minutes` 30); Auto, 2 hour soak (auto true, `soak_minutes` 120). Descriptions of the auto choices end with "needs merge_deploys = false". | none |
| gates | repo | Gate floor | Lowest review tier for every change in {repo}? | Standard; Full; Light (`repos.gates.floor`) | none |
| quiet | repo | Quiet hours | When must {repo} never auto-merge? | No quiet hours (`repos.merge.quiet_hours` []); Nights (`["20:00-08:00"]`) | `HH:MM-HH:MM`, comma-separated, each checked with `merge.quiet({'quiet_hours': [w]}, datetime(2000, 1, 1))` |
| interrupt | workspace | Interrupts | When should a pending decision interrupt you? | Batch (planner: "Batch pending owner decisions into the two-hourly digest; ask at once only when a decision blocks a running item."); At once (planner: "Ask each one-way-door decision as soon as its record passes the lint."); Morning only (planner: "Hold decisions that block nothing for the next morning gate; pages still interrupt.") | none |
| decisions | workspace | Decisions | How should decisions be presented to you? | Recommended first (planner: "Present two or three options with the recommended option first."); Options only (planner: "Present the options without marking the recommendation; the record keeps it."); Yes or no (planner: "Ask the recommendation as a yes or no question; the other options stay in the record.") | none |
| phone | workspace | Phone | What may control-plane messages carry? | Summary (`control_plane.content` "summary"); Nothing (`control_plane.content` "none") | none |
| hours | workspace | Hours | When do you work, and in which time zone? | Office hours (planner: "The owner works 09:00-17:00 in this host's time zone; outside those hours only pages interrupt."); Any time ({}) | `HH:MM-HH:MM Area/City`: the window checked with `merge.quiet`, the zone in `zoneinfo.available_timezones()`; planner sentence with both |
| avoid | workspace | Avoid words | Which words should messages sent as you never use? | Defaults only ({}); Corporate filler (voice: synergy, circle back, touch base, leverage) | comma-separated phrases (`_items`), voice |
| formality | workspace | Formality | How formal is your writing? | Plain (shepherd: "Write plainly and directly: first names, no pleasantries."); Neutral (shepherd: "Write in a neutral professional register."); Formal (shepherd: "Write formally: full sentences, a greeting and a sign-off.") | none |
| signature | workspace | Signature | How do you sign messages sent as you? | No signature (shepherd: "Add no signature to messages sent as the owner."); First name (shepherd: "Sign messages sent as the owner with the first name in owner.name.") | one `_items` item; shepherd: "Sign messages sent as the owner with: <text>." |
| risk | workspace | Risk words | What else counts as trust surface in your project? | Lead defaults ({}); Money and data (lead: "Also set trust_surface for changes touching billing, payments or exports of personal data.") | `_items`; lead: "Also set trust_surface for changes touching: <items>." |
| manual | workspace | By hand | Which commands do you always run yourself? | Deployment ban only ({}); Package publishing (`deploy.deny`: `npm publish*`, `twine upload*`, `cargo publish*`, `gem push*`) | `_items`, each starting with an `EXECUTABLE` word, `*` appended when absent |

Functions (all plain, in this module):

- `_items(text)`: split on `,`, strip, drop empties; 1 to 20 items, each
  `calibrate.SAFE.fullmatch` and no `calibrate.instruction_like` hit, else `ValueError`.
- `question(qid)`: the row, or `ValueError('unknown interview question <qid>; use one of: <ids>')`.
- `effects(qid, answer)`: a choice label (case-insensitive) gives its effects; otherwise
  the free parser's effects; otherwise `ValueError('<qid>: answer one of: <labels>')`
  (plus the hint when free text is allowed).
- `load(root, config)`: today's `interview.json` (`workspace.day_dir(root)`); absent
  gives `{}`; a symlink, non-object, unknown id, wrong shape (repository question not a
  dict, workspace question not a string), repository name not in `config['repos']`, or an
  answer `effects` rejects raises `ValueError`.
- `ask(ids, repos)` (calls `input` and `print` at run time so tests patch `builtins`): for each selected row in table order and
  each repository for a repository row, write the header, question and numbered choices
  (plus `or type your own: <hint>`), read until `effects` accepts the answer (a number
  selects a choice), and return `picked` in the answers shape. `EOFError` propagates.
- `parse(pairs, repos)`: `ID=VALUE` strings to `picked` (repository rows get the value for
  every selected repository); `effects` validates each; no `=` is `ValueError`.
- `record(root, config, picked)`: `load`, merge `picked` (repository answers per name),
  `atomic_write` `interview.json` (`json.dumps(..., indent=2, sort_keys=True)`), then
  `_proposals` and write each to `proposals/interview-<target>.json`, unlinking a stale
  `interview-<target>.json` whose target no longer has a proposal. Returns the answers.
  Nothing is written when any answer is invalid.
- `settings(answers, config)`: effects with a dotted key to `(path, key, value)`:
  `repos.<a>.<b>` gives `(('repos', index, a), b, value)` per answered repository (index in
  `config['repos']`), any other `<a>.<b>` gives `((a,), b, value)`.
- `describe(answers, config)`: one line per answer, for example
  `- merge (acme/widget): Auto, 30 min soak -> repos.0.merge.auto = true, repos.0.merge.soak_minutes = 30`,
  `- interrupt: Batch -> .wuwei/charters/planner.md`,
  `- avoid: Corporate filler -> .wuwei/memory/voice.md never: synergy, ...`,
  `- manual: Deployment ban only -> no change`. Values render with `json.dumps`.
- `_proposals(root, answers)`: per role in `ROLES`, the lines `{qid: sentence or None}`
  from today's workspace answers; read `.wuwei/charters/<role>.md` when it exists; find
  the existing block (`re.search(r'^## Owner preferences \(interview\)\n(?:(?!## ).*\n?)*', text, re.M)`),
  parse its `- <id>: <sentence>` lines, overlay today's lines (None removes), and render
  `BLOCK` plus lines in table order. Existing block: `{'action': 'patch', 'old_text': <block>, 'text': <new>}`;
  none and at least one line: `{'action': 'add', 'text': <new>}`; none and no line: no
  proposal. Voice: phrases from the `avoid` answer not already in
  `voice.parse_profile(voice.md).get('shared', {}).get('never', [])` (case-insensitive);
  `patch` of `'## shared\n'` to `'## shared\n' + '- never: <p>\n'...` when that heading is
  in voice.md, else `add` of the heading plus lines; no new phrase, no proposal. Every
  proposal carries `target`, `reason` (`owner interview: <ids>`) and `evidence`
  (`.wuwei/days/<date>/interview.json`). Overrides and voice.md are read through
  `promotion.safe_path` (no symlinked component); a symlink raises `ValueError`.
- `widgets(root, repos)`: per row and repository (repository rows only), a dict
  `{'id', 'repo', 'header', 'question', 'multiSelect': False, 'options': [{'label', 'description'}]}`
  (`repo` only for a repository row)
  whose `question` is `Morning gate (days/<date>/plan.md): ` plus the formatted question.
  A repository row with no repository raises `ValueError(calibrate.NO_REPOS)` (also in
  `ask` and `parse`).
- `reask(root)`: as FR-007. Reads `workspace.load_config(root)`; walks `watch.days(root)`
  while `(today - date.fromisoformat(day.name)).days < REASK_DAYS`; skips a day without
  `state.json`; for each id in `decision_outcomes` with `decision.answered(data, id)`,
  reads `day/decisions/<id>.md` (skips a symlink or missing file), `decision.evaluate`
  (a `ValueError` skips it), `decision.table(fields['Options'], ['Option', 'Description'], 'Options')`,
  and counts it for `MERGE_QUESTION.fullmatch(fields['Question'].strip())['repo']` when
  the chosen option's description casefolded starts with `merge`. Returns, per configured
  repository with `merge.auto` false and at least `REASK_AFTER` entries, one line:
  `- <repo>: you merged <n> pull requests the merge policy routed to you in the last 7 days (<date> D-<n>, ...). Proposed: repos.merge.auto = true<note>. Re-ask: bin/wuwei calibrate --interview merge --repo <repo>`
  where `<note>` is ` (it applies only with merge_deploys = false)` unless that repository
  already declares `merge_deploys = false`. `OSError` or `ValueError` from reading config
  or a day state returns `['- unmeasured: <reason>']`.

### 2. `cli/wuwei/calibrate.py`

- `_assignment(key, line)`: true when `line` starts (after spaces) with `key` and `=`
  and `tomllib.loads(line)` is exactly `{key: ...}` (a complete one-line assignment; a
  `TOMLDecodeError` is false).
- `apply`: replace the `path == ('deploy',) and _empty_list(key, old)` match at line 470
  with `_assignment(key, old)` for any path; record `(path, key)` in `replaced`; drop each
  replaced key from `before` with `_table(before, path).pop(key)`. `_empty_list` stays in
  `proposal` (calibrate still replaces only a one-line `[]`).
- `settle(raw, settings) -> (additions, edits)` (new): presence from `tomllib.loads(raw)`
  and `_table`; a `('deploy',)` list value becomes the present list plus new items in
  order; absent key is an addition; equal value is skipped; a key whose section (by
  `_labelled`) has an `_assignment` line is an addition (replacement); anything else is a
  hand edit `('<dotted path>.<key>', current, value)`.
- `propose(raw, results, settings=())`: after `text = apply(raw, additions)`, run
  `extra, more = settle(text, settings)` and `text = apply(text, extra)`; the diff is
  still `raw` to the final text; return `edits + more`.

### 3. `cli/wuwei/commands/calibrate.py`

`register`: a mutually exclusive group with `--interview` (`nargs='*'`,
`metavar='QUESTION'`), `--questions` (`store_true`) and `--answer` (`action='append'`,
`metavar='ID=VALUE'`). `run`: when any of them is set, return `_interview(args)` before
any profiling. `_interview(args)`:

1. `root`, `config`; `repos` = configured names filtered by `--repo` (unknown name: exit 2
   as today).
2. `--questions`: print `json.dumps(interview.widgets(root, repos), indent=2)`, exit 0.
3. `--answer`: `picked = interview.parse(args.answer, repos)`.
4. `--interview`: validate the ids with `interview.question` (empty list means all), then
   `if not sys.stdin.isatty(): raise OSError(integrity.HOST_TERMINAL)`, then
   `picked = interview.ask(ids, repos)`.
5. `answers = interview.record(root, config, picked)`; print `interview.describe(answers, config)`
   and `Next: run bin/wuwei config promote in a host terminal for the config keys, then bin/wuwei promote for the charter and voice proposals.`
6. `OSError`, `ValueError` or `EOFError`: print `wuwei calibrate: <reason>` to stderr
   (`interview interrupted; nothing written` for `EOFError`), exit 2.

### 4. `cli/wuwei/commands/config.py:promote`

After `results = calibrate.survey(...)`: `from wuwei import interview` (local, like
calibrate), `answers = interview.load(root, config)`, and pass
`interview.settings(answers, config)` to `calibrate.propose`. Add
`'Interview answers:\n' + '\n'.join(interview.describe(answers, config)) + '\n'` to
`summary` after the hand edits when there are answers, so the digest covers them. Nothing
else changes (snapshot, digest, re-read, exits).

### 5. `cli/wuwei/retro.py:compile`

Before `## Metrics`: `from wuwei import interview` (local) and
`lines += ['', '## Owner preferences', *(interview.reask(root) or ['none'])]`.

### 6. Guard, charter, skill

- `cli/wuwei/guards/protect_state.py:194`: add `'interview.json'` to the protected day
  file tuple.
- `charters/shepherd.md` step 3: after "route the merge to the owner with the decision
  record and the failed precondition", add: "Write that record with
  `Question: Merge <owner>/<repo>#<number>?` and one option whose description starts with
  `Merge`, so the retro can count merges you decided against the policy." Then run
  `bin/wuwei agents build` to regenerate `agents/shepherd.md`.
- `skills/wuwei-plan/SKILL.md`: in the opening paragraph, also read
  `.wuwei/charters/planner.md` when present (owner preferences). In step 4 add: on the
  first day (no earlier day directory under `.wuwei/days/`), after the gate questions, run
  `wuwei calibrate --questions`, ask the printed widgets with AskUserQuestion at most four
  per call passing `question`, `header`, `options` and `multiSelect` unchanged, then
  record each answer with `wuwei calibrate --answer "<id>=<label or Other text>"` (add
  `--repo <repo>` for a widget that names one), and tell the owner to run
  `bin/wuwei config promote` in a host terminal and `bin/wuwei promote`.

### 7. Docs

- `docs/site/configuration.md`: `## Owner interview` right after `## Calibration`: the
  twelve questions and what each maps to (a short table), `calibrate --interview [id]` on
  a host terminal, `--questions` and `--answer` for the plan skill, `interview.json` per
  day, config keys through `config promote`, charter and voice through `wuwei promote`,
  `deploy.deny` only grows, the retro re-ask after three merges in seven days.
- `docs/site/daily.md` section 2, after the calibrate paragraph: run
  `bin/wuwei calibrate --interview` once in a host terminal, or answer the same questions
  in the plan skill on the first day.

## Data shapes

`.wuwei/days/<date>/interview.json`:

```json
{"avoid": "synergy, per my last email", "interrupt": "Batch",
 "merge": {"acme/widget": "Auto, 30 min soak"}, "phone": "Nothing"}
```

Charter proposal `proposals/interview-planner.json`:

```json
{"target": ".wuwei/charters/planner.md", "action": "add",
 "text": "## Owner preferences (interview)\n- interrupt: Batch pending owner decisions ...\n",
 "reason": "owner interview: interrupt", "evidence": ".wuwei/days/2026-10-01/interview.json"}
```

## Must not change

- `wuwei promote`, `promotion._target` and its lint; the interview uses `add` and `patch`
  as they are.
- Calibrate's detectors, `proposal` rules and report; every test in
  `tests/test_calibrate.py` passes unchanged.
- `workspace.SCHEMA`, the template `config.toml`, `config check`, `guards/decision.py`,
  `signal.py`, the owner-action list in protect_state, and every hook.
- `calibrate` without the new flags behaves exactly as today.

## Files

New: `cli/wuwei/interview.py`, `tests/test_interview.py`.

Changed: `cli/wuwei/calibrate.py`, `cli/wuwei/commands/calibrate.py`,
`cli/wuwei/commands/config.py`, `cli/wuwei/retro.py`,
`cli/wuwei/guards/protect_state.py`, `charters/shepherd.md`, `agents/shepherd.md`
(regenerated), `skills/wuwei-plan/SKILL.md`, `docs/site/configuration.md`,
`docs/site/daily.md`, `tests/test_protect_state.py`, `tests/test_hooks.py`,
`tests/test_docs.py`, `tests/test_report_retro.py`.

## Deferred

- A signature or register lint (4.8 says tone cannot be linted; no suffix rule exists).
- A re-ask trigger for questions other than merge.
- Per-repository differences in one widget call (one `--answer --repo` call each).
