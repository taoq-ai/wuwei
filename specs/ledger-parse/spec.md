# Spec: a ledger line that is not a well-formed row is skipped by every reader (ledger-parse)

## In my words

`ws._parse` keeps any JSON value today. `ws.record` then reads `mine[-1]['hash']`, so a last line
of `[1]`, `5`, `null` or `{"a": 1}` raises. In `hook.pre_tool` that raise comes right after a deny
is decided, `handle` fails open, and the refusal is lost. Readers also break on a row whose fields
have the wrong type: doctor stops on `{"kind": [1]}` because a list is not hashable.

After this change `_parse` keeps only well-formed rows: a JSON object whose `ts` and `kind`, where
present, are strings, and whose `data`, where present, is an object. `record` chains to the hash
of the last kept row that has one (GENESIS when none has), so a malformed last line never raises.
`ledger()`, `rows()`, `traces()` and doctor's hooks check read only kept rows. `verify()` is not
changed and still names every malformed line by file:line.

## Acceptance scenarios

1. This clone's ledger file ends in `[1]`, `5`, `null` or `{"a": 1}`: `ws.record` raises nothing,
   and the new row's `prev` is the hash of the last row that has one.
2. A ledger file holds `{"kind": [1]}`, `{"ts": 5, "kind": "x"}` and a row whose `data` is a list:
   `ws.ledger()`, `ws.rows()` and doctor finish and skip those lines.
3. The same file: `ws.verify()` still names each malformed line by file:line.
4. The runtime size test still passes at 3,000 lines or fewer.

## Requirements

- FR-1: `_parse` drops a line that is not JSON, not an object, or has a `ts` or `kind` that is not
  a string, or a `data` that is not an object.
- FR-2: `record` takes `prev` from the last kept row whose `hash` is a string, else GENESIS.
- FR-3: doctor's hooks scan drops its own `isinstance(row, dict)` filter and relies on `_parse`.
- FR-4: `traces()` reuses `_parse`, which frees the lines the change adds.
- FR-5: `verify()`, the ledger format, sync and the ledger door are unchanged.

## Assumptions

- "The last row that has one" means a kept row whose `hash` is a string; a row with a non-string
  hash is skipped for chaining. Overturned if the owner wants such a row to break the chain loudly.
- A field present with a `null` value counts as present and malformed, so the row is dropped.
  Overturned if some writer records `"data": null` (none does: every `ws.record` caller passes a dict).
- Trace rows (`ts`, `tool`, `target` and so on) carry no `kind` or `data`, and `ts` is always a
  string from `ws.trace`, so the stricter parse drops no trace that `ws.trace` writes. A
  hand-edited trace with a non-string `ts` is now skipped instead of crashing the day report.
- After a malformed line, the next record chains past it, so `verify()` reports only the malformed
  line itself, not the new row. That matches the promise: the bad line stays visible.
- Every `ws.record` caller passes a string kind and a dict, so every row record writes is kept. A
  forged row with a valid hash but a malformed field is dropped; the next record chains past it
  and verify() then flags that next row. Overturned if a writer can record such a row.
