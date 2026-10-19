# Requirements checklist: push-refspecs

- [x] Every acceptance scenario of item push-refspecs maps to a test or a recorded probe run
- [x] The four acceptance-1 commands move main under real git 2.43 on a scratch bare remote, and the door refuses each with the remote read as non-scratch
- [x] The four acceptance-3 commands leave main alone under real git and pass the door, from a clone on feature and (for `--tags`) on main
- [x] `--all` meets the door by rule in each position (before the remote, after it, last), not by option order
- [x] Forced globs (`+refs/heads/*:refs/heads/*`) meet the force refusal; quoted, double-quoted and backslashed globs are read as git reads them; `$'..'` is refused as unreadable
- [x] One normalisation input per path class (`//`, `%xx`, `/./`, `/../`) in a destination, and per working-directory wrapper (`cd`, `env -C`, `sudo -D`), is probed
- [x] The generated probe reports its three counts (generated, ran the door program, holes) and 0 holes at the head, with main's count beside it
- [x] The route corpus moves no existing row; its sha256 is recorded at main and the head; moved new rows are listed
- [x] Each rule is held by a test (a mutant without it fails)
- [x] Vendored copy matches; drift test passes
- [x] Runtime lines stated against the item's budget
- [x] No emojis, no em dashes
