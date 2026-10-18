Verdict: PASS
Gate: quality
Item: verdict-symlink
PR: taoq-ai/wuwei#1137
Head: e2211fd00d0ae82f35da9e80fcb1e86c04260943
Confidence: high

## Findings
- [low] cli/wuwei/ws.py:44 blocks: no. Two surviving mutants are untested, and both were re-run in a fresh copy (1695 passed each). D3 drops O_NOFOLLOW. A generated differential of head against D3 gave 0 differences on 3.11 and on 3.13 (66 cases: 11 states planted at the temporary name x 2 moments x 3 copy states), so O_NOFOLLOW is redundant beside O_EXCL. It is still a fail-closed safeguard and should stay. D10 creates the file at 0o600 instead of 0o666. No test pins the mode that the 17 other atomic_write callers get. The head keeps the old mode (write_text's 0o666 before the umask), as plan.md records.
- [low] blocks: no. The refusal text departs from the promise's wording. The promise says the refusal "says to remove the link". The head names the first linked component and says "leave it, and report it under Blocked: for the owner". The reason is recorded in the spec Clarifications: a seat must not edit the workspace. It is a requirement-text change for the goal gate to weigh. The behaviour (refuse, write nothing) is unchanged.
- [low] blocks: no. An existing gap, carried from round 1 and now stated correctly in the spec: a loop at .wuwei/verdicts itself raises RuntimeError at hook.py:146 on 3.11 and 3.12, and the hook fails open with no write. Main behaves the same, and the planner has made it a follow-up item.

## Probes
Delta 200f361..e2211fd: hook.py (the refusal names the first link), ws.py (unlink, then os.open with O_CREAT|O_EXCL|O_NOFOLLOW at 0o666, written through the fd), tests/test_hook.py (+5 cases), and the spec. The vendored copy matches (diff -r clean). Runtime is 2,979 lines (cat cli/wuwei/*.py | wc -l), +3 against the item's budget of 3.
Round-1 high finding (link at the temporary name) is closed. Re-ran probes/attack.py at the head on 3.11, 3.12 and 3.13: the ledger file keeps its own rows, the copy is a regular file, and 1 attest row is written. At 200f361 the same plant lost the rows.
Round-1 M7 is closed: test_a_workspace_reached_through_a_symlinked_path_still_copies_in kills it (D8, 1 failed). probes/linked_root.py at the head attests on 3.11, 3.12 and 3.13.
Suite at head: 1695 passed, 2 skipped (test_release.py:36 and :57, ssh-keygen absent). The new tests go through reviewer_stop -> hook.handle SubagentStop. Head tests against the 200f361 code: the 4 temporary-name cases fail (as do 5 cases on the changed message), so they were red first.
Delta mutants, each in a fresh git archive copy with the vendored copy mutated too, over the full suite: D1 temporary file by write_bytes, 4 failed; D2 no O_EXCL, 1 failed (the hardlink replant); D4 no unlink, 4 failed; D5 O_TRUNC without EXCL/NOFOLLOW, 2 failed; D6 drop the copy's own check, 4 failed; D7 drop the parent check, 2 failed; D8 unresolved root, 1 failed; D9 name the copy, not the link, 2 failed. D3 (no O_NOFOLLOW) and D10 (0o600) survive, both re-run fresh; D3 is equivalent by the differential above.
Route corpus: sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1. All 251 routes were read through guards.bash at main and at e2211fd, comparing the full decision (verdict and reason): 0 moved.
Generated combinatorial bash probe: N.A. guards.py and the guard's command parsing are untouched. The hook.py change reads the path from the report text, not from a shell command.
Confidence high: the round-1 attack is re-run end to end on three Python versions, and every behavioural mutant in the delta is killed.
Simplicity: none. Every new line is a trust-boundary or fail-closed safeguard (unlink, exclusive create, link check), and O_NOFOLLOW stays as defence in depth even though it is equivalent beside O_EXCL.

## Residual risk
A folder link swapped in between the check and os.replace can still redirect the rename. The builder records this, and it is a follow-up item. Likewise the 3.11 and 3.12 fail-open on a loop at verdicts/ itself.
