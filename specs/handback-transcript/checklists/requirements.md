# Requirements checklist: handback-transcript

- [x] Acceptance 1 (a forged PreToolUse hand-back naming a PASS verdict) maps to a test, red at b9522fc7 and green at the head; evidence still lists the gate
- [x] Acceptance 2 (the real recorded sentinel flow) maps to a test from payload, session and agent transcript fixtures built from a real session; it attests once, as at main
- [x] A replayed real stop with a forged report attests nothing and records seat.unconfirmed
- [x] A seat transcript that is a link out of the projects folder is not read, at the hand-back and at the stop
- [x] An empty, cut, non-object, blank-line or repeated seat transcript attests no payload report and raises no hook error
- [x] A stop with no report text still takes the transcript's last report (as at main)
- [x] The route corpus is read at main and the head with its sha256; each moved route is listed (none moved)
- [x] Each rule is held by a mutant a behavioural test kills, applied to both runtime copies one at a time
- [x] No new config key, ledger kind or file format
- [x] Runtime lines stated against the item's budget
- [x] Vendored copy matches
- [x] No emojis, no em dashes
