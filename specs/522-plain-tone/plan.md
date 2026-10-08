# Implementation Plan: Plain tone

**Branch**: `522-plain-tone` | **Date**: 2026-10-08 | **Spec**: `specs/522-plain-tone/spec.md`

## Summary

Add one measure and one rule, then rewrite the texts to it. `cli/wuwei/commands/lint.py`
holds `measure(*texts)` and the read-only command `wuwei lint tone <path>...`.
`charters/_common-authoring.md` gets a five-line `## Plain tone` section. `tests/test_tone.py`
measures five text classes (reasons, cards, skills, charters, docs) against budgets, and
checks `wuwei why last refusal` and three rendered cards. Then the pass rewrites the reasons,
cards, skills, charters, concepts.md, daily.md and README.md, meaning unchanged, and updates
every test that asserted a changed text.

Order matters: build the lint first, measure the base and record it, then do the pass, then
set the budgets from the after numbers.

## Technical Context

- Python 3.11+ stdlib only (`re`, `pathlib`, `sys`). pytest for tests.
- No state, events, config keys, guards or adapters change. No new core module.
- `tests/test_invariants.py` does not exist on the base, so no invariant row is added.

## Constitution Check

- I (stdlib): `re` and `pathlib` only. Pass.
- II (three-state exits): the command returns 0 at the rule, 1 over it, 2 with a reason when
  it cannot read a path. Pass.
- III (one behaviour, one function): `measure` is the one measure; the command and the test
  both call it. Pass.
- IV (test first): every behaviour has a failing test task before its implementation. Pass.
- V (ponytail): one command module, a suffix regex for nominalisations (marked `ponytail:`),
  constants for the rule numbers, budgets as test constants. Pass.
- VII (security): read-only; it reads only the paths it is given. Pass.
- #530: no refusal added or changed; the lint never refuses. #551: no planner path change.

## Changes

### New: `cli/wuwei/commands/lint.py`

Module docstring: "Measure prose against the plain tone rule in charters/_common-authoring.md."

```python
AVERAGE, LONGEST = 20, 35
# ponytail: a suffix heuristic with false hits ("comment", "decision"); compare rates over
# time, and move to a word list if the rate misleads.
NOMINAL = r'\b[a-z]{3,}(?:tion|sion|ment|ance|ence|ness|ity)s?\b'
```

- `_blocks(text)`: the prose of one text as a list of blocks; a sentence never crosses a
  block. In order:
  1. drop front matter (`\A---\n.*?\n---\n`, DOTALL), fenced code blocks (```` ```.*?``` ````,
     DOTALL) and HTML comments;
  2. replace each inline code span `` `...` `` with the one word `code`, and each link
     `[text](url)` with `text`;
  3. walk the lines: a blank line, a heading (`#` first) or a table separator row ends the
     block and is dropped; a table row (`|` first) yields each cell as its own block; a list
     item (`- `, `* ` or `<n>. ` first) starts a new block; any other line joins the current
     block.
- `sentences(text)`: for each block, collapse whitespace and split on
  `(?<=[.!?])\s+`; each piece's length is its count of whitespace tokens that contain a word
  character or `{` (so `{}` is one word); empty pieces are skipped. Returns the list of
  lengths. A semicolon is not a boundary (spec A1).
- `measure(*texts)`: sums over the texts, each split on its own; returns
  `{'sentences', 'words', 'average', 'longest', 'over', 'nominalisations'}` where `average`
  is words / sentences (0.0 with no sentence), `over` counts lengths above `LONGEST`, and
  `nominalisations` counts `NOMINAL` matches (case-insensitive) over the joined block text,
  so code is not counted.
- `at_rule(m)`: `m['average'] < AVERAGE and m['over'] == 0`.
- `line(name, m)`: `f"{name}: average {m['average']:.1f} words, longest {m['longest']}, {m['over']} over 35, {m['sentences']} sentences, {m['nominalisations']} nominalisations ({rate:.1f} per 100 words), {'at' if at_rule(m) else 'over'} the rule"`
  with `rate = 100 * nominalisations / words` (0.0 with no word).
