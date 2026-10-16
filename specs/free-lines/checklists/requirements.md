# Requirements checklist: free-lines

- [x] Every acceptance scenario of item free-lines maps to a test
- [x] No runtime caller of integrity before the move (git grep)
- [x] Manifest format, signing namespace and key path unchanged
- [x] Script command line and exit codes unchanged; the workflow file untouched
- [x] cli/wuwei/integrity.py and its vendored copy deleted; drift test passes
- [x] Signing tests skip without ssh-keygen and run in CI
- [x] Runtime at 2,939 lines
- [x] No config key added
- [x] No emojis, no em dashes
