# Requirements checklist: scratch-remotes

- [x] Every acceptance scenario of item scratch-remotes maps to a test or a recorded probe run
- [x] `git push ../r.git main` and `git push origin main` (origin a scratch path) pass the head guard, and real git then puts main in the bare remote
- [x] The working repository's `.git`, a symlink from scratch to it, and an origin on GitHub are each refused
- [x] A cd, env -C, sudo -D, pushd, subshell, env assignment or second command before the push keeps the door
- [x] A remote name's pushurl, every push URL and pushInsteadOf are read
- [x] One input per path class (`//`, `%xx`, `/./`, `/../`) and per working-directory wrapper (`cd`, `env -C`, `sudo -D`) is probed
- [x] The generated probe reports its three counts (generated, ran the door program, holes) and 0 holes at the head
- [x] The route corpus moves no row; its sha256 is recorded
- [x] Each check is held by a test (a mutant without it fails)
- [x] Vendored copy rewritten; drift test passes
- [x] Runtime over the item's budget is recorded under Assumptions with the numbers
- [x] No emojis, no em dashes
