# Implementation Plan: Specification mode

**Branch**: `412-spec-mode` | **Date**: 2026-10-03 | **Spec**: specs/412-spec-mode/spec.md
**Input**: design 5.10 (`docs/specs/2026-09-24-wuwei-design.md:772-879`), the 4.1 hook rows,
and specs/411-spec-mode-spec/plan.md "Deferred".

## Summary

One helper, `cli/wuwei/specmode.py`, owns every rule of 5.10: the step tables as data, the
artifact checks, item location, the skip rule, the effective mode, the once-per-day events,
engine presence and the texts. Every enforcement point calls one function,
`specmode.check(...)`, and turns its `(exit, reason)` into its own form: a hook refusal, a
failing build check named `spec`, or a `dispatch.Refused`. A small guard module,
`cli/wuwei/guards/spec.py`, matches the path to an item's recorded worktree before it
imports the helper, so hooks elsewhere pay one state read and no new import.

## Technical Context

Python 3.11 stdlib; pytest for tests. Modules touched: `workspace`, `guards/__init__`, new
`guards/spec`, new `specmode`, `commands/build`, `dispatch`, `brief`, `plan`,
`commands/plan`, `state`, `commands/event`, `guards/protect_state`, `commands/next`,
`guards/lifecycle`, `report`, `commands/doctor`, `commands/setup`, `interview`. Text:
`templates/workspace/config.toml`, `charters/{builder,lead,planner}.md`,
`skills/wuwei-plan/SKILL.md`, `agents/` (regenerated), `docs/site/{configuration,concepts,daily,agent}.md`.
Fixtures: `tests/fakes/day.py`, `scripts/headless_e2e.py`, `tests/fixtures/spec/`.

## Constitution Check

- I stdlib: `json`, `re`, `pathlib` only. No subprocess in `specmode` (the diff tier reuses
  `dispatch.tier`, which already goes through the VCS port).
- II three-state: `check` returns 0, 1 or 2; an unreadable artifact is "not done" (a
  finding, never clean); unreadable state, config or plugins file is exit 2 with the
  reason; doctor reports unmeasured, never ok.
- III one behaviour, one function: every 5.10 rule lives in `specmode`; callers only map
  its result. Events are written only by the CLI (`spec.*` names its producers).
- IV test first: tasks.md orders each test before its code.
- V ponytail: no class, no registry of engines beyond one dict, no new posture area, no new
  config beyond the three keys 5.10 names, no per-repository engine, no confirmation
  prompt for `plan set`.
- VII security: `plan set` is an owner action refused from agent tools; `items.<item>.spec`
  and the `spec.*` kinds are producer-reserved; artifacts are never treated as owner
  approval; no refusal elsewhere is weakened (`AREAS['spec'] = None` applies the check's
  own mode, and owner-only areas are untouched).

## Design

### Config (`cli/wuwei/workspace.py`)

- `SCHEMA["spec"] = {"engine": (str, "speckit", ("speckit", "superpowers", "openspec",
  "none")), "mode": (str, "strict", ("strict", "advisory", "off")), "skip_tiers": [(str,
  None, ("light", "standard", "full")), ["light"]]}` (the list form `scanner.mcp.block`
  uses). Insert before `"adapters"` (line 165).
- `CONFIG_CACHE_VERSION = 2` (line 501; its comment says bump on schema or defaults).
- `templates/workspace/config.toml`: a `[spec]` section before `[security]` with the three
  keys at their defaults and one comment each (what the engine is, what each mode does,
  that a tier in `skip_tiers` skips the spec and `wuwei plan set` overrides it per item).
  `config check` needs no code: it runs `load_config`, which validates against SCHEMA.

### Helper (`cli/wuwei/specmode.py`, new)

Top-level imports: `json`, `re`, `pathlib.Path`, `from wuwei import state, workspace`
(both already loaded on every path that reaches it).

Data:

