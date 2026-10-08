# Implementation Plan: README Principles section, comparison removed (#561)

**Branch**: `561-readme-principles` | **Spec**: `specs/561-readme-principles/spec.md`

## Summary

Docs and docs tests only. Three files change: `README.md`, `NOTICE` and `tests/test_docs.py`.
No runtime code, no new module, no new helper. The tests reuse the helpers already in
`tests/test_docs.py` (`_plain`, the `section` and `flat` lambdas, `ROOT`) and the tone test
(`tests/test_tone.py::test_every_class_is_within_its_budget`) unchanged.

## Technical context

- Python 3.11+, pytest (dev only). Run: `python -m pytest -q tests/test_docs.py tests/test_tone.py`.
- `bin/wuwei lint tone README.md` gives the README's own reading (today: average 10.3, 1 over 35
  (the pinned hero alt), 3.6 nominalisations per 100 words). The budget that must hold is the
  docs class in `tests/test_tone.py` (77 long sentences, 3.0 per 100 words, average under 20).
  Keep every new sentence under 35 words and prefer verbs to "-tion/-ment/-ity" nouns.

## Constitution check

- Principle III, IV: each behaviour (a pinned README shape) gets its test change first.
- Principle V: no new files besides the spec artifacts; the landing rule is a few lines in the
  existing test file; no config, no helper module.
- #530 and #551: nothing here adds a guard, a refusal or a planner step. No invariant row.
- Writing: no emojis, no em dashes, no absolute local paths, "you" for the reader, no bold
  labels, no "professional".

## Changes

### 1. `tests/test_docs.py` (first, red)

- `test_readme_install_and_hero` (line 119): remove `'#00C9A7'` from the README phrase tuple
  and add `assert '#00C9A7' not in readme and 'brand accent' not in readme.lower()`. The SVG
  assertions on `#00C9A7` stay.
  Also assert `'deploy' not in` the "What WUWEI is and is not" section (principle 8 carries it).
- Replace `test_readme_compares_with_other_tools` (lines 136 to 158) with
  `test_readme_states_the_principles`:
  - `for gone in ('## How WUWEI compares', '### How they compose', '## Philosophy', 'BMAD',
    'kiro.dev', 'Who plans the day'): assert gone not in readme`.
  - `section = readme.split('\n## Principles\n', 1)[1].split('\n## ', 1)[0]`; the non-blank
    lines are exactly nine, each matching `^(\d)\. ` with numbers 1 to 9 (one line per item).
  - A module-level tuple `PRINCIPLES` of nine `(phrases, link)` pairs, checked in order on the
    lowercased item text and the raw item:
    1. `('model walks it', 'wuwei next', 'judgement')`, `'(docs/site/agent.md'`
    2. `('observe', 'guarded', 'warning or a card', 'floor', 'records', 'strict')`, `'(docs/site/security.md#security-posture)'`
    3. `('moment of action', 'invariant', 'code host')`, `'(docs/site/concepts.md#guards)'`
    4. `('mit cisr', 'routine', 'mandate', 'strategic', 'one-way', 'card')`, `'(docs/site/concepts.md#decision-classes-and-cruise-levels)'`
    5. `('ledger', 'ceiling', 'novel', 'undo', 'error budget', 'brier', 'shadow')`, `'(docs/site/daily.md#cruise-answers)'`
    6. `('records', 'card', 'confirmation', 'host terminal')`, `'(docs/site/concepts.md#drafts-and-cards)'`
    7. `('unmeasured', 'ci is the gate', 'live source')`, `'(docs/site/concepts.md#unmeasured)'`
    8. `('ziran', 'signed', 'posture', 'deploy', 'approve', 'admin')`, `'(docs/site/security.md)'`
    9. `('stdlib', 'delet')`, `'(https://github.com/taoq-ai/wuwei/blob/main/.specify/memory/constitution.md)'`
  - Each item is at most 110 words once link targets are blanked
    (`re.sub(r'\]\([^)]*\)', ']', item)`).
  - Item 5 links `https://github.com/taoq-ai/wuwei/issues/<n>` for each n in 556 to 560.
  - Kept from the old test: `for word in ('professional', 'enterprise', 'best-in-class'):
    assert word not in readme.lower()` and `'\N{EM DASH}' not in section`.