- `register(subparsers)`: parser `lint` (help `Measure prose against a writing rule`) with
  subparsers `dest='lint_action', required=True`; `tone` (help `Report sentence length and
  nominalisations per file against the plain tone rule`) takes `paths`, `nargs='+'`, and sets
  `func=run_tone`.
- `run_tone(args)`: expand each path in order: a directory gives `sorted(path.rglob('*.md'))`,
  a file gives itself. A missing path or a directory with no `*.md` prints
  `wuwei lint tone: {path} is not a file or a directory with markdown files; pass a markdown file or a directory of them`
  to stderr and returns 2. Read each with `encoding='utf-8'`; an `OSError` or
  `UnicodeDecodeError` prints `wuwei lint tone: cannot read {path} ({exc}); pass a readable UTF-8 file`
  and returns 2. Print `line(str(path), measure(text))` per file; with more than one file
  print `line('total', measure(*texts))`. Return 1 if any file is not `at_rule`, else 0.
  No workspace lookup.

### `cli/wuwei/commands/__init__.py`

Add `'lint tone'` to `READ_ONLY`. Nothing else.

### `cli/wuwei/__main__.py`

Add `lint` to the Plumbing group string in `GROUPS` (alphabetical: after `index`).

### `docs/site/reference.md`

One row in the command table, after `bin/wuwei integrity`:
`| \`bin/wuwei lint\` | Plumbing: \`lint tone <path>...\` reports each file's average and longest sentence, sentences over 35 words and nominalisations against the plain tone rule; exit 1 over the rule. | |`
Keep the row itself at the rule (split it if the lint says so).

### `charters/_common-authoring.md`

A new section after `## Writing for a person` (the ten-item checklist there stays exactly ten
items; `tests/test_charters.py:179` counts them):

```markdown
## Plain tone

Text in WUWEI's voice follows five rules; `bin/wuwei lint tone <path>` measures the first.

1. Keep sentences under 20 words on average and none over 35.
2. Put one idea in each sentence.
3. Use the verb, not a noun made from it: "close measures it", not "the measurement by close".
4. Use the plain word (use, run, send, ask) and drop chains of qualifiers.
5. Call the owner "you" in docs and cards, and "the owner" in reasons a seat reads (#362).
```

Bump the charter's patch version; rebuild the agents (`bin/wuwei agents build`).

### `cli/wuwei/plan.py` (`gate_widget`, lines 247-272)

The Approve description becomes short sentences: join the parts with `'. '` instead of
`'; '`, each part starting with a capital (`part[:1].upper() + part[1:]`), and end with `.`.
The parts and their content stay as they are. Rewrite the Change something description into
two or three short sentences with the same content (goals, queue, seat policy, CAP and seats
per goal, envelope and carry-over asked separately; CAP is derived; a changed CAP is recorded
as config `cap`).

### The pass (meaning unchanged)

Work file by file; after each file run its focused tests. Before changing any text, grep
`tests/` and `docs/` for a distinctive fragment of it and update every match in the same
step, with the same meaning. Never delete an assertion.

- Reasons: every reason literal with a sentence over 25 words (list them with
  `test_reasons.all_reasons()` and `sentences`), and every reason under `cli/wuwei/guards/`.
  Keep the #362 shape (what happened, `; `, next step), keep the next step verb that
  `NEXT_STEP` matches, keep family suffixes (`exits.DAMAGED` and the rest) as they are, keep
  the pronoun rule (seat-facing: "the owner"; person-facing scope in
  `tests/test_reasons.py:PERSON_MODULES`/`PERSON_PARTS`: "you"). Keep the first `; ` as the
  rule/fix split `wuwei why` uses (`commands/why.py:194`). Split long ones into two
  sentences, turn nouns into verbs, use the plain word. Rewrite `exits.py` families only if
  they break the rule.
- Cards: the literal questions and option descriptions in every `widget(` call
  (`commands/close.py`, `commands/consolidate.py`, `commands/telemetry.py`,
  `commands/doctor.py`, `drafts.py`, `plan.py`, `interview.py`) and the questions and choice
  descriptions in `interview.QUESTIONS`. Cards say "you", never "the owner".