```python
INSTALL = {'speckit': 'uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai claude',
           'superpowers': '/plugin marketplace add obra/superpowers-marketplace, then /plugin install superpowers@superpowers-marketplace',
           'openspec': 'npm install -g @fission-ai/openspec, then openspec init'}
MARKER = {'speckit': '.specify', 'openspec': 'openspec'}   # superpowers: the plugins file
OWN = {'speckit': ('specs', '.specify'), 'superpowers': ('docs/superpowers',), 'openspec': ('openspec',)}
# Where the item's artifacts live, relative to the worktree; {item} is the id lowercased.
LOCATION = {'speckit': ('specs/{item}', 'specs/*-{item}'),
            'openspec': ('openspec/changes/{item}', 'openspec/changes/archive/*-{item}'),
            'superpowers': ('.',)}
DATE = '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
# (step, artifact glob under the location or None, rule, command)
STEPS = {
    'speckit': (('specify', 'spec.md', 'one', '/speckit.specify'),
                ('clarify', 'spec.md', 'clarified', '/speckit.clarify'),
                ('plan', 'plan.md', 'one', '/speckit.plan'),
                ('tasks', 'tasks.md', 'one', '/speckit.tasks'),
                ('analyze', 'analysis.md', 'clean', '/speckit.analyze, report saved as analysis.md'),
                ('checklist', 'checklists/*.md', 'checked', '/speckit.checklist'),
                ('implement', 'tasks.md', 'checked', '/speckit.implement')),
    'superpowers': (('brainstorming', f'docs/superpowers/specs/{DATE}-{{item}}-design.md', 'one', 'superpowers:brainstorming'),
                    ('writing-plans', f'docs/superpowers/plans/{DATE}-{{item}}.md', 'one', 'superpowers:writing-plans'),
                    ('executing-plans', f'docs/superpowers/plans/{DATE}-{{item}}.md', 'checked',
                     'superpowers:executing-plans with superpowers:test-driven-development'),
                    ('verification-before-completion', None, None, 'superpowers:verification-before-completion')),
    'openspec': (('proposal', 'proposal.md', 'one', '/openspec:proposal'),
                 ('specs', 'specs/*/spec.md', 'some', '/openspec:proposal'),
                 ('tasks', 'tasks.md', 'one', '/openspec:proposal'),
                 ('validate', 'validation.json', 'valid', 'openspec validate {item} --strict --json > validation.json'),
                 ('apply', 'tasks.md', 'checked', '/openspec:apply'),
                 ('archive', None, 'archived', 'openspec archive {item} --yes')),
}
IMPLEMENT = ('implement', 'executing-plans', 'apply')
```

Rules (one small function each, in a dict `RULES`), all reading UTF-8 and treating any
read or decode error as not done with the file named:

- `one`: exactly one match (two dated superpowers files are ambiguous; the reason names both).
- `some`: at least one match.
- `clarified`: the one `spec.md` has a line `## Clarifications`.
- `clean`: the one `analysis.md` has no Markdown table row (`|`-delimited line) with a
  cell equal to `CRITICAL` or `HIGH` (case-insensitive); the reason names the first such
  row.
- `checked`: at least one match, at least one `- [x]`/`- [X]` across them, no `- [ ]`.
- `valid`: `json.loads` gives a dict whose `items` is a nonempty list of dicts each with
  `valid is True`.
- `archived`: the resolved location lies under `openspec/changes/archive/`.
- `None` rule: always done.

Functions (the whole public surface):

- `mode(config)`: `'off'` when `engine == 'none'` or `mode == 'off'`; `'advisory'` when
  `mode == 'advisory'` or (`mode == 'strict'` and `workspace.posture(config)[0] ==
  'observe'`); else `'strict'`.
- `label(config)`: `f"{engine} {mode(config)}"`, for the orientation line.
- `skip(config, row, computed=None)`: `row.get('spec')` override first (`skipped` returns
  `owner: <reason>`, `required` returns None); then `row.get('tier') in skip_tiers` returns
  `lead tier <tier>` unless `computed` is given and not in `skip_tiers`; else None.
