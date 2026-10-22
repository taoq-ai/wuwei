# Requirements checklist: gates-at-push

- [x] Each acceptance scenario of item 1221 maps to a test; the new behaviours run red at 470ab63 and green at the head
- [x] The builder charter hands back without a CI read and reports CI as unread
- [x] The planner launches gates at push, while CI runs; green CI still holds ready and merge
- [x] A red check after the gates pass goes back to the builder, and its fix is a new head under the delta rule
- [x] The board's owed-gates duty shows while CI runs, has not started or misses a required check; a red head owes none
- [x] The ready door refuses the flip and a reviewer request on a draft while a check fails, naming the checks
- [x] Running CI does not hold the ready door; green CI passes it
- [x] An owner exception for the printed `CI failing` gap opens the ready door at that PR and head only
- [x] A verdict attested while CI ran counts once CI is green at its head; no hook refuses it
- [x] The route corpus is read at main and the head with its sha256; each moved route is listed
- [x] Each runtime rule is held by a mutant a behavioural test kills, applied to both runtime copies
- [x] Runtime lines stated against the item's budget
- [x] Vendored copy matches; agents rebuilt; every agent under its word ceiling
- [x] No emojis, no em dashes
