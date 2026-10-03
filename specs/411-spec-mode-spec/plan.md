# Implementation Plan: Specification mode, a configured spec engine (spec-kit by default) whose steps the hooks enforce on every non-trivial item, with superpowers and OpenSpec as alternatives

**Branch**: `411-spec-mode-spec` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

A spec-only change. The builder pastes the amendment text below into three files, edits it
only for a real conflict found in the consistency review, and shows the phrase check red on
`main` and green on the worktree:

- `docs/specs/2026-09-24-wuwei-design.md`: one new section, 5.10 Specification mode; two
  rows and one clause in the 4.1 hook table; one phrase in the 3.3 `config.toml` line.
- `.specify/memory/constitution.md`: one Workflow bullet (WUWEI itself runs under spec-kit
  strict); version 1.2.0, amended 2026-10-03.
- `AGENTS.md`: the spec-kit line lists the full strict step order.

No runtime code, no charter, skill, template, docs site page or test changes. The
implementation issue builds from 5.10 and the "Deferred" map at the end.

## Technical Context

Markdown only. The verification check is a throwaway stdlib script run from a scratch
directory outside the repository, never committed (the issue's acceptance: only the spec
changes). `tests/test_docs.py::test_guard_boundaries_are_stated_once` reads 4.5, 9.1,
section 10 and the constitution's "design reconsideration recorded in its spec" and
"#222"; none of these change. `tests/test_calibrate.py` reads `AGENTS.md:1` and
`.specify/memory/constitution.md:1`; both first lines stay.

## Constitution Check

- I (stdlib), II (three-state exits), III (one behaviour, one function): no runtime code.
  5.10 keeps III for the implementation: one helper serves the guard, the build loop,
  dispatch, the briefs, setup and doctor.
- IV (test first): the phrase check runs red against a `git archive main` export before
  the amendment is pasted, then green on the worktree. Red is never produced by stashing or
  reverting the working tree.
