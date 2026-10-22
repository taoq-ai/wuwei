Verdict: FIX
Gate: quality
Item: cache-paths
PR: taoq-ai/wuwei#1242
Head: b0956601b321b967055ab6f39bf0942b6a41c6dd
Confidence: medium

## Findings
- [medium] cli/wuwei/ws.py:136 blocks: yes. Failure: ws.clone reads and writes .wuwei/cache/clone without going through ws._cached, so a symlink planted at .wuwei/cache/clone (or a linked cache folder) is followed; a target file holding `../../../evil` makes ws.record append the ledger to `<ws>/../evil.jsonl` outside .wuwei (probe run at the head printed id `../../../evil` and created evil.jsonl outside the workspace), and a linked cache folder serves the clone id from outside the workspace; this violates FR-001 and the goal "every cache read, write and prune" (CWE-59, CWE-22)
- [medium] tests/test_ledger.py:0 blocks: yes. Failure: no pytest covers a linked .wuwei; removing the `folder.resolve() == Path(root).resolve() / DIR / 'cache'` check at cli/wuwei/ws.py:221 (mutant m2, applied to both trees) passes all 20 selected tests, and the repository's own specs/cache-paths/probe.py then shows 3 holes (link:wsdir:get returns the outside secret, put and prune change outside/cache/esc.json), so a workspace whose .wuwei is a link out would read, overwrite and delete files in the link target (CWE-59); the same check is also the only Windows junction guard and is untested
- [low] cli/wuwei/ws.py:251 blocks: no. A NUL in a payload-built name (session_id "a\u0000b") still makes cache_put raise ValueError out of atomic_write (same at main, and cache_prune raises it too); nothing leaves the folder, but the Stop hook would error instead of skipping. Suppressing ValueError in the helper's callers or rejecting NUL in _cached would close it.
- [low] cli/wuwei/ws.py:245 blocks: no. `path.is_file()` in cache_prune is untested and likely redundant (mutant m7, removed: 20 passed); unlink on a directory raises OSError, which the suppress already covers. A differential probe was not run, so untested rather than deletable.
- [low] cli/wuwei/ws.py:226 blocks: no. `path.is_file()` in cache_get is untested (mutant m5 survives); read_text on a directory raises OSError, already suppressed. Same reading as the note above.
- [low] blocks: no. Cross-platform: the new code uses only Path.resolve, is_symlink, is_file and parent equality, so FR-002 holds. atomic_write (O_DIRECTORY, dir_fd) and ws.record (fcntl) are POSIX-only already at main, so the Windows claim for the helper does not extend to the cache write path; not this item's change.

## Probes
- pytest tests/test_ledger.py tests/test_hook.py in a git archive of the head: 569 passed.
- specs/cache-paths/probe.py, re-run under my scratch folder at the head: generated 21, ran 21, holes 0 (python3 3.13 and python3.11 both).
- Adversarial names, head against main (put, get, prune): '', '.', '..', '...', backslash path, 'C:esc', 'C:\esc', NUL, 300 and 5000 characters, newline, 'a/', '/', '//', non-ASCII, '.json', 'a.b'. Nothing writes outside the cache at either; the head additionally refuses 'a/', '/', '//' and the 5000-character name (get None, put skipped). NUL and the 300-character name still raise on put (same as main).
- Mutants (one at a time, both ws.py copies, vendored-drift test deselected): m1 drop `not folder.is_symlink()` KILLED by test_a_cache_folder_linked_to_itself_reads_as_empty; m3 drop `path.parent == folder` KILLED by test_a_name_never_leaves_the_cache_folder[../esc]; m4 drop `not path.is_symlink()` KILLED by test_a_linked_cache_entry_reads_as_absent_and_is_never_pruned_through; m6 prune without the `_cached(root, path.stem) == path` check KILLED by test_a_linked_cache_folder_is_never_read_written_or_pruned; m8 put writing without the helper KILLED by the same test; m9 cache_get without the helper KILLED by the same test; m2 drop the resolve comparison SURVIVED (finding 2); m5 and m7 SURVIVED (notes); m10 reverse the prune age comparison SURVIVED in these two files (pre-existing line, covered by tests/test_watch.py:304, not run).
- Tests: the four new tests in tests/test_ledger.py and the one in tests/test_hook.py reach the real consumer (cache_get, cache_put, cache_prune and the Stop hook); no wall-clock or network dependence; the plan records them red on main.
- Callers: every ws.cache_get, ws.cache_put and ws.cache_prune user (evidence.py, board.py, hook.py, guards.py, setup.py, __main__.py) goes through the helpers. Two bypasses: ws.clone (finding 1) and hook.py:344 `glob(f'answer-{session}--*.json')`, which is safe because the session is stripped to `[\w-]` and each hit is re-read by name through cache_get. replay.py:37 only rmtrees a copy's cache.
- TOCTOU between the check and the open: recorded out of scope by the PR; accepted, the same writer already writes the workspace.
- Runtime lines: +12 net in ws.py (17 added, 5 removed), within FR-003; ws.py is copied to the vendored tree identically.

Simplicity: `path.is_file()` in cache_get and cache_prune can probably be deleted (the suppressed OSError already covers a directory entry), after a differential probe shows 0 differences; not listed as deletable until then. The helper's two folder checks (is_symlink and the resolve comparison) both stay: the first alone misses a linked .wuwei, the second alone misses nothing but the self-link case on Python 3.11.

## Residual risk
Once clone is routed through the same check and a linked .wuwei is pinned by a test, the cache path is closed apart from the accepted check-then-open race. Without the fix, the clone id remains a way to steer the ledger append path for anyone who can plant a link in .wuwei/cache.
