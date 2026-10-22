Verdict: PASS
Gate: security
Item: cross-platform
PR: taoq-ai/wuwei#1248
Head: e3a79723c9075b38496933f4ea63d6af6b306910
Confidence: medium
Supersedes: cross-platform/security-429525d.md

## Findings
- [low] cli/wuwei/guards.py:88 blocks: no. named() reads an 8.3 short name only in its prefix form (WUWEI~1, CLAUDE~1, PROJEC~1, LEDGER~1.JSO); NTFS gives the fifth and later colliding names a hash form (two letters, four hex digits, ~1, for example WU1A2B~1), which passes. It needs four earlier names sharing the prefix when .wuwei or .claude was created, so it is a limit; Git's is_ntfs_dot_generic shows the deterministic hash fallback a fix could copy.
- [low] cli/wuwei/guards.py:89 blocks: no. Case folding uses str.lower(), which leaves U+017F (long s) and U+0131 (dotless i) unchanged, so ".wuwei/ledger.j<U+017F>onl", ".claude/project<U+017F>/Q/S.jsonl" and ".wuwe<U+0131>/ledger" pass; where the file system folds them (macOS APFS case-insensitive folding long s to s; NTFS upcase unverified) they open the ledger file or a transcript. main read no case at all, so on macOS this is an existing gap the PR narrows; comparing n.upper() with p.upper() closes both. Unverified off Linux.
- [low] cli/wuwei/ws.py:27 blocks: no. Carried from the last round: Windows PROJECTS comes from user-writable HKCU\Volatile Environment, and its missing-key fallback resolves to a creatable C:\dev\null; both only narrow the transcript containment check (fail closed).
- [low] cli/wuwei/ws.py:228 blocks: no. Carried: a process holding the Windows lock byte stalls record() for 30 s and the door then denies; the same holds with flock on Linux today.

## Probes
Delta 429525d..e3a7972 read: guards.py only in runtime (cli and .claude copies identical); records() refuses when the raw reading or the windows() reading names the folder; harness keep reads backslash and the drive form only when guards.WINDOWS; windows() drops a leading X:, :stream suffixes, trailing dots and spaces; named() adds 8.3 prefix short names. Head unmoved (git ls-remote) at e3a7972.
Route corpus tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, 288 routes: pytest -k route 388 passed at e3a7972, as at main 8c38073; 0 moved.
My round-1 probes re-run at e3a7972: bsprobe.py 8 of 8 denied, ledger files read 0, transcript unchanged; e2e.py through bin/wuwei hook PreToolUse: Write and Bash ledger plants deny, control deny; bracket.py 4 of 4 denied, .wuwei tree unchanged; wrap.py generated 20, holes 0; genprobe.py generated 700, Linux-runnable 225, refused 700, Linux holes 0, Windows-spelling misses 0.
Builder probes re-run: spelling probe generated 481, ran the door program 481, holes 0; normalisation probe 21 inputs, 0 MISS.
Union defeat probe defeat.py, 27 spellings x (Write tool, Bash redirect) x guards.WINDOWS False and True: in-under-Windows-out-under-raw and the reverse both refused (x\..\.wuwei, .wuwei\ledger, .wuwei/ledger/x\..\..\..\a, a:..\..\b), colon and trailing-strip tricks that could mint a '..' refused (..:x, '.. .'), C:.wuwei, C:/.wuwei, WUWEI~1, WUWEI~5, wuwei~1, WU~1, CLAUDE~1/projects, CLAUDE~1/PROJEC~1, LEDGER~1.JSO, ::$INDEX_ALLOCATION, trailing space, \\.\ and \\?\GLOBALROOT device paths all refused. Allowed: .wuwei/ledger/x:/../../a.jsonl and .wuwei/C:\..\..\a.jsonl (on Linux both land in .wuwei itself, outside ledger and cache, as main allows), the 8.3 hash forms and the Unicode case forms (notes above).
Mutants on the fix in fresh copies, both trees: drop the raw reading killed by test_a_name_holding_backslash_dots_inside_the_ledger_is_refused_where_backslash_is_a_name_character; drop the Windows reading killed by test_windows_and_macos_spellings_judge_as_on_linux; read backslash in keep on every OS killed by test_a_memory_path_with_backslash_dots_that_lands_on_a_transcript_is_refused.
closed: records() backslash read lets a backslash-dotdot name plant ledger and cache files and clears inside for cd, pushd, env -C at e3a7972
closed: harness keep reads backslash on POSIX and lets a staged path overwrite a transcript at e3a7972
closed: Windows trailing dot, drive-relative, ::$INDEX_ALLOCATION and 8.3 prefix spellings into .wuwei at e3a7972
Scanner: no secret, dependency or static-analysis scanner runs on this diff; unmeasured. No new dependency.
Confidence medium: Linux results are real writes under bash; Windows and macOS file-system behaviour (short names, case folding) is judged from documentation, not run.

## Residual risk
Path-spelling guards stay best effort against file-system aliasing (8.3 hash names, Unicode case folding, PowerShell and zsh quoting); a Windows and macOS CI test per alias class would measure them.