- V (ponytail): one section; config only for what the owner asked to choose (engine, mode,
  skip tiers); no per-repository engine; no new posture area (`spec.mode` is the only
  knob); no new trust record beyond the owner's `plan set`; artifacts are files the engines
  already write, plus one saved report where an engine writes none (`analysis.md`,
  `validation.json`); reuse of the lead and diff tiers (#280), the item worktree and branch
  rule, the build loop's failing-check feedback, the owner-action table and
  `scanner.mcp.plugins_file`.
- VII (security): no refusal is weakened. Lowering the requirement for one item is an
  owner action; the artifacts are never treated as owner proof.
- Governance: the design spec is amended only by its owner; the owner's request is in the
  issue, and the owner merges. The constitution amendment carries its date.

## What changes (builder pastes, in order)

### A. Design 3.3, the `config.toml` line in the workspace tree

Replace `environment register, outward-text rules` (the second line of the `config.toml`
comment) with:

```markdown
                       environment register, outward-text rules, spec engine (5.10)
```

### B. Design 4.1 hook table

Insert after the row `| PreToolUse | Write or Edit on `state.json`, `events.jsonl` | ...`:

```markdown
| PreToolUse | Write, Edit, MultiEdit or NotebookEdit in an item worktree, outside the spec engine's directories | under spec mode, a step of the configured engine before implementation is not done for the item (5.10) |
```

Insert after the row `| PostToolUse | write to `decisions/gate-*.md` | ...`:

```markdown
| PostToolUse | Write, Edit, MultiEdit, NotebookEdit or Bash in an item worktree | never refuses; records each spec step whose artifact appeared (5.10) |
```

Replace the SubagentStop row with:

```markdown
| SubagentStop | a seat finishes | its three-line retro note is missing, or a builder's last message does not name its spec artifacts (5.10); otherwise records it, flagging a last message that asks the owner a question without a decision id (5.8) |
```

### C. Design 5.10, inserted after 5.9 and before `## 6. Memory`

```markdown
### 5.10 Specification mode (owner, 2026-10-03, #411)

Every item that is not trivial is specified with one configured spec engine before it is
built, and the hooks keep the engine's steps in order. `[spec]` in `config.toml`:

- `engine` (default `"speckit"`): `speckit`, `superpowers`, `openspec`, or `none`, which
  checks nothing (the behaviour before this section).
- `mode` (default `"strict"`): `strict` refuses at every enforcement point below;
  `advisory` lets each call through and records the first gap per item and day as one
  `spec.warned` event, which `wuwei next` and the report list; `off` checks nothing. The
  spec checks are not a 9.1 posture area: `mode` is their only setting, and under the
  `observe` posture `strict` runs as `advisory`.
- `skip_tiers` (default `["light"]`): the lead tiers (#280) whose items need no spec.

Engines. The builder runs every step, in order, with the engine's own command or skill;
the CLI reads only the artifacts, in the item's worktree, found by the item id lowercased
(the branch rule of `wuwei worktree add`). A step is done when its artifact is present and
reads as stated; a missing or unreadable artifact, or two paths that match the item, is not
done. The next step is the first one not done; artifact times are not compared. Every step
runs under `strict`; none is optional. Every engine ends with WUWEI's own validation: the
build loop's fast checks and the gates (5.3).

spec-kit: the feature directory is the one directory under `specs/` named `<item>` or
ending in `-<item>` (`create-new-feature.sh --short-name <item>`); each step is
`/speckit.<step>`.

| Step | Artifact in the feature directory |
|---|---|
| `specify` | `spec.md` |
| `clarify` | a `## Clarifications` section in `spec.md`: each question answered with the seat's recommendation as an assumption (5.3), or none |
| `plan` | `plan.md` |
| `tasks` | `tasks.md` |
| `analyze` | `analysis.md`, the saved report, with no finding of severity CRITICAL or HIGH |
| `checklist` | every item checked in `checklists/*.md` (`specify` writes `requirements.md`) |
| `implement` | every task in `tasks.md` checked |

superpowers: the skills of the superpowers plugin; the item is the topic in the file names.

| Step | Artifact |
|---|---|
| `brainstorming` | `docs/superpowers/specs/<date>-<item>-design.md` |
| `writing-plans` | `docs/superpowers/plans/<date>-<item>.md` |
| `executing-plans` with `test-driven-development` | every step in that plan checked |
| `verification-before-completion` | the fast checks and the gates; nothing more |

OpenSpec: the change is `openspec/changes/<item>/`, and after `archive` the one directory
under `openspec/changes/archive/` ending in `-<item>`; each step is `/openspec:<step>` or
the `openspec` command.

| Step | Artifact in the change |
|---|---|
| `proposal` | `proposal.md` |
| `specs` and `design` | at least one `specs/<capability>/spec.md`; `design.md` where the proposal needs one |
| `tasks` | `tasks.md` |
| `validate` | `validation.json`, the saved `openspec validate <item> --strict --json`, every entry valid |
| `apply` | every task in `tasks.md` checked |
| `archive` | the change moved under `openspec/changes/archive/`, before the gates |

The steps before implementation are the rows above `implement`, `executing-plans` and
`apply`.

Trivial items. An item needs no spec when the owner ran `wuwei plan set <item>
spec=skipped --reason <why>`, or when its lead tier (`items.<item>.tier`) is in
`skip_tiers` and the owner did not run `wuwei plan set <item> spec=required`. `plan set` is
an owner action, refused from agent tools like `config set`; it writes `items.<item>.spec`
(the value and the reason) and a `spec.override` event. A skipped item passes every check
below; the first check that sees it writes one `spec.skipped` event with the reason. A
tier skip holds only while the diff agrees: at the move to the gates, when the tier the
diff computes (#280, before the floor and the lead tier) is not in `skip_tiers`, the item
needs its spec after all.

Enforcement. Cooperative mistake prevention (9.1), in item worktrees only (the item whose
recorded worktree contains the path):

- PreToolUse on Write, Edit, MultiEdit and NotebookEdit refuses a path outside the
  engine's own directories (`specs/` and `.specify/`, `docs/superpowers/`, `openspec/`)
  while a step before implementation is not done. The reason names the next step, its
  artifact and its command, and the engine's install line when its files are absent from
  the repository.
- PostToolUse on the same tools and Bash records each step whose artifact newly appears as
  one `spec.step` event (item, engine, step, path) per item and day. It never refuses.
- The build loop (5.3) moves an item to the gates (implement to gate, fix to delta) only
  when every step is done, implementation included, on every runtime. A gap goes back to
  the builder as a failing check named `spec`, under the same error signature and stuck
  rule. `wuwei dispatch next` refuses the gates to an item at `gate` with a gap, naming
  the step.
- SubagentStop refuses a builder seat's stop while its last message does not name the
  item's artifacts (the spec-kit feature directory, the OpenSpec change, or the superpowers
  design and plan files).
- Briefs (5.2): the builder brief carries the engine's step table with the item's paths
  and commands, or the skip and its reason; gate briefs carry the artifact paths.

`spec.step`, `spec.skipped`, `spec.warned`, `spec.override` and `items.<item>.spec` are
written only by the CLI. The artifacts are written by the seat: they show the work was
done, never that the owner agreed; only `plan set` lowers the requirement for one item.

Engine presence. `wuwei setup` and `wuwei doctor` look for each engine in each configured
repository: `.specify/` for spec-kit, `openspec/` for OpenSpec, and a `superpowers@` entry
in Claude Code's installed plugins file (`scanner.mcp.plugins_file`) for superpowers.
Setup proposes the engine it finds, spec-kit when it finds none, and the interview asks
"Which spec engine do your repositories use?" with that answer first. A configured engine
absent from a repository is a doctor fail carrying its install line; `none` never is.
`wuwei calibrate` already reads `.specify/memory/constitution.md` as a convention source.

Seats and owner. The builder, lead and planner charters and the plan skill name the
configured engine's steps and the skip rule; the orientation block (`wuwei next`) shows the
engine and mode; the docs glossary defines spec engine and strict mode, and the
configuration page documents `[spec]`.
```

### D. Constitution

Insert after the Workflow bullet "One GitHub issue is one spec-kit feature: ...":

```markdown
- Specification mode (design 5.10; amended 2026-10-03, #411): WUWEI itself runs under
  `engine = "speckit"` and `mode = "strict"`. Every feature runs `specify`, `clarify`,
  `plan`, `tasks`, `analyze`, `checklist` and `implement`, in that order, then the full
  suite and the review; none is optional. The `analyze` report is saved as `analysis.md` in
  the feature directory, and a CRITICAL or HIGH finding is resolved before `implement`. A
  trivial change skips the spec only as 5.10 allows (a light lead tier, or the owner's skip
  with a recorded reason), and its pull request says why.
```

Replace the last line with:

```markdown
**Version**: 1.2.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-03
```

### E. `AGENTS.md`

Replace the bullet that starts "Work follows spec-kit:" (five lines, ending "record
assumptions in the spec under Assumptions and move on.") with:

```markdown
- Work follows spec-kit in strict mode (constitution, Workflow): `speckit-specify`,
  `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-analyze` (save the report
  as `analysis.md`; resolve CRITICAL and HIGH findings), `speckit-checklist`, then
  `speckit-implement` (skills in `.agents/skills/`). One GitHub issue is one feature,
  created with `.specify/scripts/bash/create-new-feature.sh --json --number <issue>
  --short-name <slug> "<description>"`. Do not ask clarifying questions; answer them with
  your recommendation, record assumptions in the spec under Assumptions and move on.
```

## Design decisions the builder must check against the issue

- Numbering: 5.10, not the issue's 5.9 (taken); hook rows in 4.1, not 4.5; the config line
  in 3.3, since the design has no configuration appendix.
- Config: `engine` speckit, `mode` strict, `skip_tiers` `["light"]` (lowercase, as the
  code spells tiers); one engine per workspace.
- Step tables as the issue lists them, plus OpenSpec `validate` as its analyze step; a
  step is done by its artifact; the next step is the first not done; no timestamps.
- Skip: owner `plan set` override first, else lead tier in `skip_tiers`; re-checked at the
  move to the gates against the diff's `computed` tier (before the floor, which defaults
  to `standard` and would otherwise void the skip).
- The move to the gates is enforced in the build loop (gap fed back as a failing `spec`
  check), with `dispatch next` as the backstop, because `gate` cannot return to
  `implement`.
- `advisory` warns once per item and day through `spec.warned`; `observe` runs `strict` as
  `advisory`; no new posture area.

## Consistency review (builder)

Read these against 5.10 and edit only the three files, only for a real conflict, keeping
the phrases the check pins:

- 3.3, 4.1, 4.4 (profile `strict` is a different setting; no conflict expected), 5.1
  (builder writes the spec), 5.2 (briefs and the mandate: clarify answers by
  recommendation), 5.3 (tracks, assume and record, build loop, engineering standards: test
  first), 5.7 (lead tiers through discovery), 9.1 (cooperative guards, guard scope,
  postures), 10.6 (the PreToolUse check runs on every Write or Edit in a workspace and
  shares the latency budget: it stops before reading state when the path is not in an
  item worktree).
- The constitution's Workflow bullets and `AGENTS.md` name the same seven steps in the same
  order.

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `.github/`, `docs/site/`, `README.md`.
- `tests/`: no file changes.
- Design 4.5, 9.1 and section 10, and the constitution's Cycle budget bullet: untouched, so
  `test_guard_boundaries_are_stated_once` keeps passing.
- The first lines of `AGENTS.md` and the constitution (`test_calibrate` cites `:1`).

## Verification commands

Run from the repository root. `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs .specify/memory AGENTS.md | tar -x -C <scratch>/main
python3 <scratch>/check_411.py <scratch>/main   # must fail: AssertionError: 5.10 section
python3 <scratch>/check_411.py .                # must print: OK: specification mode stated once
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md   # must be empty
python -m pytest -q
```

`<scratch>/check_411.py`:

```python
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
spec = (root / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
constitution = (root / '.specify/memory/constitution.md').read_text()
agents = (root / 'AGENTS.md').read_text()
flat = lambda text: ' '.join(text.split())
part = lambda pattern: flat((re.search(pattern, spec, re.S | re.M) or [''])[0])
mode = part(r'^### 5\.10 Specification mode.*?(?=^## )')
assert mode, '5.10 section'
hooks = part(r'^### 4\.1 .*?(?=^### )')
layout = part(r'^### 3\.3 .*?(?=^### )')
for phrase in ('`engine` (default `"speckit"`)', '`speckit`, `superpowers`, `openspec`, or `none`',
               '`mode` (default `"strict"`)', '`advisory` lets each call through', '`off` checks nothing',
               '`skip_tiers` (default `["light"]`)', 'not a 9.1 posture area',
               'under the `observe` posture `strict` runs as `advisory`',
               'found by the item id lowercased', 'two paths that match the item, is not done',
               'The next step is the first one not done; artifact times are not compared',
               'Every step runs under `strict`; none is optional', "WUWEI's own validation",
               '`create-new-feature.sh --short-name <item>`', '`/speckit.<step>`',
               'a `## Clarifications` section in `spec.md`', '`analysis.md`, the saved report',
               'severity CRITICAL or HIGH', '`specify` writes `requirements.md`',
               '`docs/superpowers/specs/<date>-<item>-design.md`', '`docs/superpowers/plans/<date>-<item>.md`',
               '`openspec/changes/<item>/`', '`openspec validate <item> --strict --json`',
               'before the gates', 'The steps before implementation are the rows above',
               '`wuwei plan set <item> spec=skipped --reason <why>`', '`wuwei plan set <item> spec=required`',
               'refused from agent tools like `config set`', '`items.<item>.spec`', '`spec.override`',
               'one `spec.skipped` event', 'before the floor and the lead tier',
               'Cooperative mistake prevention (9.1), in item worktrees only',
               'PreToolUse on Write, Edit, MultiEdit and NotebookEdit',
               '(`specs/` and `.specify/`, `docs/superpowers/`, `openspec/`)', 'the engine\'s install line',
               'PostToolUse on the same tools and Bash', 'one `spec.step` event', 'It never refuses',
               'implement to gate, fix to delta', 'on every runtime', 'failing check named `spec`',
               '`wuwei dispatch next` refuses the gates', 'SubagentStop refuses a builder seat',
               'gate briefs carry the artifact paths', 'written only by the CLI',
               'never that the owner agreed', '`superpowers@`', '`scanner.mcp.plugins_file`',
               'spec-kit when it finds none', '"Which spec engine do your repositories use?"',
               'doctor fail carrying its install line', '`none` never is',
               'the orientation block (`wuwei next`) shows the engine and mode',
               'glossary defines spec engine and strict mode', 'documents `[spec]`'):
    assert phrase in mode, phrase
for steps in (('specify', 'clarify', 'plan', 'tasks', 'analyze', 'checklist', 'implement'),
              ('brainstorming', 'writing-plans', 'executing-plans', 'verification-before-completion'),
              ('proposal', 'specs', 'tasks', 'validate', 'apply', 'archive')):
    start = mode.index(f'| `{steps[0]}` |')
    found = [mode.index(f'| `{step}`', start) for step in steps]
    assert found == sorted(found), steps
whole = flat(spec)
for once in ('(default `"speckit"`)', '(default `"strict"`)', '(default `["light"]`)',
             'Which spec engine do your repositories use?'):
    assert whole.count(once) == 1, once
assert hooks.count('(5.10)') == 3, '4.1 rows'
assert "a builder's last message does not name its spec artifacts (5.10)" in hooks
assert 'outside the spec engine\'s directories' in hooks and 'records each spec step' in hooks
assert 'spec engine (5.10)' in layout
law = flat(constitution)
for phrase in ('Specification mode (design 5.10', '`engine = "speckit"` and `mode = "strict"`',
               '`specify`, `clarify`, `plan`, `tasks`, `analyze`, `checklist` and `implement`, in that order',
               'none is optional', '`analysis.md`', 'CRITICAL or HIGH finding is resolved before `implement`',
               'only as 5.10 allows', '**Version**: 1.2.0', '**Last Amended**: 2026-10-03',
               'design reconsideration recorded in its spec', '#222'):
    assert phrase in law, phrase
guide = flat(agents)
order = [guide.index(f'`speckit-{step}`') for step in
         ('specify', 'clarify', 'plan', 'tasks', 'analyze', 'checklist', 'implement')]
assert order == sorted(order), 'AGENTS.md step order'
for text in (spec, constitution, agents):
    assert '\N{EM DASH}' not in text and not any(ord(c) >= 0x1F000 for c in text)
print('OK: specification mode stated once')
```

## Deferred (the implementation issue)

The map below is what 5.10 implies on `main` at e0c32d1; the implementation issue's plan
owns the details.

- One shared helper, `cli/wuwei/spec.py` (new): the three step tables (step, artifact
  rule, command), `location(tree, engine, item)`, `gaps(tree, engine, item, through)` (the
  first step not done, before implementation or through it), `skip(config, row,
  computed=None)` (override, then lead tier, then the diff re-check), the effective mode
  (`observe` lowers `strict`), the once-per-item-and-day event writers, presence detection
  and the install lines. Every caller below uses it; none re-implements a rule.
- Config: `workspace.SCHEMA["spec"] = {"engine": (str, "speckit", ("speckit",
  "superpowers", "openspec", "none")), "mode": (str, "strict", ("strict", "advisory",
  "off")), "skip_tiers": [(str, None, ("light", "standard", "full")), ["light"]]}`;
  `templates/workspace/config.toml` `[spec]`; `docs/site/configuration.md` `[spec]` (pinned
  by `test_configuration_names_every_config_section`).
- Guard: `cli/wuwei/guards/spec.py` (new) with PreToolUse `Write|Edit|MultiEdit|NotebookEdit`,
  PostToolUse `Write|Edit|MultiEdit|NotebookEdit|Bash` and SubagentStop checks; register
  in `guards.MODULES`, and `guards.AREAS['spec'] = None` (it applies its own mode, like
  `agent_launch.check_mcp`). Item from the path: `workspace.worktree_workspace` then the
  state item whose `worktree` contains the path; the SubagentStop seat from
  `guards.agent_launch.stopping_seat`.
- Build loop: `cli/wuwei/commands/build.py` `complete_checks`, before
  `state.transition(item, after)`: a gap becomes a failure `('spec', {...})` so the
  signature and stuck rule apply; the tier re-check calls `dispatch.tier(...)['computed']`.
  Backstop: `cli/wuwei/dispatch.py` `next_step`, phase `gate`, raises `Refused`.
- Briefs: `cli/wuwei/brief.py` `write`, one `Spec:` header line (builder: the step table or
  the skip; gates: the artifact paths).
- Owner action: `wuwei plan set` in `cli/wuwei/commands/plan.py` and `cli/wuwei/plan.py`;
  `('plan', 'set')` in `guards/protect_state.py` `_OWNER_ACTIONS`; `items.<item>.spec` in
  `state._producer_error` (written by `wuwei plan set`); `spec.step`, `spec.skipped`,
  `spec.warned`, `spec.override` in `commands/event.py` `EVENT_PRODUCERS`.
- Orientation: `cli/wuwei/commands/next.py`, one `Spec:` line (engine, mode, warned items).
- Presence: `cli/wuwei/commands/doctor.py` one engine row per repository;
  `cli/wuwei/commands/setup.py` proposes the detected engine; `cli/wuwei/interview.py`
  `QUESTIONS` gains `spec` (workspace scope, header "Spec engine", choices spec-kit,
  superpowers, OpenSpec, none, each setting `spec.engine`, plain words first).
- Install lines for the doctor row and the refusal: spec-kit `uvx --from
  git+https://github.com/github/spec-kit.git specify init --here --ai claude`; superpowers
  `/plugin marketplace add obra/superpowers-marketplace`, then `/plugin install
  superpowers@superpowers-marketplace`; OpenSpec `npm install -g @fission-ai/openspec`,
  then `openspec init`.
- Agent-facing text: `charters/builder.md` (steps 1 and 2 name the engine's steps),
  `charters/lead.md` (a `light` tier also skips the spec, re-checked against the diff),
  `charters/planner.md`, `skills/wuwei-plan/SKILL.md`; regenerate `agents/`.
- Owner-facing text: `docs/site/concepts.md` glossary (spec engine, strict mode),
  `docs/site/configuration.md`, the interview page.
- Tests: `tests/test_spec.py` (helper tables per engine, skip order, diff re-check, exits
  0, 1 and 2), recorded hook payloads in `tests/test_hooks.py`, `tests/test_build.py`
  (failing `spec` check, stuck park), `tests/test_dispatch.py` (backstop),
  `tests/test_protect_state.py` (`plan set` refused from agent tools), `tests/test_doctor.py`,
  `tests/test_interview.py`, `tests/test_docs.py`; a mutation test for the new guard (10).
- Outside this repository: the delivery pipeline's implementation brief lists the four
  spec-kit steps; the orchestrator updates it to the seven when the constitution lands.
