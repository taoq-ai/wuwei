# Spike: a derived memory graph over the records

Issue #444, run on 2026-10-03. Owner: "transform as a PoC: we select some hypotheses and
then we make a conclusion."

## Question and scope

Should WUWEI keep a derived graph (an index, never the store) over its records so
planners, leads and retros can answer history questions? The harness already has memory,
so the graph has to earn its place. Throwaway code lives in `scripts/poc/memory-graph/`;
nothing under `cli/` changed.

## Method

- Corpus (`corpus.py`): a seeded `.wuwei/` of 90 days ending 2026-09-29 in the record
  shapes on main. Per 90 days: 120 items, 300 decisions, 400
  PRs, 60 lessons, 20 incidents, 10 reverts.
- Synthetic extensions today's records lack: PR files on `pr.raised`, a `pr.reverted`
  event and `incidents/INC-n.md`. Touched needs the first, revert the other two.
- Golden set: 30 questions, six each of why (a setting changed), touched (what touched a
  file), lesson (which lesson fits a symptom), revert (who reverted a PR and why) and
  reversed (which decisions on an item were reversed). Each has expected records and an
  answer phrase the generator proves occurs nowhere else. Questions came before any graph code.
- Baselines: case-insensitive `grep -rn` over `.wuwei/`, files ranked by hits, the top 5
  read in full; tokens are the first 100 grep lines plus those files. Word grep ORs every
  question word (the worst case). Key grep searches one specific key: the setting's first
  two words, the symptom, the PR ref, the path, the item id. H1 is judged against the
  stronger of the two.
- Graph (`graph.py`): stdlib `sqlite3`, FTS5 or a `LIKE` fallback. Nodes: item, decision,
  pr, file, lesson, retro, incident, ticket. Eight typed edges, each with source path and
  line. Queries `ask(words)` and `around(node, hops)`; no `path` query, since no question needs it.
- Tokens: `wuwei.memory.estimated_tokens`. The graph pays for its hits plus reading its
  top 5 records in full, like grep. The excerpts-only column is an optimistic bound no
  threshold uses.
- Answered: every expected record is in the top 5. No partial credit.
- Rule, fixed before measuring: drop if H1 is unsupported; park if H3 is unsupported or H4
  is supported; build otherwise. H2 only decides whether briefs join a build.
- Rerun: `python3 scripts/poc/memory-graph/run.py` (`--no-fts` for the fallback). Wall times are one machine's.

## Results

Printed by the runner, pasted unedited. The run took under 10 seconds.

Search: fts5 (Python 3.12.13, SQLite 3.53.1), corpus 90 days, 30 questions

### H1 answers

| Type | Questions | Word grep answered % | Key grep answered % | Graph answered % | Word grep tokens | Key grep tokens | Graph tokens | Graph excerpts-only tokens | Word grep ms | Key grep ms | Graph ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| why | 6 | 0 | 100 | 100 | 6441 | 171 | 871 | 190 | 81.0 | 65.3 | 0.3 |
| touched | 6 | 100 | 100 | 100 | 1877 | 1877 | 1899 | 180 | 72.6 | 65.9 | 0.2 |
| lesson | 6 | 17 | 100 | 100 | 5818 | 954 | 1368 | 240 | 66.0 | 66.1 | 0.3 |
| revert | 6 | 0 | 100 | 100 | 5798 | 837 | 789 | 114 | 59.7 | 74.5 | 0.2 |
| reversed | 6 | 0 | 0 | 100 | 2725 | 2502 | 638 | 130 | 65.0 | 63.2 | 0.2 |
| total | 30 | 23 | 80 | 100 | 4532 | 1268 | 1113 | 171 | 68.9 | 67.0 | 0.2 |

Verdict H1: unsupported (against the stronger grep: answer rate up 25 points or tokens down by half)

### H2 briefs

| Item | Brief tokens | With subgraph tokens | Ratio | Prior decisions | Visible without | Visible with | Asks | Re-decisions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I-017 | 99 | 148 | 1.49 | 4 | 0 | 2 | unmeasured | unmeasured |
| I-037 | 80 | 129 | 1.61 | 4 | 0 | 2 | unmeasured | unmeasured |
| I-057 | 81 | 129 | 1.59 | 3 | 0 | 2 | unmeasured | unmeasured |
| I-077 | 91 | 140 | 1.54 | 4 | 0 | 2 | unmeasured | unmeasured |
| I-097 | 80 | 131 | 1.64 | 3 | 0 | 2 | unmeasured | unmeasured |
| I-117 | 88 | 138 | 1.57 | 3 | 0 | 2 | unmeasured | unmeasured |
| I-001 | 88 | 136 | 1.55 | 3 | 0 | 2 | unmeasured | unmeasured |
| I-002 | 79 | 127 | 1.61 | 5 | 0 | 2 | unmeasured | unmeasured |
| I-003 | 77 | 118 | 1.53 | 1 | 0 | 1 | unmeasured | unmeasured |
| I-005 | 100 | 148 | 1.48 | 5 | 0 | 2 | unmeasured | unmeasured |

