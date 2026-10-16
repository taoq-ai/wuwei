# Requirements checklist: vendored-drift

- [x] Every acceptance scenario of item vendored-drift maps to a test
- [x] The drift test names each differing path and ignores __pycache__
- [x] vendor() itself unchanged; no symlink, no doctor check
- [x] release-please bumps .claude/wuwei/.claude-plugin/plugin.json with the root
- [x] .claude/ re-vendored at the head; the copy carries the root version (1.2.1)
- [x] No config key added
- [x] Runtime at 3,000 lines or fewer
- [x] ADR for the one-way 1.2.1 release decision in docs/adr/
- [x] No emojis, no em dashes
