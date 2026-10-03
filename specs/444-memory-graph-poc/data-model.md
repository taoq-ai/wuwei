# Data model: memory graph PoC

Everything below is generated or derived inside a temporary directory. Names are neutral:
repository `example/app`, modules `billing`, `export`, `search`, `auth`, `notify`,
`report`, people `dev-a` to `dev-e`, items `I-001`, tickets `TK-001`, lessons `L-01`,
incidents `INC-01`.

## Corpus

Shapes follow the records on `main`; the three entries marked **synthetic** do not exist
in today's records and the document must say so.

| Record | Path | Shape |
|---|---|---|
| Events | `.wuwei/days/<date>/events.jsonl` | one JSON object per line, `{"kind", "payload", "ts"}` as `state._append_event` writes it. Kinds used: `plan.approved` `{approved_items}`, `pr.raised` `{pr, item, head}` plus **synthetic** `files` (list of repo paths), `merge.auto` `{pr}`, `decision.decided` `{id, option, decided_by, item}`, `decision.reversed` `{id, option, decided_by, item}`, `retro.captured` `{agent_type, evidence}`, **synthetic** `pr.reverted` `{pr, reverts, item, by, reason}` |
| Decision | `.wuwei/days/<date>/decisions/D-<n>.md` | the 13 fields of `wuwei decision template` (`decision.FIELDS`), passing `decision.evaluate`. `Question:` starts with the item id (`Question: I-042: Raise the retry limit on export jobs from 3 to 5?`). A reversing decision's `Context:` contains `Reverses <date> D-<n>`. `Outcome:` is an option id. D numbering restarts each day |
| Brief | `.wuwei/days/<date>/briefs/<item>-builder.md` | header lines `Charter: charters/_common.md`, `Charter: charters/builder.md`, `Written: <ts>`, `Item: <item>`, `Seat policy: {...}`, a blank line, then `Scope: <module>` (module only, never a file path) and four to six lines of task text |
| Retro | `.wuwei/days/<date>/retro/<sha256>.json` | one line, `{"agent_id", "agent_type", "fields": {"Blocked", "Gap", "Change"}, "missing": [], "invalid": []}` as `guards/verdict.py` writes it |
| Proposal | `.wuwei/days/<date>/proposal.json` | `{"goals", "cap", "candidates": [{"id": <item>, "goal", "evidence": "TK-<n> <title>", "scope": <module>}]}` |
| Report | `.wuwei/days/<date>/report.md` | first line `<date>: <n> items closed, <m> carried`, then one line per item |
| Incident | `.wuwei/days/<date>/incidents/INC-<n>.md` | **synthetic**: `Title: <text>`, `Caused by: example/app#<n>`, `Item: <item>` |
| Charter override | `.wuwei/charters/<role>.md` | one rule per line, `- <rule text> (L-<n>)`; a rule may cite `INC-<n>` or `example/app#<n>` |
| Ledger | `.wuwei/memory/ledger.jsonl` | `{"target", "action": "add", "reason": "promoted from retro", "lesson": "L-<n>", "evidence": <retro path>, "date"}` per lesson (the `lesson` key is a PoC addition so the ledger links a lesson to its retro) |

Noise volumes per 90 days (scaled by `days / 90`, rounded, at least 1): 120 items, 300
decisions, 400 PRs (each touching one to three files of its item's module), 60 lessons, 20
incidents, 10 reverts, 200 tickets. Noise reuses the words of the planted phrases (module names,
"retry", "limit", "flaky", "revert") but never a whole planted phrase.

## Golden set

30 entries, six per type, each a dict:
`{"id": "Q01", "type", "text", "words": [...], "form": [...], "expected": [[path, line], ...], "answer"}`.
Paths are relative to the corpus root; lines are 1-based.

| Type | Planted fact | Form | Expected | Answer phrase |
|---|---|---|---|---|
| why | one decision whose Question carries a unique setting phrase ("retry limit on export jobs") | `["ask", words]` | the decision file, Question line | the setting phrase |
| touched | three PRs whose `pr.raised.files` include one file no noise PR touches | `["around", "file:<path>", ["touches"], 1]` | each `events.jsonl` line of those `pr.raised` | the file path |
| lesson | one charter rule naming a unique symptom ("flaky e2e login test") and the retro whose `Change` taught it | `["ask", words]` | the charter line and the retro file line | the symptom phrase |
| revert | a `pr.reverted` event and the incident it cites, sharing a unique reason ("duplicate invoice emails") | `["around", "pr:<reverted pr>", ["reverted", "caused"], 1]` | the event line and the incident Title line | the reason phrase |
| reversed | an item with a decision and a later decision whose Context says `Reverses <date> D-<n>` | `["around", "item:<item>", ["decided_in", "supersedes"], 1]` | the first decision's Question line and the second decision's Context line (where the phrase is) | `Reverses <date> D-<n>` |

A reverting PR appears only in its `pr.reverted` event (it is not raised separately), so
its node cites that event line. Planted facts are placed so every expected record exists
even at `days=6`.

The question words for the baseline are the same `words` the graph uses; for `around`
forms they are the node's key (the file path, the PR ref, the item id) plus one type word
("revert", "Reverses").

## Graph

```sql
CREATE TABLE meta(search TEXT);                 -- 'fts5' or 'like'
CREATE TABLE nodes(id TEXT PRIMARY KEY, type TEXT, title TEXT, path TEXT, line INTEGER, excerpt TEXT);
CREATE TABLE edges(src TEXT, dst TEXT, type TEXT, path TEXT, line INTEGER);
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED, text);   -- only when fts5
```

Node ids and their source (first sighting in sorted path order wins):

| Node | Id | From |
|---|---|---|
| item | `item:I-042` | proposal candidate (every item is a candidate on its start day) |
| decision | `decision:<date>/D-3` | decision file, Question line; title is the Question |
| pr | `pr:example/app#123` | `pr.raised` or `pr.reverted` event line |
| file | `file:billing/ledger.py` | `pr.raised.files` |
| lesson | `lesson:L-12` | charter override line |
| incident | `incident:INC-04` | incident file, Title line |
| ticket | `ticket:TK-123` | proposal candidate `evidence` |
| retro | `retro:<retro path>` | retro file; title is `fields.Change` |

Edges (each with the path and line it came from):

| Edge | From record |
|---|---|
| `decided_in` decision -> item | decision Question line |
| `supersedes` decision -> decision | `Reverses <date> D-<n>` in Context |
| `closed_by` item -> pr | `pr.raised` |
| `touches` pr -> file | `pr.raised.files` |
| `reverted` pr -> pr | `pr.reverted` (`pr` -> `reverts`) |
| `caused` pr -> incident | incident `Caused by:` |
| `learned_from` lesson -> incident or pr | an `INC-<n>` or PR ref in the charter line |
| `learned_from` lesson -> retro | ledger row (`lesson` -> `evidence`) |
| `mentions` ticket -> item | proposal candidate |

Excerpt: the source line, at most 200 characters. The `search` text (or the `LIKE`
target) is `title || ' ' || excerpt`.

## Export (simulated #443)

`export(root)` returns one text: every `- ` line of `.wuwei/charters/*.md`, then for the
last 7 day directories in date order: each decision's `Question:`, `Context:` and
`Outcome:` lines, each retro `fields.Change`, each incident `Title:` line. No paths, as
#443 requires of a digest.
