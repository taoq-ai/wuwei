# Research: Plain tone

## Before and after

Measured with `measure` from `cli/wuwei/commands/lint.py` over `classes()` in
`tests/test_tone.py`. The before column is the base before any existing text changed (T006).
Columns: average words per sentence, longest sentence, sentences over 35 words,
nominalisations per 100 words.

| Class | Before average | Before longest | Before over 35 | Before nominal rate | After average | After longest | After over 35 | After nominal rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reasons | 11.8 | 46 | 1 | 3.0 | 11.5 | 26 | 0 | 3.0 |
| cards | 8.4 | 28 | 0 | 3.1 | 8.2 | 23 | 0 | 3.1 |
| skills | 16.8 | 42 | 8 | 2.9 | 14.5 | 32 | 0 | 2.9 |
| charters | 14.3 | 66 | 9 | 4.3 | 13.6 | 35 | 0 | 4.3 |
| docs | 11.3 | 171 | 103 | 2.9 | 11.1 | 171 | 75 | 2.9 |

## The pages in the pass

| File | Before average | Before longest | Before over 35 | After average | After longest | After over 35 |
| --- | --- | --- | --- | --- | --- | --- |
| docs/site/concepts.md | 16.9 | 69 | 16 | 15.6 | 35 | 0 |
| docs/site/daily.md | 18.1 | 68 | 10 | 16.7 | 34 | 0 |
| README.md | 10.4 | 54 | 2 | 10.3 | 34 | 0 |

## The docs over budget

The docs class carries 103 sentences over 35 words on the base. The three pages in the pass
carry 28 of them, so the pages outside the pass (agent, configuration, index, reference,
rehearsal, remote, security) carry 75. That is the docs over-35 budget (A4). The
`bin/wuwei lint` row added to reference.md has no sentence over 35 words, and the agent.md
read-only line it lengthened was already over 35.

## The nominalisation budgets

Each budget is the after rate rounded up to one decimal: reasons 3.1, cards 3.1, skills 2.9,
charters 4.3, docs 3.0. The unrounded after rate is at or below the before rate in every
class (reasons 3.005 against 3.016, cards 3.056 unchanged, skills 2.893 against 2.912,
charters 4.279 against 4.306, docs 2.906 against 2.910). The pass split long sentences; it
did not hunt nominalisations, so the rates moved little.

The card class was already at the rule on the base (longest 28), so the pass changed only
the gate card: its Approve text is now short sentences, not one semicolon chain.
