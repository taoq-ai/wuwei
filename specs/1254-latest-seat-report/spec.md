# One latest seat report

Promise: when handback is unavailable, a seat ends with a plain-text report. The planner receives
only its latest undelivered final report, once, isolated by session and agent.

## Acceptance scenarios

1. A refused handback followed by a final message delivers that report once, without a retry.
2. Three retained versions produce only the latest report. Earlier bodies cannot displace it.
3. A matching real notification or previous delivery prevents another delivery of that final.
4. Similar text from separate agents or sessions never suppresses either report.
5. A cancelled notification or the real error saying no report was delivered gives no delivery credit.
6. Superseded files remain available for audit beside the retained report path.
7. An overlapping delivery or temporary failure to archive an old version never makes it current.
8. Moving the latest file between pending and archive cannot hide its supersession watermark.
9. A concurrent claim during retention listing or reading never loses the returning final in A/B/A.
10. Only a readable, nonblank UTF-8 regular file with the writer's session/agent/role/version name
    establishes a latest-version marker. Invalid pending, archived, and moved copies suppress nothing.

## Assumptions

The existing timestamped filenames order versions within a seat. They are generated from time_ns;
a native producer that supplies a different ordering would overturn this choice.
Repeated identical latest reports are one final report. A changed latest report supersedes earlier
pending versions, even when its text matches an older version. This prevents historical body deduplication
from losing the final report.

## Scope

Reuse report retention and delivery in hook.py. Preserve launch verification, notification frame
matching, cancellation handling, guard decisions, and the existing outside-auto guidance.

## Success criteria

Each session and agent contributes at most one report body per delivery. Subsequent calls and Stop
remain quiet until that seat produces another final report. All accepted report versions remain available for audit.

Rollback: revert this change.

## Approved selection reconsideration

The owner approved revised report selection after the first delta found filename-only archive
watermarks could hide authentic finals. Validate filename, file type, UTF-8 readability, and nonblank
content before selecting a version in retention or delivery. Validate a moved archive copy by the
same rule. Keep pending-first enumeration and claim fallback. Existing positive integer version
filenames remain supported. This is filesystem robustness, not a new authenticity protocol.
