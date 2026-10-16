# Requirements checklist: door-hardening

- [x] Every acceptance scenario of item door-hardening maps to a test
- [x] guards.DOORS is the one table of edit tools and MCP door suffixes; pre_tool and hook.door read it
- [x] hook.py holds no copy of the MCP door suffixes
- [x] hook.door matches DOOR_WORDS with quotes and backslashes removed
- [x] hook.door counts network programs and every mcp__ tool; Read and Glob stay open
- [x] codex() runs inside handle's try; apply_patch is an edit door
- [x] _unwrap keeps main's rule; nine wrapper assignment shapes pinned as refused or asked
- [x] A failed hook-seen stamp never changes the guards' decision
- [x] SECURITY.md and docs/design.md say what a failing guard refuses
- [x] .claude/ re-vendored at the head
- [x] Route verdicts unchanged (route corpus from origin/claude/route-fixtures run over the head)
- [x] Runtime at 3,000 lines or fewer
- [x] No config key, no new door, no emojis, no em dashes
