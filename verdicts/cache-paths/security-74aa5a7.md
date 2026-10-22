Verdict: PASS
Gate: security
Item: cache-paths
PR: taoq-ai/wuwei#1242
Head: 74aa5a76d360cedde75c10fcc7cbb0fde4791321
Confidence: high

## Findings
- [low] cli/wuwei/ws.py:136 blocks: no. Fail closed costs the audit (CWE-778): with .wuwei/cache or its clone entry linked, ws.record raises, so hook.pre_tool keeps its decision but records no refused or asked row (stderr only), and a clean merge door is denied because merge.checked cannot be written. A seat cannot plant the link (ln, mv, cp -s and python os.symlink on .wuwei/cache are refused at main and head). But `rm .wuwei/cache/clone; mkdir .wuwei/cache/clone` passes the guards and makes record raise (IsADirectoryError) the same way at main and head. That gap is pre-existing, outside this diff; a follow-up should add mkdir and mkfifo to the cache writers.
- [low] cli/wuwei/ws.py:233 blocks: no. Untested: mutant M10 (drop `path.is_file()` in cache_get) survives twice. Without it a FIFO entry (`mkfifo .wuwei/cache/hook-seen.json` passes the guards) hangs the reader. That is main's behaviour, so the mutant is no regression; the hardening has no test.
- [low] cli/wuwei/ws.py:246 blocks: no. Untested: mutant M9 (drop `path.is_file()` in cache_prune) survives twice. Without it prune would unlink a FIFO or socket inside the cache only; no outside effect.
- [low] cli/wuwei/ws.py:226 blocks: no. A hard-linked entry (same inode as an outside file) still reads through cache_get. Put replaces it by rename and prune unlinks only the name, so no write or delete reaches the outside file. Planting needs `ln`, which the guards refuse.
- [low] cli/wuwei/ws.py:138 blocks: no. `str.isalnum` is Unicode-aware and unbounded: a 1000-character clone id makes record raise ENAMETOOLONG (also on main), and a `\u0661\u00b2abc` id names a ledger file inside .wuwei/ledger. Neither leaves the folder.
- [low] blocks: no. Windows is not reachable: ws.py imports fcntl and pwd at module top, so the spec's `\`, drive and junction claims are unmeasured on a real host. On PureWindowsPath the parent check refuses `..\esc`, `D:esc`, `C:\esc`, `\\srv\share\esc` and `/esc`. `C:esc` and `stop-a:b` (an NTFS stream) stay in the cache folder; reserved device names (`con.json`) are unchecked.
- [low] blocks: no. A linked .wuwei/ledger folder or ledger file is still followed by ws.record (pre-existing, outside this item's promise beyond the clone id). TOCTOU between check and open is recorded as out of scope in the spec.

## Probes
- Diff read at 74aa5a76 against origin/main b9522fc7 (merge base b9522fc7); the PR head was read once over REST: 74aa5a76, draft, open. The vendored .claude copies of ws.py and hook.py are byte-identical to cli/.
- Route differential (my own script, git archive copies of main and head): corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 on both, 288 routes. Each route ran through guards.bash and through hook.handle PreToolUse as a planner, in 3 layouts (plain, linked cache folder, linked clone entry): 1728 cases. Decisions moved 0, reasons moved 0 in every layout, which matches specs/cache-paths/route_diff.txt (0 decision or door-reason moves).
- Files in the same differential: at main the hook wrote a ledger outside .wuwei/ledger (ws/escape.jsonl) in 120 linked-folder and 219 linked-clone cases, plus cache entries into the outside folder. At head that count is 0, and the outside folder holds only the planted clone in all 576 linked cases.
- Name probe (16 names x get, put, prune, guards.once), with //, %2e%2e%2f, /./, /../, an absolute path, a backslash, C:, ., .., the empty name, NUL, 300 chars, U+2025 and a deep ../ to an absolute path. At head, 0 writes or deletes landed outside .wuwei/cache. At main, 10 escaped, including a write to /esc.json at the filesystem root (see Residual risk). NUL raises ValueError from put, prune and once at main and at head alike: no regression.
- Layout probe at head: a linked .wuwei, a link loop and a dangling cache link each give get None, a skipped put, no prune and a record that raises OSError naming the link, with no file moved. At main, a linked .wuwei read the secret and wrote the ledger outside. A FIFO entry is skipped at head; main hung, and that run hit the 60 s timeout.
- Planting probe through guards.bash at main and head: refused for `ln -s`, `ln -sfn`, `cd .wuwei && ln -s`, `mv`, `cp -rs` and python os.symlink on .wuwei/cache, and `ln -s` on the clone entry. These pass: `rm` of the clone entry, `rm -r` of the cache, `mkdir` of cache/clone and `mkfifo` of an entry.
- Mutants, one at a time, applied to cli/ and .claude/ (test_ledger.py and test_hook.py, vendored test deselected), 11 in all. Killed: M1 folder is_symlink (test_a_cache_folder_linked_to_itself_reads_as_empty), M2 resolve compare (linked workspace folder [get]), M3 parent check (name [../esc]), M4 entry is_symlink (linked cache entry), M5 clone isalnum, M6 clone falling back to the raw path (linked clone [entry]), M7 the _confirm check (confirming answers ... linked cache folder[False]), M8 prune _cached, M11 put ignoring _cached. Survived, confirmed on a second run in fresh copies: M9 and M10 (see Findings).
- Targeted tests at head: test_ledger.py and test_hook.py, 577 passed.
- Confidence high: every escape class the promise names is closed at head with killed mutants, and the corpus differential moves 0 decisions; the remaining notes are pre-existing or unreachable.

## Residual risk
Recording can still be stopped by a plain directory or FIFO a seat may create in .wuwei/cache: the guards do not treat mkdir or mkfifo as writers (pre-existing). My main-tree probe wrote /esc.json (content "planted") at the filesystem root through main's bug; the sandbox refused its removal, and the owner should delete it.