- `status(tree, engine, item, *, build=False)`: None when done, else `{'step', 'artifact',
  'command', 'reason', 'location'}` for the first step not done. Without `build` the
  steps stop before the `IMPLEMENT` row; with `build` all rows count. Location: the
  `LOCATION` globs with `item.lower()`; none matches: the first step is the gap (reason
  `no <glob> yet`); two or more: the first step is the gap (reason names them). `tree`
  None is no location.
- `done(tree, engine, item)`: `[(step, relative path)]` for each step whose rule holds and
  has an artifact, for PostToolUse.
- `own(engine, tree, path)`: True when `path` is under one of `OWN[engine]` in `tree`.
- `once(root, kind, payload, keys)`: append `kind` unless today's `events.jsonl` already
  has that kind with the same values for `keys`; reads only lines containing `"spec.`
  (the status-line prefilter idea, #346). `# ponytail:` read then append is not one
  transaction; a race writes a duplicate count, never a decision input.
- `check(root, config, item, row, tree, *, build, where)`: the one decision.
  1. `mode` off: `(0, '')`.
  2. `skip(config, row)`; when it is a lead-tier skip and `build`, recompute with
     `computed = (row.get('gates') or {}).get('computed') or dispatch.tier(root, config,
     row)['computed']` (imported inside; the build loop has no tier record yet). Still
     skipped: `once('spec.skipped', {item, reason}, ('item',))`, `(0, '')`.
  3. `status(tree, engine, item, build=build)` None: `(0, '')`.
  4. advisory: `once('spec.warned', {item, engine, step, where}, ('item',))`, `(0, '')`.
  5. strict: `(1, text)` where text is
     `spec mode ({engine} strict): {item} needs {step} first: {command}; artifact {artifact}
     in {location or the LOCATION glob}. {reason}` plus, when `MARKER[engine]` is absent
     from the repository (`tree`), ` {engine} is not installed here: {INSTALL[engine]}.`,
     plus ` A trivial item: the owner runs wuwei plan set {item} spec=skipped --reason
     <why>.` The phrase `{step} first: {command}` is what tests assert
     (`specify first: /speckit.specify`).
- `record(root, config, item, row, tree)`: PostToolUse. Off or skipped: nothing. Else
  `once('spec.step', {item, engine, step, path}, ('item', 'step'))` for each of
  `done(...)`.
- `named(root, config, item, row, tree, text)`: SubagentStop. Off or skipped: `(0, '')`.
  The names are the resolved location relative to `tree` (spec-kit directory, OpenSpec
  change) or the two superpowers files; none resolved counts as missing. All present in
  `text`: `(0, '')`; else advisory `once('spec.warned', where='stop')` and `(0, '')`;
  strict `(1, 'spec mode: name your spec artifacts in your final message: <names or the
  next step>')`.
- `brief_line(config, item, row, tree, gate)`: None when off. Skipped (no re-check):
  `Spec: skipped (<reason>)`. Builder: `Spec: <engine> <mode>; artifacts in <location or
  glob>; steps in order: <step> (<command>) -> <artifact>; ...; name the artifacts in your
  final message.` For spec-kit it adds `create the directory with
  .specify/scripts/bash/create-new-feature.sh --json --short-name <item lowercased>`.
  Gate: `Spec: <engine> artifacts: <location>` or `Spec: not found (<reason>)`.
- `present(path, engine, config)`: True/False for the marker directory under the repository
  path; superpowers reads `scanner.mcp.plugins_file` (expanded) as text and looks for
  `"superpowers@`; an unreadable file returns None (unmeasured). `none` returns True.
- `detect(paths, config)`: the first of `speckit`, `openspec`, `superpowers` present in
  any path, else `speckit`.

### Guard (`cli/wuwei/guards/spec.py`, new)

```python
from wuwei.exits import CLEAN, UNRUN
from wuwei.guards import Guard
```

- `_item(payload, path)`: `workspace.find_workspace(cwd)` (FileNotFoundError: then
  `workspace.worktree_workspace(path)`; None: return None). `state.read_state(root)`; the
  item whose `(root / row['worktree']).resolve()` contains `path`, deepest first. Returns
  `(root, item, row, tree)` or None. Imports `state` and `workspace` inside.
- `check_edit(payload)` (PreToolUse `Write|Edit|MultiEdit|NotebookEdit`): path from
  `file_path` or `notebook_path` against `cwd`; `_item` None: CLEAN. Then import
  `specmode`, load config, `own(...)`: CLEAN; else `specmode.check(..., build=False,
  where='edit')`. `(OSError, ValueError, KeyError, TypeError, UnicodeError)`: `(UNRUN,
  f'spec mode: {exc}')`.
- `check_record(payload)` (PostToolUse `Write|Edit|MultiEdit|NotebookEdit|Bash`): path is
  the file path, or `cwd` for Bash; `_item` None: CLEAN; `specmode.record(...)`; errors are
  `(UNRUN, reason)` (Claude Code shows them; the call already ran).
- `check_stop(payload)` (SubagentStop): `stop_hook_active` or a role other than
  `wuwei:builder`: CLEAN. `workspace.find_workspace(cwd)`; `guards.agent_launch.stopping_seat(payload, root)`
  gives `(directory, name, role)`; the seat's item from `brief.seats(state.read_state(directory=directory))`;
  its row and recorded worktree from today's state; no worktree: CLEAN. Then
  `specmode.named(..., payload['last_assistant_message'])`. Errors: UNRUN with reason.
- `GUARDS = [Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_edit),
  Guard('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', check_record),
  Guard('SubagentStop', None, check_stop)]`.
- `cli/wuwei/guards/__init__.py`: `MODULES['spec'] = {'PreToolUse':
  'Write|Edit|MultiEdit|NotebookEdit', 'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash',
  'SubagentStop': None}`; `AREAS['spec'] = None` (the check applies its own mode, like
  `agent_launch.check_mcp`). `test_import_map_matches_guard_tables` pins both.

### Build loop and backstop

- `cli/wuwei/commands/build.py` `complete_checks` (line 321): after the per-command loop
  and before `if not failures:` (line 343), read the item row; when its phase is
  `implement` or `fix`, call `specmode.check(root, config, item, row,
  Path(record['worktree']), build=True, where='gates')`; exit 1 appends `('spec',
  {'error': reason})` to `failures`; exit 2 raises ValueError (the command's exit 2 path).
  Load `config` once before (it is loaded at line 349 today only on failure). The
  signature, stuck rule, park and continue feedback then apply unchanged.
- `cli/wuwei/dispatch.py` `next_step` (line 148): right after the tier block (line 180),
  when `phase == 'gate'`, `specmode.check(root, config, item, row, (root /
  row['worktree']).resolve() if row.get('worktree') else None, build=True,
  where='dispatch')`; exit 1 raises `Refused(reason)`. Load config once for both blocks.

### Owner action `plan set`

- `cli/wuwei/commands/plan.py` `register`: `set` subparser with `item`, `assignment`
  (`spec=required` or `spec=skipped`) and `--reason`; `run` prints `plan.set_spec(...)`.
  Exits come from the existing handlers: StateError 1, ValueError 2.
- `cli/wuwei/plan.py` `set_spec(item, assignment, reason=None, root=None)`: key must be
  `spec`, value `required` or `skipped` (ValueError otherwise); `skipped` needs a nonblank
  reason (ValueError); reason folded to one line like `dispose`; unknown item is
  StateError naming today's items. `state._write_state(update, root, reserved=False,
  kind='spec.override', payload={'item', 'value', 'reason'})` setting
  `items.<item>.spec = {'value': ..., 'reason': ...}`. Returns `<item>: spec <value>`.
- `cli/wuwei/state.py` `_producer_error` items map: `'spec': 'wuwei plan set'`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `spec.step`, `spec.skipped`,
  `spec.warned`: `'wuwei hook, wuwei build or wuwei dispatch next'`; `spec.override`:
  `'owner host wuwei plan set'`. (Every non-`note` kind is already refused; this names the
  producer in the refusal.)
- `cli/wuwei/guards/protect_state.py` `_OWNER_ACTIONS`: `('plan', 'set'): 'Spec overrides
  are an owner action on the host, outside agent tools.'` Other `plan` verbs stay seat
  commands (the table is per pair).

### Briefs, orientation, report

- `cli/wuwei/brief.py` `write`: after `header.append(f'Track: {track}')` (line 277), for
  `role == 'builder'` or `gate`, `line = specmode.brief_line(config, item, current, tree,
  gate)`; append when not None.
- `cli/wuwei/commands/next.py` `orientation(row, posture, spec=None)`: one line `Spec:
  {spec}` after the posture paragraph when given. `cli/wuwei/guards/lifecycle.py:44`
  passes `specmode.label(config)`.
- `cli/wuwei/report.py` `build`: after the Shadow block, `## Spec warnings` with `- <item>:
  <step> (<where>)` per `spec.warned` event of the day, only when there are any (reuse
  `watch.records`, already imported there).

### Presence: doctor, setup, interview

- `cli/wuwei/commands/doctor.py` repo loop (after the `fast_checks` row, line 294): one
  row `<name> spec`: engine `none` or mode `off`: ok `<engine> <mode>`; `present` True: ok
  `<engine> found`; False: fail `<engine> not found in <path>` with fix `INSTALL[engine]`;
  None: unmeasured with the plugins-file reason.
- `cli/wuwei/interview.py` `QUESTIONS`: after `posture`, `{'id': 'spec', 'scope':
  'workspace', 'header': 'Spec engine', 'question': 'Which spec engine do your
  repositories use?', 'choices': (('spec-kit', 'Each change gets a spec, a plan, tasks and
  an analysis before code; the hooks keep the steps in order (spec-kit).', {'spec.engine':
  'speckit'}), ('superpowers', 'A design and a plan from the superpowers skills before code
  (superpowers).', {'spec.engine': 'superpowers'}), ('OpenSpec', 'A proposal, specs, tasks
  and a validation before code (OpenSpec).', {'spec.engine': 'openspec'}), ('None', 'No
  spec step; the build loop starts at the code.', {'spec.engine': 'none'})), 'free':
  None}`. `ask(ids, repos, first=None)`: `first` maps a question id to a choice label
  moved to position 1.
- `cli/wuwei/commands/setup.py` (line 288): `engine = specmode.detect([resolved repo paths
  of staged_cfg], staged_cfg)`; pass `first={'spec': <the choice label whose effect is
  spec.engine = engine>}` to `interview.ask`.

### Agent-facing and owner-facing text

- `charters/builder.md` steps 1 and 2: follow the brief's `Spec:` line; run each step of
  the configured engine in order with its command before editing source; the hooks refuse
  out-of-order edits; name the artifacts in the final message; a skipped item says why.
  Bump the charter `version:` line if `tests/test_charters.py` or the overrides check
  requires it.
- `charters/lead.md` step 5: a `light` tier also skips the spec while `light` is in
  `spec.skip_tiers`; the diff re-checks it at the gates.
- `charters/planner.md` and `skills/wuwei-plan/SKILL.md`: one line each: a gap comes back
  as a failing check named `spec`; only the owner skips with `wuwei plan set <item>
  spec=skipped --reason <why>`.
- Regenerate `agents/` with `python3 -P -m wuwei agents build` (from `cli/`), then
  `agents check`.
- `docs/site/configuration.md`: a `[spec]` entry under `## Sections` (keys, defaults,
  modes, skip tiers with the tier names, `plan set`, install lines).
- `docs/site/concepts.md` glossary: `### Spec engine` and `### Strict mode` (at most two
  lines each), and `tests/test_docs.py` `GLOSSARY` gains `('Spec engine', r'spec engines?')`
  and `('Strict mode', r'strict mode')` in the page order; first uses in README, index and
  daily link to them.
- `docs/site/daily.md`: one paragraph in "4. Through the day": on a non-trivial item the
  builder runs the engine's steps first; how to skip one item.
- `docs/site/agent.md`: step 4 of "The day in order" names the spec steps; "What the
  hooks refuse" gains one bullet.

### Fixture days

- `tests/fakes/day.py` `Runtime.dispatch`, builder branch: on the first build write the
  spec-kit set for item A under `specs/001-a/` in `day.repo` (spec.md with `##
  Clarifications`, plan.md, tasks.md all checked, analysis.md with no CRITICAL or HIGH row,
  checklists/requirements.md all checked), each followed by `day.hook('PostToolUse',
  tool_name='Write', tool_input={'file_path': ...})`, then `day.hook('PreToolUse',
  tool_name='Write', tool_input={'file_path': memory/demo.py})` before the source write.
  Commit the spec files with the source change (git through the patched `subprocess.run`
  with an `env`, as `local_git` expects; `git.workspace_commit` accepts only procedure
  paths), so the tree stays clean for the stop and the gate brief. The builder's last
  message (and transcript line) is `Spec: specs/001-a\n` + RETRO.
- `tests/test_e2e_day.py`: in `test_scripted_day`, before `day.build`, one PreToolUse Write
  of `memory/demo.py` after the builder brief is refused with `specify first:
  /speckit.specify`; after the build, one `spec.step` event per step and none twice. New
  `test_light_item_skips_spec(day)`: the candidate carries `tier: light`; the build
  completes with no `spec.step` and one `spec.skipped`. Use `[spec]` defaults (no config
  change in the Day).
- `scripts/headless_e2e.py`: `fixture_plan` candidate A gets `'tier': 'light'`;
  `validate` requires a `spec.skipped` event for A; `tests/test_headless_e2e.py` evidence
  fixtures gain that event.

## What must not change

- `hook.py` flow, `guards.discover`, `guards.level` and `posture`; the #346 tests and
  their deny lists; `tests/test_hooks.py` bodies other than any table rows that list
  every guard module.
- The tier algorithm in `dispatch.tier` (only read), gate sets, the merge policy.
- `state.PHASES` (the existing `spec` phase stays unused), `_generic_allowed`.
- Design spec, constitution, `AGENTS.md` (411 owns them).
- Exit codes of existing commands; `wuwei next`'s one-line output.

## Test churn (expected, not scope creep)

With `speckit strict` the default, tests that move an item to `gate` without artifacts
fail at `complete_checks` or `dispatch next`. After T030 runs the suite, add `[spec]\nengine
= "none"` to the config text of each failing test that is not about spec mode (likely
`tests/test_build.py`, `test_build_next.py`, `test_dispatch.py`, `test_launch_contract.py`,
`test_pr_actions.py`, `test_linear_loop.py`, `test_operator_records.py`,
`test_steward.py`, `test_decision.py`, `test_signal_status.py`); never change an assertion
to make it pass. Tests that compare a whole brief header or the whole orientation block
gain the one new line. `tests/test_guard_mutation.py` `PROBES` gains one row per new check.

## Verification

- `python -m pytest -q` from the repository root, full suite green.
- `python -m pytest -q tests/test_hooks.py -k "imports or latency"` unchanged and green.
- `grep -rn "speckit\.\|analysis.md\|skip_tiers" cli/wuwei --include=*.py` lists only
  `specmode.py`, `workspace.py` (schema) and `interview.py` (choice effect).
- Every written file checked for em-dashes, emojis and absolute local paths.

## Deferred

- A STANDARD item in the paid `scripts/headless_e2e.py` run (needs the seat to run every
  spec-kit step for real; the offline scripted day covers it).
- Listing warned items in `wuwei next`'s one-line output (the report and the events carry
  them).
- Per-repository engines (one engine per workspace, 411 assumption).