- New `test_readme_landing_marks_follow_main` (next to it), the landing rule:
  ```python
  shipped = lambda n: any(ROOT.glob(f'specs/{n}-*'))
  sentences = [s for line in readme.splitlines() for s in re.split(r'(?<=[.!?])\s+', line)]
  landing = {int(n) for s in sentences if re.search(r'\blanding\b', s, re.I)
             for n in re.findall(r'taoq-ai/wuwei/issues/(\d+)', s)}
  assert landing and not any(shipped(n) for n in landing), landing
  principle = <item 5 of the Principles section>
  for n in range(556, 561):
      assert f'taoq-ai/wuwei/issues/{n})' in principle, n
      assert (n in landing) != shipped(n), n
  ```
  A sentence that says "landing" without an issue link fails too: assert every such sentence
  has at least one issue link.
- `test_readme_tells_the_day_in_superpowers_shape` (line 179): in `new`, `'## Philosophy'`
  becomes `'## Principles'`; drop `'## How WUWEI compares'` from the order list; delete the
  philosophy block (lines 229 to 234), now covered by the new test. Keep the 300-line cap.
- `test_docs_index_mirrors_the_readme_sections` (line 256): `('Philosophy', 'security')`
  becomes `('Principles', 'security')`.
- `test_readme_first_day_and_shipped_areas` (line 766): `'## How WUWEI compares'` becomes
  `'## Principles'`; add `'docs/site/agent.md'` to the ships link tuple (the path line).
- `test_notice_credits_match_readme_acknowledgements` (line 1067): add `'OpenSpec'`, `'CISR'`,
  `'vGOAL'`, `'error budget'` and `'Brier'` to the name tuple. Its URL check already makes
  every new NOTICE source appear in the Acknowledgements.

### 2. `README.md` (green)

- Lines 22 and 24, "What WUWEI is and is not", recommended text:
  - "WUWEI is a Claude Code plugin. It runs a chartered team of agents across your
    repositories, keeps workspace memory under `.wuwei/`, and works through `gh` for the code
    host, with tracker and chat as optional adapters."
  - "WUWEI is not a hosted service, a tracker, a chat system, or a replacement for your
    repository rules."
