# Implementation Plan: the workflow writes its own records

**Branch**: `357-records-by-workflow` | **Spec**: `specs/357-records-by-workflow/spec.md`

## Summary

Three small changes at the shared spots, plus text:

1. `goals.proposed` renders the lead's goal objects to `goals.md` text while `memory/goals.md`
   has no `## G-n` heading; `plan propose`, `rank` and `plan template` use it. `plan propose`
   writes the draft `days/<date>/goals.md` and shows the blocks as provisional in `plan.md`.
2. A PostToolUse AskUserQuestion recorder in `guards/decision.py` notes on the planner's
   session row which records (`goals`, `voice`) its answered morning gate questions named.
3. `protect_state._owner_action` lets a literal `goals edit --file` / `voice edit --file`
   through for that planner session under `observe` and `guarded`; under `strict`, and for
   the planner otherwise, it refuses with the host-terminal command appended.

Then a lint test over skills, CLI strings, site docs and templates, and the text it forces.

## Technical Context

Python 3.11+, stdlib only (`re`, `ast` in the test). Tests: pytest, in process, under
`tmp_path`, `WUWEI_WORKSPACE` and `WUWEI_NOW` set. One subprocess test for `goals edit`
reuses the existing `cli()` helper in `tests/test_owner_edits.py`.

## Constitution Check

- I stdlib only: yes. II exits: guard errors stay exit 2 (`check_bash` already catches
  `ValueError`/`OSError`); the recorder returns 2 with a reason on any read or write error.
- III one behaviour, one function: goal rendering lives once in `goals.py`; the morning
  citation test moves into one helper used by both `check_question` and the recorder.
- IV test first: every task pair below.
- V ponytail: no new command (`goals propose` skipped), no new top-level state key (the
  session row carries the record), no allowance for scripts, xargs or editor mode.
- VII security: the allowance needs today's planner registration, no `agent_id`, a recorded
  gate topic, a literal argv with `--file`, and a non-strict posture; the draft is a
  protected day file; the gate record is producer-owned state.

## Design

### 1. `cli/wuwei/goals.py`

Add, below `parse`:

```python
def defined(text):
    """memory/goals.md has at least one goal heading (the template's example is indented)."""
    return re.search(r'^## ', text, re.M) is not None


def proposed(text, goals):
    """(goals text, provisional): memory/goals.md, or while it has no goal heading, the
    lead's goal objects rendered as goals.md text and validated by parse."""
```

Rules for `proposed`:

