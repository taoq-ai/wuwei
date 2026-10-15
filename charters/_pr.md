WUWEI PR standard. Start from this body (keep the repository's own template sections too):

## What and why
<what changed and why, in two or three sentences>

## Assumptions
<each two-way choice you took: what, why, what would overturn it; or none>

## Tests
<the tests that cover the change; or a line "No test: <reason>">

## Review notes
<residual non-blocking findings; or none>

---
<sub>[WUWEI](https://taoq-ai.github.io/wuwei/) · Item `<id>` · <item title> · Goal <G-n> · Tier <tier></sub>

End the body with that footer, filled from `wuwei plan show <id>`; it links the PR to its plan item.

The gates the diff needs passed on this branch before it opened. Request a reviewer. Before merge
CI is green, every review thread is answered, and a delta after review fixes is re-read when it needs it.
