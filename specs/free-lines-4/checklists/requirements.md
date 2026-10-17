# Requirements checklist: free-lines-4

- [x] Every acceptance scenario of item free-lines-4 maps to a test or a recorded probe
- [x] Runtime at 2,977 lines or fewer, with at least 22 freed
- [x] No rewritten line over 150 characters
- [x] The `tokens[2:] + ['']` sentinel stays with a comment naming why
- [x] OPS keeps `&&`, `||`, `|&` and `&>`; drops only `;;`
- [x] No existing test changed
- [x] .claude/ re-vendored at the head
- [x] DOOR_WORDS and LEDGER regexes untouched (outside the item)
- [x] No emojis, no em dashes
