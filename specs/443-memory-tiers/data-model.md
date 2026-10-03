# Data model: Memory tiers over time

All paths are under the workspace's `.wuwei/`. Every file here has one producer and is
protected by the records guard.

## Archived day

`archive/<year>/<date>.tar.gz`, gzip tar written by `consolidation.archive_days` only.

- Members: the directory `<date>` and every regular file of `days/<date>/` as
  `<date>/<relative path>`. No symlink, hard link, device or absolute member; no `..`.
- Verified after writing: the member file names equal the source file names, then the source
  directory is removed.
- Read only through `consolidation.day_records(root, day)` (see plan.md).

## Week and month digests

`memory/digests/<iso year>-W<iso week, 2 digits>.md` and `memory/digests/<year>-<month, 2
digits>.md`, written only by `digest.write`. Rebuilt from day records, never edited in
place. Example (week):

```text
# Week 2026-W40 (2026-09-28 to 2026-10-04)

## Decisions
- 2026-09-30 D-1: Retry the import with backoff? Outcome: backoff
- 2026-10-01 D-2: decided carry

## Lessons
- 2026-09-30 landed: builder.md patch: Run the fast checks before the gate.
- 2026-10-01 rejected: planner.md add

## Metrics
- 2026-09-30 Escaped defects: 0; baseline: 0
- 2026-10-01 unmeasured

## Incidents
- 2026-10-01 mcp.finding: 1

## Items
- 2026-09-30 closed: ITEM-1, ITEM-2; carried: ITEM-3; parked: none
```

Line rules:

| Section | Source in the day records | Structured fields | Free text (linted) |
| --- | --- | --- | --- |
| Decisions | `decisions/D-*.md`, `Outcome:` not `pending` | date, id, outcome label | the `Question:` line |
| Lessons | `memory/ledger.jsonl` rows with that `date` | date, status, target file name, action | `reason` |
| Metrics | `report.md` lines under `## Outcome` or `## Changed` | the report's own lines | none |
| Incidents | `events.jsonl`, `signal.classify(event, state)[0] == 'page'` | date, kind, count | none |
| Items | `state.json` `items` | date, names by phase: `merged` closed, `parked` parked, others carried | none |

A free-text line is kept when `outward.lint(line, 'digest', config, to_owner=True)[0] == 0`,
`'/' not in line` and `redact.known_values(line) == line`. Otherwise the fallback is the
structured fields only (`- 2026-10-01 D-2: decided carry`, `- 2026-10-01 rejected:
planner.md add`). An empty section is `none`. The month digest has the same shape with the
title `# Month 2026-09`.

## Forgetting proposals

`memory/forget.json`, written by `consolidate` (adds) and `memory forget` (status change),
through `workspace.atomic_write`. One JSON object keyed by id:

```json
{
  "F-1": {"id": "F-1", "kind": "unreferenced", "action": "archive",
          "target": ".wuwei/memory/notes/retry-policy.md",
          "evidence": "retry-policy: named by no brief, decision or retro since 2026-08-04 (60 days)",
          "status": "pending", "created": "2026-10-03"},
  "F-2": {"id": "F-2", "kind": "duplicate", "action": "fold",
          "target": ".wuwei/memory/notes/b.md", "survivor": ".wuwei/memory/notes/a.md",
          "evidence": "a, b: near-duplicate notes (0.91); a has 4 loads, b 0",
          "status": "pending", "created": "2026-10-03"},
  "F-3": {"id": "F-3", "kind": "superseded", "action": "drop",
          "target": ".wuwei/charters/builder.md", "old_text": "- Record the final result after review.\n",
          "evidence": "builder.md line 4 is superseded by line 9 (0.93)",
          "status": "declined", "created": "2026-10-03"},
  "F-4": {"id": "F-4", "kind": "contradicted", "action": "drop",
          "target": ".wuwei/charters/planner.md", "old_text": "- Do not carry parked items.\n",
          "evidence": "D-2 on 2026-10-01 chose carry: Carry parked items to tomorrow",
          "status": "applied", "created": "2026-10-03"}
}
```

- `kind`: `unreferenced` (action `archive`), `duplicate` (`fold`), `superseded` (`drop`),
  `contradicted` (`drop`).
- `status`: `pending`, `applied`, `declined`. Only `memory forget` moves it off `pending`.
- Ids grow: the next id is one more than the largest existing number.
- Dedup key: `(kind, target, old_text or survivor)`; an existing row with the key, in any
  status, blocks a new one.
- Landing maps `archive` and `fold` to `promotion._apply` actions of the same name and
  `drop` to `patch` with `text: ""`, with `reason` the evidence line and `evidence`
  `.wuwei/memory/forget.json`.

## Events

| Kind | Producer | Payload |
| --- | --- | --- |
| `memory.folded` | owner host `wuwei memory forget` | `{"id", "kind", "action", "target", "archive"}` (archive: the `memory/archive/` path holding the before text) |
| `memory.consolidated` | `wuwei consolidate` | `{"archived": <int>, "pending": <int>}` |

## Dropped rules archive

`memory/archive/dropped-rules.md`, appended only by `promotion._apply` on a charter drop:
`- <date> <charter file name>: <removed line without the leading "- ">`.

## Export block

In the file `memory.export_to` names (default `CLAUDE.md`, relative to the workspace root):

```text
<!-- wuwei:memory:start -->
## WUWEI rules

Generated by wuwei memory export from the workspace charters and the latest week digest.
Change them through wuwei promote; edits here are overwritten.

### builder
- Run the fast checks before the gate.

### Lessons, 2026-W40
- 2026-09-30 landed: builder.md patch: Run the fast checks before the gate.
<!-- wuwei:memory:end -->
```

A charter with no `- ` lines and an empty Lessons section are left out. With no rules and no
lessons the block holds the two header lines only. Text outside the markers is kept byte for
byte; with no markers the block is appended after one blank line.