- "What ships today": add, before the cruise line, "- The path: `bin/wuwei next` returns the
  exact next action for each step of the day, and the session walks it
  ([what the session knows](docs/site/agent.md))." Append to the cruise line: "A new target
  asks you once, and a class whose stated confidence keeps missing runs at most L1." (plain
  words; "novel" is linked first in Principles). After the bullets, one blank line and:
  "Landing next: merge grants per repository ([#524](https://github.com/taoq-ai/wuwei/issues/524)),
  process depth per tier ([#567](...)), one register of people, channels and tools
  ([#552](...)), a day pace ([#579](...)), measured undo ([#557](...)), shadow-before-live
  raises ([#560](...)) and [#586](...)." One sentence, one line.
- Replace lines 106 to 112 (`## Philosophy` and its bullets) with `## Principles` and nine
  numbered items, one line each. Recommended text (tighten freely, keep the pinned phrases,
  the links and every sentence under 35 words):
  1. The CLI owns the path and the model walks it. `bin/wuwei next` returns the one next action: the exact command or Agent call, why, and what comes after. Skills and charters hold judgement, never a step list ([what the session knows](docs/site/agent.md), [design spec](docs/specs/2026-09-24-wuwei-design.md) 5.2 and 5.3).
  2. Autonomous by default, with floors. Under observe and guarded a guard gives you a warning or a card, and the work goes on. The one floor is records: the workflow writes them and you answer. Under strict, refusals stay ([security posture](docs/site/security.md#security-posture), design spec 9.2).
  3. Rules hold at the moment of action. A rule written only as a prompt can be skipped, so hooks check each call against the invariant table in design spec 9.2, and a test walks every case of it. Your code host's protected branches and required checks still carry the guarantee ([guards](docs/site/concepts.md#guards)).
  4. Who decides follows from the decision. Each record gets an MIT CISR class from how reversible it is, how far it reaches and how unclear it is. A Routine two-way decision is taken under the [mandate](docs/site/concepts.md#mandate); a Strategic or one-way one comes to you on a card ([decision classes](docs/site/concepts.md#decision-classes-and-cruise-levels), design spec 5.8).
  5. Autonomy is earned from the ledger, never by copying you. Each decision class runs at a level up to its ceiling; your agreements raise it and your reversals lower it ([cruise answers](docs/site/daily.md#cruise-answers), design spec 5.8.1). A [novel](docs/site/concepts.md#novel) target asks you once on a card (concepts.md, Novel) ([#556](https://github.com/taoq-ai/wuwei/issues/556)). A record counts as two-way only once its undo was rehearsed, landing in [#557](https://github.com/taoq-ai/wuwei/issues/557). Reversals spend an error budget, so one bad call does not drop a class ([#558](https://github.com/taoq-ai/wuwei/issues/558)). Stated confidence is scored against outcomes with a Brier score ([#559](https://github.com/taoq-ai/wuwei/issues/559)). A raise runs in shadow before it goes live, landing in [#560](https://github.com/taoq-ai/wuwei/issues/560).
  6. The workflow writes its records and you answer cards. Outside strict, your answer on a card is the confirmation; no step asks you for a hash or a command in a host terminal ([drafts and cards](docs/site/concepts.md#drafts-and-cards), design spec 5.2).
  7. Evidence over claims. [Unmeasured](docs/site/concepts.md#unmeasured) is never a pass, CI is the gate, and every count comes from its live source ([concepts](docs/site/concepts.md)).
  8. Security first, with least privilege. ZIRAN audits each role's tool grants in CI, releases are signed, and you choose the posture per area. WUWEI never deploys, never approves a pull request and never merges past branch protection as admin ([security](docs/site/security.md), design spec 1 and 7).
  9. Keep it simple. The runtime is Python stdlib only, nothing is built for a need that has not come, and deleting code beats adding it ([constitution](https://github.com/taoq-ai/wuwei/blob/main/.specify/memory/constitution.md)).
- Delete lines 186 to 213: `## How WUWEI compares`, its intro, table and paragraph, and
  `### How they compose`.
- Acknowledgements: add, in the form of the existing lines (one line each to stay within the
  300-line cap):
  - `[OpenSpec](https://github.com/Fission-AI/OpenSpec)`: the `openspec` spec engine option (MIT, run as an external tool).
  - `[MIT CISR decision framework](https://cisr.mit.edu/)`: Sebastian, Weill, Haskamp and vom Brocke, "A framework for determining when AI can make decisions"; the decision classes.
  - `[Verifiably Safe Autonomous Decision-Making (vGOAL)](https://www.kuleuven.be/)`: KU Leuven; the invariant table and its exhaustive test, without the model checker.
  - `[Error budgets](https://sre.google/sre-book/embracing-risk/)`: Google, Site Reliability Engineering, "Embracing Risk"; the error budget per decision class.
  - `[Brier score](https://doi.org/10.1175/1520-0493%281950%29078%3C0001%3AVOFEIT%3E2.0.CO%3B2)`: Glenn W. Brier, Monthly Weather Review, 1950; confidence calibration.
- Unchanged: hero and caption, the lead, How it works, the Mermaid block, When something goes
  wrong, What is inside, Installation, Quick start, Limits, Development installs, Development.

### 3. `NOTICE`

- superpowers entry: "philosophy" becomes "principles".
- After the ZIRAN entry, an OpenSpec entry (Source, Licence: MIT, Used: as an external tool,
  the openspec spec engine option, design spec 5.10; no code copied).
- Under "Concepts (credited by author and source)", four entries in the WSJF form (Source,
  Author, Used) for the MIT CISR framework (design spec 5.8), vGOAL (design spec 9.2), error
  budgets (design spec 5.8.1) and the Brier score (design spec 5.8.1), with the same URLs as
  the README lines.

## What must not change

- No file under `cli/`, `adapters/`, `hooks/`, `skills/`, `charters/`, `docs/site/` or
  `docs/specs/`. The docs index needs no edit (no Philosophy or comparison text there).
- The assertions that pin the hero, its caption, the Mermaid block, the lead phrases, the
  commands, Quick start, Limits and the Installation subsections keep their strength.
- `tests/test_tone.py` budgets are not raised.

## Risks

- Glossary first use: the first `mandate`, `novel` and `unmeasured` in the README must be
  linked (`test_glossary_words_link_at_first_use`); avoid other unlinked glossary words
  (nudge, page, park, lens, strict mode, ticket) in the new text.
- `test_readme_tells_the_day_in_superpowers_shape` checks every `wuwei <command>` in backticks
  in the new sections against the CLI groups; only `wuwei next` is used.
- `test_release_asset_ships_every_linked_doc` resolves relative README links in the release;
  the constitution is linked by its GitHub URL because `.specify/` is not shipped.
