# Requirements checklist: announcement-url

- [x] Every acceptance scenario maps to a requirement and a task
- [x] `breaking_gaps` lines re-found at b28a3dc (evidence.py 330 to 349)
- [x] Runtime 2,992 to 2,992 lines, within the item's budget of 2
- [x] `.claude/` re-vendored and the agents rebuilt
- [x] Tests ran red on main and green at the head
- [x] Near misses tested: a bare path, `see CHANGELOG`, a URL inside prose, a non-http scheme, whitespace
- [x] The #1135 break detection kept: its tests pass with only the gap text changed
- [x] Rollback line in the spec
- [x] Breaking declared with migration notes
- [x] No emojis, no em dashes