Brief length within 20 percent for every item: no.

Verdict H2: unmeasured (asks and re-decisions need a live seat; counted unsupported)

### H3 cost

| Days | Build s | Largest events.jsonl bytes | Index bytes | Nodes | Edges | Rebuild identical |
| --- | --- | --- | --- | --- | --- | --- |
| 360 | 0.45 | 6130 | 3358720 | 4347 | 7175 | yes |

Verdict H3: supported (build at most 10 s, events.jsonl at most 20 MB, index under 50 MB, identical rebuild)

### H4 overlap

Export size: 2297 tokens.

| Type | Questions | Answered by export | Fraction |
| --- | --- | --- | --- |
| why | 6 | 0 | 0.00 |
| touched | 6 | 0 | 0.00 |
| lesson | 6 | 6 | 1.00 |
| revert | 6 | 1 | 0.17 |
| reversed | 6 | 1 | 0.17 |
| total | 30 | 8 | 0.27 |

Verdict H4: unsupported (supported when the export answers more than half)

Conclusion: drop

With `--no-fts` every answer rate and verdict is the same; graph tokens rise to 1160 per
question and graph time to 0.8 ms; the year index is 1.9 MB and builds in 0.61 s.

## Reading the numbers

- H1: against word grep the graph looks strong (100 against 23 percent, a quarter of the
  tokens), but that grep ORs common words ("retry", "export", "revert") and ranks busy
  `events.jsonl` files first. Key grep, one specific key per question, answers every why,
  touched, lesson and revert question at about the graph's cost or less (why 171 against
  871 tokens, lesson 954 against 1368, revert 837 against 789, touched equal). The graph's
  only lead is the reversed type, which `wuwei why <item>` already covers. Against the
  stronger grep the gain is 20 points and 12 percent of tokens, short of both thresholds.
- H2: asks and re-decisions need about 20 paid live seat runs. Offline, the subgraph made
  briefs 48 to 64 percent longer and showed one or two prior decisions the brief lacked.
- H4: the export answers every lesson question (promoted rules are in it by design) and
  almost nothing older than a week.

## Threats to validity

- Synthetic corpus and golden set, written by the graph's author. Answer phrases are
  unique by construction, so 100 percent is an upper bound.
- Key grep is given the right key. A planner who does not know the exact phrase or ref
  would do worse; real records that repeat phrases would hurt key grep and the graph alike.
- `wuwei why <item>` (`cli/wuwei/commands/why.py`) already covers the reversed type,
  including `decision.reversed`. It was not measured.
- Touched and revert rest on record fields that do not exist yet.
- The #443 export is simulated. Peak memory is unmeasured.

## Conclusion

The pre-registered rule gives drop: H1 is unsupported against the stronger grep, so H3
and H4 do not matter. Key grep answers 24 of 30 at about the graph's cost; the 6 it misses
are the reversed type `wuwei why` answers. The graph only beats a careless grep.

Issue #444 closes with this document linked. Revisit trigger: remeasure on real records
(a 30-day workspace) against key grep and `wuwei why`; reopen if the graph clears the rule.

## Decision record

Question: Build the derived memory graph from #444?
Context: H1 unsupported against key grep (100 against 80 percent, 1113 against 1268 tokens; the gap is the reversed type wuwei why covers), H3 supported, H4 unsupported (8 of 30), H2 unmeasured. Synthetic corpus.
Options:
| Option | Description |
| --- | --- |
| A | Build the reduced scope: ask, around for PRs, and the PR files, revert and incident records |
| B | Defer: park until a team workspace or real records show the need |
| C | Do nothing: drop the graph and rely on grep, wuwei why and the export |
Musts:
| Criterion | A | B | C |
| --- | --- | --- | --- |
| Records stay the store | pass | pass | pass |
| Off the hook path | pass | pass | pass |
Wants:
| Criterion | Weight | A | B | C |
| --- | --- | --- | --- | --- |
| Answers what grep misses (H1) | 8 | 3 | 2 | 2 |
| Fits the consolidate budget (H3) | 5 | 8 | 10 | 10 |
| Not covered by the export (H4) | 5 | 6 | 4 | 3 |
| Low build and upkeep cost | 4 | 3 | 7 | 10 |
Recommendation: C
Confidence: medium
Reversibility: two-way
Blast radius: None; no code under cli changes and the records stay as they are.
Pre-mortem: Real records are noisier than the synthetic corpus, so key grep misses answers the graph would find and the drop costs planner time.
Revisit: Remeasure on real records: rerun the golden types on a real 30-day workspace against key grep and wuwei why; reopen if the graph clears the H1 rule there.
Decided-by: owner
Outcome: pending