- If `defined(text)` or `goals` is not a nonempty list of dicts: return `(text, False)`
  unchanged (callers parse it, so the template still raises `no goals` and string ids keep
  today's `goals must cite identifiers` path).
- Each dict must have exactly the keys `id`, `outcome`, `measure`, `target`, `date`,
  `priority`; values are `str` (priority `int`, not `bool`), and `str(value).splitlines()`
  must equal `[str(value)]` (one line, no injected heading). Otherwise
  `ValueError('proposed goals: ...')`.
- Render `# Goals`, blank line, then per goal `## <id>` and `<field>: <value>` for `FIELDS`
  in order, blank line between blocks; run `parse` on the result, re-raising its
  `ValueError` prefixed with `proposed goals: `. Return `(rendered, True)`.

### 2. `cli/wuwei/plan.py` (`propose`)

At lines 93-94 replace the read and parse with:

```python
goals_text, provisional = goals.proposed(
    (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'), data.get('goals'))
goal_list = goals.parse(goals_text)
if provisional:
    data = {**data, 'goals': list(goal_list)}
```

(`data` may not be a dict here; guard with `data.get` only when `isinstance(data, dict)`,
otherwise pass `None` so `_proposal` reports `proposal must be an object` as today.)

In the `plan.md` lines, the `## Goals to confirm` section becomes, when `provisional`:

```
## Goals to confirm
Provisional: proposed by the lead; the planner records days/<date>/goals.md on approval.
- G-1 (provisional)
  outcome: ...
  measure: ...
  target: ...
  date: ...
  priority: ...
```

and stays `- G-n` per goal otherwise. Next to the `proposal.json` write, write
`directory / 'goals.md'` with `goals_text` when provisional, else
`(directory / 'goals.md').unlink(missing_ok=True)` so no stale draft survives a re-propose
on confirmed goals. `_proposal`, `approve` and `add` are unchanged: they validate against
`memory/goals.md`, which is what keeps `plan approve --goals-confirmed` failing until the
planner has recorded the draft.

### 3. `cli/wuwei/commands/rank.py` (`run`)

Keep the `template` branch as is (parse `memory/goals.md` first). For an input file, read
and decode it first, then:

```python
text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
if isinstance(rows, dict):  # a whole lead JSON, such as proposal.json
    text, _ = goals.proposed(text, rows.get('goals'))
    rows = rows.get('candidates')
goal_list = goals.parse(text)
```

### 4. `cli/wuwei/commands/plan.py` (`template`)

When `goals.defined(text)` is false, print `goals` as one goal object
`{'id': 'G-1', 'outcome': 'Replace with the outcome', 'measure': 'Replace with the measure',
'target': 'Replace with the target', 'date': workspace.now().date().isoformat(),
'priority': 1}` and cite `G-1` in the candidate. When true, keep today's output. Delete the
unreachable `if not identifiers` branch (parse raises first).

### 5. `cli/wuwei/guards/decision.py`

- Extract the morning citation test from `check_question` (lines 121-131) into
  `gate_question(question, root)`: True when the question text or header starts with
  `Morning gate` and the text cites today's `plan.md` (same three citation forms, same
  regex). `check_question` calls it in place of the inline code; behaviour unchanged.
- Add `TOPICS = re.compile(r'(?<![\w-])(goals?|voice)(?![\w-])', re.I)` and
  `record_gate(payload)`:
  - out of scope (`scope(cwd)` is None) or `'agent_id' in payload`: `(0, '')`;
  - `session_id` must equal `state.read_state(root).get('planner_session_id')`, else
    `(0, '')`;
  - for each question dict in `tool_input['questions']` with `gate_question(...)` true,
    collect topics from `header + ' ' + question` (`goal`/`goals` maps to `goals`);
  - nothing collected: `(0, '')`; otherwise one `state._write_state(update, root,
    reserved=False, kind='gate.asked', payload={'session_id': ..., 'topics': [...]})`
    where `update` sets `data['sessions'][session]['gate_asked']` to the sorted union
    (a missing row raises, reported as exit 2: the planner registers before it asks);
  - `(OSError, ValueError, RuntimeError, TypeError, KeyError)`: `(2, f'gate record: {exc}')`.
- `GUARDS` gains `Guard('PostToolUse', 'AskUserQuestion', record_gate)`.

### 6. `cli/wuwei/guards/__init__.py`

`MODULES['decision']['PostToolUse']` becomes
`'Write|Edit|MultiEdit|NotebookEdit|Bash|AskUserQuestion'`
(`tests/test_hooks.py::test_import_map_matches_guard_tables` derives exactly that).

### 7. `cli/wuwei/guards/protect_state.py`

- `_GATE_EDITS = {('goals', 'edit'), ('voice', 'edit')}`.
- `_gate_edits(payload, root)` returns `(topics, planner)`:
  `(frozenset(), False)` when `root` is None, `'agent_id' in payload`, or `session_id` is
  not today's `planner_session_id`; `(frozenset(), True)` when
  `workspace.posture(workspace.load_config(root))[0] == 'strict'`; else
  `(frozenset(sessions[session].get('gate_asked', ())), True)`.
- `_owner_action(commands, text, relevant, cwd, script=False, edits=(frozenset(), False))`.
  At the owner-reason return (line 158):

  ```python
  if reason := _owner_reason((group, verb)):
      if (group, verb) in _GATE_EDITS and edits[1]:
          if group in edits[0] and any(w == '--file' or w.startswith('--file=') for w in action):
              continue
          return 1, f'{reason} Run it in a host terminal: {shlex.join(argv)}'
      return 1, reason
  ```

