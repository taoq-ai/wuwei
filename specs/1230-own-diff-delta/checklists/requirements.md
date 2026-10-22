# Requirements checklist: 1230-own-diff-delta

- [x] Each acceptance scenario of item 1230 maps to a test, red at fbf187b and green at the head
- [x] A conflict resolution that edits the PR's own lines is probed on a plain and a risky path
- [x] A base merge into a file the PR touches is probed on lines far from and next to its hunk, and above it (a new function heading)
- [x] An update-branch merge commit (`Merge branch 'main' into feature`) is probed under real git
- [x] A merge that reverts main's change, a merge that adds a PR-own file, and a fix after a merge are probed
- [x] A patch GitHub leaves out moves its file; an own diff at the 300-file cap falls back to head to head
- [x] A plain fix push with no base merge reads as on main (probe fix classes, route differential fix host)
- [x] The `Generated` line needs the repository and a date; backticked and comma-separated globs read
- [x] The route corpus is read at main and the head under three hosts, with its sha256; each moved route is listed
- [x] Each rule is held by a mutant a behavioural test kills, applied to both runtime copies
- [x] No new config key; no uncached host call on the board path
- [x] Runtime lines stated against the item's budget
- [x] Vendored copy matches; docs name the new measure and the standards line
- [x] No emojis, no em dashes
