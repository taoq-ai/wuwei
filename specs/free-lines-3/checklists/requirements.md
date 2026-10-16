# Requirements checklist: free-lines-3

- [x] Every acceptance scenario of item free-lines-3 maps to a test
- [x] verdict.CONFIDENCE had no reader before removal (grep)
- [x] hook._confidence had one caller before inlining (grep)
- [x] ws.PLUGIN names the same root as the four old definitions, in the tree and in the vendored copy
- [x] guards._git keeps the 5 s timeout and answers '' on OSError or SubprocessError
- [x] wuwei --version and --help match main; the PR standard note matches the charter with the version
- [x] Every route in tests/fixtures/routes.json reads as recorded
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime at 2,986 lines
- [x] No CLI flag, output, config key or guard route changed
- [x] No emojis, no em dashes
