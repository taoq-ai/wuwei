Verdict: PASS
Gate: security
Item: verdict-symlink
PR: taoq-ai/wuwei#1137
Head: e2211fd00d0ae82f35da9e80fcb1e86c04260943
Confidence: high

## Findings
- [low] cli/wuwei/ws.py:44 blocks: no. O_NOFOLLOW is redundant beside O_EXCL: O_CREAT | O_EXCL already refuses an existing link with EEXIST. Removing it survives the tests, and a generated differential (40 temporary-name states x planted before or re-planted after the unlink x str and bytes) shows 0 differences between the head and that change. It costs nothing as defence in depth, so this is not a defect.
- [medium] cli/wuwei/hook.py:151 blocks: no. Carried from 200f361 and unchanged: the CWE-367 parent swap race between the lstat check and os.replace. It wrote into the ledger in 36 of 2000 copy-ins at this head under a RENAME_EXCHANGE loop, against 1011 at main. The plan now holds it as verdict-dirfd (a dir-fd walk, budget 10), ordered after this item merges.
- [low] cli/wuwei/hook.py:148 blocks: no. Carried from 200f361: on 3.11 and 3.12 a looping path raises RuntimeError, both for a named path inside the try and for .wuwei/verdicts at the top, outside it. The hook fails open with no write and no attest. This is pre-existing, the same at main, and covered by verdict-dirfd's promise (RuntimeError refused like OSError, recording verdict.missing).

## Probes
Delta 200f361..e2211fd read with git diff: ws.atomic_write now does unlink, then os.open(O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o666). The hook refusal names the first linked component. There are 5 new tests and the spec text changed. The vendored hook.py and ws.py are byte-identical to cli/. PR head was read once with gh api: e2211fd, still a draft.
Previous blocking finding (ws.py temporary-name link, CWE-59 / CWE-377): closed. e2e_tmpname.py through the real bin/wuwei hook SubagentStop process with 32768 links: no ledger file added, verify() is clean, and evidence.verdicts(I-9) is []. other_seat.py: the other seat's FIX is unchanged. test_zz_probe2.py: 16 cases, 0 holes, and the 4 temporary-name cases now copy in and attest a regular file.
Builder probe test_zz_probe.py at this head: 21 cases, 0 holes.
Differential diff_nofollow.py (10 states: none, file, symlink to a file, dangling, to a folder, loop, relative ../, hardlink, folder, fifo; planted before the call or re-planted after the unlink; str and bytes, 40 cases): the target never changed and the copy was never a link. Every re-plant failed closed with FileExistsError. A folder planted at the temporary name fails closed with IsADirectoryError, which only refuses the seat's own copy-in.
Mutants on the new atomic_write guards (fresh copies; tests test_hook, test_ledger, test_sync): no unlink, killed by the 4 new temporary-name tests. No O_EXCL, killed by the hardlink re-plant test. No O_EXCL and no O_NOFOLLOW, killed. Revert to write_bytes, killed. No O_NOFOLLOW survived, and the 40-case differential shows it is equivalent.
Route corpus tests/fixtures/routes.json, sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1 at main and this head: 251 routes through guards.bash, 0 moved (guards.py is not in the diff). The 6 planting commands give the same PreToolUse decisions as at 200f361.
Other atomic_write callers: all pass str. Mode 0o666 before the umask matches write_text. The unlink removes only the caller's own .<name>.<pid>.tmp. The wuwei runtime starts no threads (grep threading), so the per-pid name cannot collide inside one process. Full suite in a git archive copy: 1695 passed, 2 skipped. Runtime lines: 2979 of 3000.
Scanner: CI at this head passed every check, as the coordinator reported. The repository has no local scanner, so CWE-377 stays unmeasured by tooling and is measured here by the probes above. No dependency, lockfile or workflow change.
Confidence high: the closed finding was re-run end to end at an unknown hook pid, every new guard has a killing test or a 0-difference differential, and the residuals are measured and planned.

## Residual risk
The parent swap race (about 2 percent of hand-backs under a background exchange loop) and the 3.11/3.12 loop fail-open stay open until verdict-dirfd lands. The ledger hash chain carries no secret, so any write that reaches ledger/ can forge a valid chain.
