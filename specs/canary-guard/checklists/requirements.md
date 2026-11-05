# Requirements checklist: canary-guard

- [x] Every acceptance scenario of the item maps to a test
- [x] Every canary read in hook.py goes through one reader
- [x] The reader returns '' for a missing, non-regular, unreadable or non-UTF-8 file, and never blocks on a FIFO
- [x] Write, Edit, MultiEdit, NotebookEdit and Bash writes to .wuwei/canary meet the ledger door in its words
- [x] Each path class (//, %xx, /./, /../) and wrapper (cd, env -C, sudo -D) probed
- [x] Reading the canary still passes
- [x] Route corpus read at main and head, sha256 recorded, only new canary rows move
- [x] No config key, ledger kind or file format added
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