- Skills: `skills/wuwei-plan`, `wuwei-report`, `wuwei-retro`, `wuwei-consolidate`
  (`SKILL.md`). Keep every command, path and loop step (`tests/test_skill_evals.py`,
  `tests/test_path_day.py`, `tests/test_charters.py:236` no-blocking rule read these). Skills
  are seat-facing: "the owner".
- Charters: every `charters/*.md`, each to 0 over 35. Keep sentences that
  `tests/test_charters.py` pins to one home in that home. Patch-bump each changed charter's
  `version:`; run `bin/wuwei agents build`, then `bin/wuwei agents check` (exit 0).
- Docs: `docs/site/concepts.md`, `docs/site/daily.md`, `README.md`, each to the rule. Keep
  headings, anchors, links, section order, list counts and the phrases `tests/test_docs.py`
  asserts (README paragraph and line limits included). The owner is "you". Replace the five
  "the owner" mentions in README with "you" where the text addresses the reader.
- Every rewrite passes the humanizer checklist in `_common-authoring.md` (no tells, no em
  dash, no emoji).

### New: `tests/test_tone.py`

- Imports `measure`, `sentences`, `at_rule`, `AVERAGE`, `LONGEST` from
  `wuwei.commands.lint`, and `all_reasons`, `_sources`, `_text` from `test_reasons`
  (cross-test imports follow `tests/test_why.py`, which imports `test_decision`).
- `classes()` returns `{name: [texts]}`:
  - `reasons`: `[text for _, _, text, _, _ in all_reasons()]`;
  - `cards`: for each module in `_sources()`, every `ast.Call` whose function name (`id` or
    `attr`) is `widget` with args: the texts of `_text(args[0])` (it returns `(text, family)`
    pairs), and when `args[2]` is a list or tuple,
    `_text(elt.elts[1])` for each two-element tuple in it; plus `row['question']` and each
    choice description from `interview.QUESTIONS`;
  - `skills`: each `skills/*/SKILL.md`; `charters`: each `charters/*.md`; `docs`: each
    `docs/site/*.md` and `README.md`.
- `BUDGETS = {name: (over, nominal_rate)}`: over is 0 for reasons, cards, skills and
  charters; docs is the base count of the docs pages outside the pass (T006). Nominal rates
  are the after numbers rounded up to one decimal (T020).
- The budget test asserts per class: `average < AVERAGE`, `over <= budget`,
  `rate <= nominal budget`; the failure message is `line(name, m)`.

### New: `specs/522-plain-tone/research.md`

The before and after table: per class, average, longest, over 35 and nominalisations per 100
words, from `measure` over `classes()`. The before column comes from the base before any
text changes (T006); the after column at the end (T020). The pull request copies it.

## What must not change

- No guard decision, exit code, posture behaviour, event kind, state key or config key.
- The #362 reason shape and pronoun rule; `exits.FAMILIES` names; the `; ` rule/fix split.
- Command names, flags, record command strings in cards (`record`), card headers (12
  characters at most) and option labels the answer commands parse (`carry`, `park`, `Skip`,
  `Approve`, `Change something`, interview labels).
- The ten-item Writing for a person checklist, the humanizer wording the charters test pins,
  every sentence `tests/test_charters.py` pins to one home.
- README and docs headings, anchors and section order; skill loop commands.
- No absolute local path, client or repository name, em dash or emoji in any file.

## Existing tests at risk

`tests/test_docs.py` (README, concepts, daily phrases and limits), `tests/test_charters.py`,
`tests/test_agents.py` (drift), `tests/test_skill_evals.py`, `tests/test_path_day.py`,
`tests/test_next.py`, `tests/test_plan.py:342` (`claims PR-12` becomes `Claims PR-12`) and
`:354`, `tests/test_reasons.py`, `tests/test_why.py`, `tests/test_protect_state.py` and every
guard test that matches reason text, `tests/test_guide.py` (the read-only line gains
`lint tone`), `tests/test_cli_known_command.py` (sets), `tests/test_e2e_day.py`,
`tests/test_interview.py`, `tests/test_stop.py:924` (close widget), `tests/test_doctor.py`.
Update each to the new text with the same meaning.
