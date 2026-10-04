# Data model: decision record and lens config

## Decision record (new shape, design class)

Same file, same fields as today, plus `Class:` (now required for a new record), the Options
table's three columns, `Reasoning:` and `Lenses:`. Neutral example; this is also what
`decision template` prints with the default lenses.

```
Question: Which cache should the report use?
Class: design
Context: tests/test_report.py shows the slow path.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | In-process cache | Passes every must and scores 8 on Speed because reads repeat within one run. Costs little on Simplicity. | Reports get faster today; a restart empties the cache; closes nothing. |
| B | Defer | Passes every must but scores 2 on Speed. | Nothing changes; the slow path stays. |
<!-- Lenses: one line per option for each. SOLID: Which SOLID principle does it keep or break? ... -->
Lenses:
| Lens | A | B |
| --- | --- | --- |
| SOLID | Keeps single responsibility: the cache sits behind the existing reader. | No change. |
| twelve-factor | No new config or backing service. | No change. |
| YAGNI | Builds only the cache the slow report needs. | Builds nothing. |
| ponytail | Stdlib functools.lru_cache; no dependency. | Simplest: nothing. |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Speed | 10 | 8 | 2 |
Recommendation: A
Reasoning: Speed decided it; a report that must survive restarts would flip it to B.
Confidence: medium
Reversibility: two-way
Blast radius: own branch
Pre-mortem: The cache serves stale data.
Revisit: Reopen if a report shows stale data.
Decided-by: seat
Outcome: pending
```

Field rules (new record; FR-002):

| Field | Rule | Refusal names |
|---|---|---|
| `Class:` | one line, one of `decision.CLASSES` | `Class` |
| Options | columns exactly `Option, Title, Rationale, Consequence`; no empty cell | `Options` |
| Title | unique (case-insensitive), at most 40 characters, no `"`, backtick, `$`, backslash; the Do nothing or Defer option's title starts with `Do nothing` or `Defer` | `Options` and the title |
| `Reasoning:` | present, one line | `Reasoning` |
| `Lenses:` | only for an engineering class with at least one configured lens: columns `Lens, <option ids>`; rows exactly the configured lens names; no empty cell | `Lenses` and the lens name |

A record before this change (`| Option | Description |`, no `Class:`, no `Reasoning:`)
still passes `evaluate(text)`; only `evaluate(text, lenses)` (the new-record check) refuses
it.

Engineering classes: `design`, `boundary`, `refactor`, `dependency-bump`.

New 5.8.1 rows (default, ceiling): `design` (L0, L3) an architecture, interface or data-shape
choice that outlives the item; `boundary` (L0, L3) moving or changing a module, service or
ownership boundary; `refactor` (L0, L3) restructuring code without changing behaviour.

## Lens config

```toml
[decisions.lenses]
company-rule = "Does it follow our data retention rule?"   # adds a lens
YAGNI = ""                                                 # drops a default lens
```

Schema: `"lenses": {"*": (str, "")}` under `decisions`. Effective set:
`{**decision.LENSES, **config['decisions']['lenses']}` minus empty values, in that order
(defaults first, then added names). Defaults (`decision.LENSES`):

| Name | Question |
|---|---|
| `SOLID` | Which SOLID principle does it keep or break? |
| `twelve-factor` | Where relevant, how does it treat config, backing services, processes and dev-prod parity? |
| `YAGNI` | What does it build that no item needs yet? |
| `ponytail` | Is there a simpler thing that works: stdlib before custom, native before a dependency? |

Config check: each name matches `[A-Za-z][A-Za-z0-9_-]*`, else `decisions.lenses.<name>:
...` refusal.

## Widget (AskUserQuestion) from the example, `brief`

```json
{"question": "D-1: Which cache should the report use? Speed decided it; a report that must survive restarts would flip it to B.",
 "header": "D-1", "multiSelect": false,
 "options": [
   {"label": "In-process cache (Recommended)",
    "description": "Passes every must and scores 8 on Speed because reads repeat within one run.\nReports get faster today; a restart empties the cache; closes nothing.\nSOLID: Keeps single responsibility: the cache sits behind the existing reader.\ntwelve-factor: No new config or backing service.\nYAGNI: Builds only the cache the slow report needs.\nponytail: Stdlib functools.lru_cache; no dependency."},
   {"label": "Defer", "description": "..."}],
 "record": "wuwei decide D-1 \"<label>\""}
```

At `standard` and `full` the rationale keeps its second sentence.