- `check_bash` (line 436): compute `edits = _gate_edits(payload, root) if owner_relevant
  else (frozenset(), False)` and pass it. `owner_script` (scripts) passes nothing, so a
  script stays refused.
- `_protected_name`: add `'goals.md'` to the `days/<date>/<name>` tuple.
- `_STATE_HINT`: replace "The owner edits config.toml, voice.md and goals.md outside agent
  tools." with "The planner records goals and voice with wuwei goals edit --file and voice
  edit --file after the morning gate; config changes go through wuwei config set."

### 8. Producer tables

- `cli/wuwei/state.py` `STATE_PRODUCERS['sessions']`: append
  `, wuwei hook PostToolUse (gate questions)`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS['gate.asked'] = 'wuwei hook PostToolUse'`.

### 9. Lint test `tests/test_owner_records_lint.py` (new)

- Scopes: `skills/**/SKILL.md`; every `ast.Constant` string under `cli/wuwei/**/*.py`
  (f-string parts included via `ast.walk`; comments are not strings); `docs/site/**/*.md`;
  `templates/**/*.md` and `templates/**/*.toml`.
- `PATTERN = re.compile(r"\bpaste\b|\bedit the file\b|\b(?:set|sets|record|records)\s+`?"
  r"(?:Outcome|Decided-by)\b|Decided-by: owner`? in\b|\badd\b[^.\n]*\bgoals\.md|"
  r"\bopen\s+`?\.wuwei/|replace this guide", re.I)`.
- For each match: the sentence is the span from the previous `. `, `? `, `! `, blank line
  or start, to the next terminator or end, whitespace collapsed; the location is
  `path:line`. A sentence in `ALLOWED` or `PENDING_354` is skipped.
- `ALLOWED` (exact sentences, each with a one-line reason comment): the credentials
  sentence in `docs/site/adapters.md` ("Edit the file as the owner; the existing state
  guard refuses agent writes to it.") and `docs/site/remote.md` ("Never paste the secret
  or the URI into a website.").
- `PENDING_354`: the three decision sentences #354 replaces (skill step 1, configuration
  docs, doctor fix line). Comment: `# removed by #354 (decide command); delete this set
  when it lands`. If #354 is on main at build time, leave the set out.
- Tests: `test_no_owner_hand_edit_instructions` (collects all, asserts the list is empty,
  message lists every `path:line: sentence`) and `test_lint_catches_planted_instruction`
  (the matcher reports "Paste these blocks into .wuwei/memory/goals.md." and does not
  report a whitelisted sentence).

### 10. Text

- `docs/specs/2026-09-24-wuwei-design.md` 5.2, after the Briefs paragraph:
  "Records (owner, 2026-10-03, #357). The records under `.wuwei/` are written by the
  workflow from the owner's answers; no step asks the owner to create or edit a file by
  hand. The owner answers questions (in the session, in the DM, or y/N at a terminal) and
  may edit any record afterwards; the planner records. The host terminal remains for the
  strict posture and for credentials."
  5.7 Goals: replace "Only the owner edits it; seats and the steward may propose changes
  (6.8) but" with "While it has none, the lead proposes goals in its JSON, the morning gate
  shows them and the planner records the approved blocks with `wuwei goals edit --file`
  (5.2); later, seats and the steward may propose changes (6.8) but".
- `skills/wuwei-plan/SKILL.md`: step 2, after the JSON keys: "When `memory/goals.md` has
  no `## G-n` block, `goals` is a list of goal objects with `id`, `outcome`, `measure`,
  `target`, `date` and `priority`, and candidates cite those ids." Step 4, goals question:
  "The goals come from the lead. When `plan.md` marks them provisional, show the proposed
  blocks in the goals question. On approval, record them with `wuwei goals edit --file
  .wuwei/days/<date>/goals.md` (and `wuwei voice edit --file <draft>` for approved voice
  lines); under strict the hook refuses and prints the command, so show that line to the
  owner for a host terminal. Never ask the owner to type or paste a record." Step 1's
  decision sentence stays for #354.
