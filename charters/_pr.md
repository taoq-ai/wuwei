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
<sub>[WUWEI <version>](https://taoq-ai.github.io/wuwei/) · Item `<id>` · <item title> · Goal <G-n> · Tier <tier></sub>

End the body with that footer, filled from `wuwei plan show <id>`; it links the PR to its plan item.

The PR opens as a draft, and the gates the diff needs read the draft head while CI runs. It turns
ready once they pass and CI is green, and the shepherd requests the reviewer then. Before merge, CI
is green and every review thread is answered. A check red after the gates pass goes back to the
builder. A delta after review or CI fixes is re-read when it needs it.
