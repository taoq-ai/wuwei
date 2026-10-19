# Requirements checklist: verdict-dirfd

- [x] Every acceptance scenario of the item maps to a test and to a probe run
- [x] Each folder below the trusted root is opened with O_DIRECTORY and O_NOFOLLOW relative to its parent
- [x] The temporary file is unlinked, then created with O_CREAT, O_EXCL and O_NOFOLLOW at 0o666, relative to the last folder
- [x] The temporary name still carries the pid and threading.get_ident()
- [x] os.replace renames with src_dir_fd and dst_dir_fd
- [x] A RuntimeError from resolving is refused like an OSError and recorded as verdict.missing
- [x] free() lists its folder once and never raises
- [x] sync.py:82 walks from .wuwei
- [x] Callers that pass no root behave as before
- [x] No config key, ledger kind or file format added
- [x] Runtime under the 3,400 cap; the item's +10 budget overrun stated with its reason
- [x] .claude/ re-vendored
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