- `charters/lead.md` step 3: "cite the confirmed goal it serves from `memory/goals.md`, or
  while it has none the goal object you propose in `goals`, or mark it `unplanned`";
  regenerate `agents/lead.md` with `python3 -P -m wuwei agents build`
  (`tests/test_agents.py::test_checked_in_agents_match_charters_and_allowlist`).
- `templates/workspace/memory/goals.md`: replace the two owner lines with "The lead proposes
  goals at the morning plan, you confirm them in the gate question, and the planner records
  them here. You can edit them later with `bin/wuwei goals edit`." Keep the indented
  example block and the priority line; drop "only the owner edits this file".
- `docs/site/daily.md:66-67` and section 3, `docs/site/concepts.md:40,44`,
  `docs/site/configuration.md` Goals and discovery paragraph, `docs/site/reference.md`
  (`goals` row at line 76, host terminal actions row for `goals edit` and `voice edit`):
  the lead proposes, the gate confirms, the planner records with `--file`; the owner can
  edit later with `goals edit`; under strict it is a host-terminal command.

## What must not change

- `goals.parse`, `promotion.owner_edit`, `_owner_edit.run` and the vcs owner commit.
- `plan approve`, `plan add` and `_proposal` validation; approve still needs
  `--goals-confirmed` and a parsing `memory/goals.md`.
- Seat refusals: `tests/test_owner_edits.py::test_seat_cannot_edit_goals` and
  `test_first_seat_tool_uses_transcript_registration` pass with their exact reason strings.
- Every other owner action in `_OWNER_ACTIONS`, the script, xargs and opaque paths.
- `check_question` results for every existing test in `tests/test_decision*.py`.

## Project Structure

```
cli/wuwei/goals.py                     defined, proposed
cli/wuwei/plan.py                      propose: provisional goals, draft, plan.md section
cli/wuwei/commands/rank.py             proposed goals for a lead JSON
cli/wuwei/commands/plan.py             template on an empty goals.md
cli/wuwei/guards/decision.py           gate_question, record_gate, GUARDS
cli/wuwei/guards/__init__.py           MODULES decision PostToolUse matcher
cli/wuwei/guards/protect_state.py      _gate_edits, _owner_action allowance, draft protected, hint
cli/wuwei/state.py                     STATE_PRODUCERS sessions
cli/wuwei/commands/event.py            EVENT_PRODUCERS gate.asked
tests/test_goals_rank.py               proposed, rank on a lead JSON
tests/test_plan.py                     provisional propose, template
tests/test_owner_edits.py              gate allowance per posture and caller
tests/test_decision.py (or the file holding check_question tests)  record_gate
tests/test_owner_records_lint.py       new lint
docs, skill, charter, agents, template as in Design 10
```

## Test approach

- Fixture goal objects are neutral (`Ship the widget`, `widgets shipped`, `1`,
  `2026-10-30`, `1`; `G-2` the same with `Document the widget`).
- The gate tests build the workspace with `tests/test_owner_edits.py::workspace` (git
  workspace history) and a template `goals.md`, run `plan.propose` with the two goal
  objects, `plan.session('planner-1', root)`, then `decision.record_gate` with a
  PostToolUse payload (`session_id: planner-1`, no `agent_id`, one question
  `Morning gate (days/<date>/plan.md): confirm goals G-1 and G-2?`, header `Goals`),
  then `check_bash` with `bin/wuwei goals edit --file .wuwei/days/<date>/goals.md`, then
  `cli(root, 'goals', 'edit', '--file', <draft>)`, then `plan.approve(['A'], root,
  goals_confirmed=True)`. Postures via `[security]\nposture = "..."` in `config.toml`.
