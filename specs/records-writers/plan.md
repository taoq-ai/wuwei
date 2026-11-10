# Plan: a seat's command naming the records passes only for a reader (records-writers)

## Approach

- `cli/wuwei/guards.py` (and the vendored copy): a `READERS` set, plus a seat-only rule in `bash`
  with its own reason, `READER_ONLY`. The rule covers a program off the list whose words name
  `LEDGER + OWNED` (`.wuwei` itself included).
- Fix round 1: the rule also joins each word, and the value after an `=`, to every directory that
  a `cd` or `pushd` (or a `-C`/`-D` value) may have reached. A record dir there, a joined word
  naming a record, or more than 64 such dirs needs a reader. So a seat can still read files under
  `.wuwei/verdicts` after `cd`, but cannot reach `../config.toml`.
- Fix round 1: `_unwrap` returns the words before a wrapper's cut as their own segment (`env perl
  -pi ... .wuwei/config.toml git` reads as `env perl ...` and `git`). No other door matches a
  wrapper's name, so only the seat rule sees the new segment. The readers stay out of `READ`, so a
  reader behind a wrapper is still refused (`sudo -u cat git push` would otherwise hide a push).
- `find`, `rg` and `du` are readers. `-ok`, `-okdir` and `-fprint0` join `FIND`, and `rg --pre`
  is a writer. These changes also close an owner-session ledger hole.
- `SECURITY.md`, `docs/design.md` section 7 and `docs/site/concepts/doors.md` describe the rule
  and the reads it refuses.

## Constitution check

Stdlib only, no new module, runtime at 3,959 of 4,000 lines, test first.
