Verdict: PASS
Gate: security
Item: verdict-closed
PR: taoq-ai/wuwei#1144
Head: d8a09671df6f45863316df639ea055e3f65e6993
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/hook.py:147 blocks: no. CWE-755 (improper handling of exceptional conditions): free() can raise. StopIteration comes when -2 through -998 are all held. PermissionError comes when the folder can be traversed but not listed. The call sites at :169 and :173 are outside the try. The call at :156 is inside it, but StopIteration is not an OSError or ValueError. handle() records hook.error and, since SubagentHandback is not a door, lets the hand-back and the stop through without the refusal main delivered. Attestation stays closed (0 attest rows, held -2 unchanged), so no trust property is lost; the seat is only left untold. A default for next() and an OSError fallback would keep the refusal.
- [low] cli/wuwei/hook.py:148 blocks: no. CWE-407 (inefficient algorithmic complexity): the name set is rebuilt for every candidate number, so the cost is held numbers x folder entries. 997 held took 8.3 s and 9.8 s; with 2,000 other files 26 s; with 20,000, 185 s. Main took 0.0 s. hooks/hooks.json sets no timeout. Planting it needs workspace write, and it fails closed on attestation. Building the set once fixes it.
- [low] blocks: no. A limit that predates this diff and that it leaves unchanged (OWASP LLM05 improper output handling, CWE-20): the parser reads only ## Findings. So a PASS with an open blocker written under ## Probes, with or without the closed: prefix, is attested and counted as PASS by evidence.verdicts, the same at main and at the head. A FIX still counts as FIX wherever its findings sit. This is the same as leaving the finding out, and a shape check cannot judge truth. A follow-up item could refuse a blocks: yes FINDING line under Probes that lacks the closed: prefix, which catches honest misfiling only.
- [low] cli/wuwei/hook.py:147 blocks: no. Untested: two mutants survive in fresh copies. S4 counts directories as free and S5 drops the $ anchor of the strip. Neither does harm: a directory at -2 sends the seat's copy-in to the readable-file refusal, and S5 renames only odd stems such as quality-abc1234-2-3.

## Probes
Confidence reason: a generated 5,760-row matrix and the main-versus-head differential show no hook write outside the workspace and no named file that is held. free() only names a file and never writes. All remaining findings concern availability, not integrity. What would lower it: a run on a case-insensitive filesystem (unmeasured).
Suite (git archive copies, /root/.local/bin/pytest -q): head 1789 passed, 2 skipped; main 3d2eb29 1774 passed, 2 skipped.
Route corpus (builder probe_differential.py + compare.py, re-run): tests/fixtures/routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at main and head. 251 routes went through guards.bash and PreToolUse with 0 moved, and 7 payload fixtures with 0 moved.
Builder hand-back matrix, re-run: 232 rows, 124 reasons moved, 0 attest counts moved. At the head, 140 refusals name a next file and all 140 are free and attest, 0 holes (main has 32). The outside file never changed.
Builder mutants M1-M9 re-run in fresh git archive copies: 9 of 9 killed.
Own matrix (probe_sec.py): 4 layouts (plain; item folder linked out; .wuwei/verdicts linked out; item folder linked inside verdicts) x 8 states at -2 (none, file, dangling link, link out, link to a sibling verdict, directory, hardlink out, another seat's attested verdict at the base) x 3 names (base, -2, -12) x 5 spellings (plain, //, /./, /../, %2D) x root-relative, root-absolute, worktree x SubagentStop, SubagentHandback x shape-refused, well-formed. That is 5,760 rows; 512 were skipped because the seat would write through a link or onto a directory, leaving 5,248 live.
Head on that matrix: 1,096 refusals name a next file. None names a file, directory or link the real folder holds. lstat snapshots of the workspace and outside folder before and after each call show 0 hook writes outside. A good verdict written at each named file changed no other file, and 1,096 of 1,096 attested with 0 refusals.
Main versus head on that matrix: hook-changed paths, attest rows and decision kinds are the same in all 5,248 rows. The 128 rows where the outside hardlink target changed are the seat's own write onto a held hardlink before the hook ran, the same at main.
#1137 link check: every worktree row with a link at the copy path or on a parent got the symlink refusal, at the head as at main (240 rows per linked layout per body). free(copy) runs only after that check, and both other free(path) calls take a resolved path.
Normalisation: the //, /./, /../ and %xx classes on the Verdict file path are all in the matrix. %2D stays literal for both the hook and the OS, so the name is the literal-percent file in the same folder. The cd, env -C and sudo -D wrappers do not apply because the input is a path, not a command.
Odd stems (probe_stems.py, 18 cases: -0, -02, -2-3, uppercase hex, 8 hex, a 7-digit sha, an Arabic-Indic digit, a zero-width space, a 30-digit suffix, a 245-character stem, .md): every named file is in the same folder, free and writable, with no hook error. Names come only from the seat's own stem, so other seats' file names are never echoed into the prompt.
Exhaustion (-2 to -998 held): at the head, StopIteration leads to hook.error, with no refusal on either event, 0 attest rows, and the copy-in leaves the held -2 unchanged. Main refused.
Unlistable folder (PermissionError from iterdir, simulated because root ignores mode 0311): at the head, hook.error, no refusal, 0 attest rows. Main refused.
Hidden blockers (8 bodies: PASS or FIX with a blocker under Probes, closed: under Findings, a second Findings section and others): the hook result, attest rows and evidence.verdicts counts are the same at main and at the head.
Own mutants: S1 (copy-in lists the worktree folder), S2 (exists() instead of the listing) and S3 (only -2 tried) were killed. S4 and S5 survived, then survived again in fresh copies.
Scanners: in CI at d8a0967, CodeQL, ZIRAN and ziran-audit succeeded ("No new alerts in code changed by this pull request"). ziran is not installed here, so a local run is unmeasured. The diff changes no dependency, lockfile or workflow.
Combinatorial bash probe: not run, because guards.py and the command parser are untouched. door(), the leak check and the ask rule are unchanged.

## Residual risk
On a case-insensitive filesystem, free() compares names exactly, so a held Quality-...-2.md would let it name quality-...-2.md again. The #1137 lstat check still refuses a link there. Untested here.
A seat that hides an open blocker outside ## Findings is not caught. This is the same at main and the same as leaving the finding out.
