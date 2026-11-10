# Plan: a seat's command naming the records passes only for a reader (records-writers)

## Approach

- `cli/wuwei/guards.py` (and the vendored copy): a `READERS` set, plus one clause in the records
  check of `bash`. When `seat` is set, the program is not in `READERS`, and a word names
  `LEDGER + OWNED` (`.wuwei` itself included), the guard denies with the existing records reason.
  The `OWNER_ONLY` reason lists the main readers. Runtime +2 lines.
- `READ`, `segments` and `_unwrap` stay unchanged, so a reader behind a wrapper is refused. Adding
  readers to `READ` would let `env -S '<writer>' cat` unwrap to `cat`.
- `SECURITY.md`: the known-open writer list becomes the reader rule and its limits.
- `tests/test_guards.py`: writer shapes x records refused for a seat, and passed for the owner on
  config and plan; readers x records pass for a seat.

## Constitution check

Stdlib only, no new module, runtime at 3,951 of 4,000 lines, test first.
