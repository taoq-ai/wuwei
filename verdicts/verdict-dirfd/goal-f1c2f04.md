Verdict: PASS
Gate: goal
Item: verdict-dirfd
PR: taoq-ai/wuwei#1151
Head: f1c2f04d6d28aa896d59130eea5992a4cb4b914b
Confidence: medium

## Findings
- [low] blocks: no. The PR body's Residual risk names the post-write read-back by path (hook.py `path.read_bytes()`), which still follows a parent swapped in after the write. The item's promise covers the write path only, and the body states it, so this is a disclosed limit, not drift.
- [low] blocks: no. `sync.pull` now raises OSError at a planted link (How this fails 1 in spec.md) where main wrote through it. This is the stated intent of "Covers sync.py:82" and is recorded as an assumption in the body; the owner can overturn it.

## Probes
- Traced G-2 (bugs found running WUWEI on itself are fixed before features) to the item's why (security gate on #1137: swap race lands writes in the ledger; RuntimeError on 3.11 and 3.12 fails SubagentStop open) to the diff in cli/wuwei/hook.py, ws.py and sync.py. Each promise clause has an artifact:
  - Directory fds: ws.py `atomic_write` opens root, then each component with `O_DIRECTORY|O_NOFOLLOW` relative to the previous fd, creates the temp with `O_CREAT|O_EXCL|O_NOFOLLOW` at `dir_fd=fd`, and renames with `src_dir_fd` and `dst_dir_fd`. The hook passes `Path(root).resolve()` (hook.py copy-in).
  - RuntimeError: `verdicts.resolve()` moved inside the `try`, and the `except` is now `(OSError, ValueError, RuntimeError)`.
  - sync.py:82 passes `Path(root) / ws.DIR` as the root.
- Acceptance 1 (swap, 2000 copy-ins, no ledger change): the body reports 0 of 2000 ledger files changed at the head, at both levels on 3.13 and 3.11, against 256 to 331 at main. I did not re-run `race_probe.py`; I read the numbers from the body, so they are the builder's, not mine.
- Acceptance 2 (loop at verdicts on 3.11 refuses and records verdict.missing): `test_a_looping_verdicts_folder_refuses_the_handback_and_records_verdict_missing` asserts deny, one verdict.missing row, no hook.error and no attest. I ran it on Python 3.11 with `uv run --python /usr/bin/python3.11`: `-k "looping or swapped"` gave 3 passed.
- Ran `pytest -q tests/test_hook.py tests/test_sync.py` on 3.13 at the head: 171 passed.
- Body checks. WUWEI-Item: verdict-dirfd is present. The promise is restated in the builder's own words and matches the item (fds, RuntimeError, sync.py:82). Assumptions has two entries with what would overturn each. The scope added, `free()` failing closed (a refusal text instead of StopIteration or PermissionError), is named and tied to the #1144 gate brief, and the diff matches. Size reads "+16 against 10".
- Counts read at the head with `git ls-tree` and `wc -l` on cli/wuwei/*.py: 2993 at d7c4f43 and 3009 at the head, +16, under the 3,400 cap. `git diff --numstat d7c4f43 HEAD -- cli/` gives 30 added and 14 removed, as the body says.
- The vendored copy `.claude/wuwei/cli/wuwei` matches `cli/wuwei` (`diff -r -q` shows only __pycache__).
- Drift check, missing: no promised outcome is absent. Claimed without a requirement: only the `free()` change, which is disclosed and traceable to the caller's brief. The "re-plant test moved from Path.unlink to os.unlink" claim follows from the write moving to `os.unlink(dir_fd=)`.
- The Rollback line (revert the commit and re-vendor) is present.
- Not done by me: the route-corpus differential (251 routes, 0 moved) and the path probe (14 cases) are quoted from the body; the security and quality gates own their re-runs.

## Residual risk
The race numbers and the 3.11 path-probe counts are the builder's own and I did not reproduce them. The fix is Linux and macOS only (`*at` calls), which the body discloses.
