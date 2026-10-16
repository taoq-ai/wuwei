Verdict: FIX
Gate: quality
Item: 1065
PR: taoq-ai/wuwei
Head: b0e6aaf29462e3ee72ddb7a1e34c926dd136be33
Confidence: high
Breaking: no

## Findings
- [medium] cli/wuwei/setup.py:150 blocks: yes. Failure: doctor loops over `ws._parse(...)` rows and calls `row.get('kind')`, but `_parse` returns whatever `json.loads` gives. A line in this clone's ledger file that is valid JSON but not an object (`[1]`, `null`, `5`, `"x"`) makes `wuwei doctor` die with `AttributeError: 'list' object has no attribute 'get'`. On origin/main the same ledger gives `ledger fail broken at ledger/<clone>.jsonl:2` and the run finishes. So the diagnostic that reports a damaged ledger now crashes on one, a regression. Fix: skip rows that are not dicts, e.g. `if isinstance(row, dict)` in the loop, and add a test line for it. Malformed and empty lines are already handled by `_parse`.
- [low] tests/test_setup.py blocks: no. Note: no test covers a non-object line, a clone file with no workspace.init row (works: a hook row there counts), or `init --cloud` over a settings.json that already holds other hooks, or run twice. I compared old and new instead (see Probes) and they match, so this is a missing test only.
- [low] cli/wuwei/setup.py:123 blocks: no. Note: `repos = (config := ws.config(root) if root else ws.DEFAULTS)['repos']` is hard to read; it saves a line to stay at 3,000. The runtime is exactly 3,000 lines, so the next change must remove lines first.

## Probes
- Suite in a copy of the head: 265 passed.
- Settings equivalence: ran init in a copy of origin/main and of the head, in 7 cases: plain, cloud, plain and cloud over a settings.json with an existing Stop hook, a custom event, `model` and other `permissions.allow`, cloud twice, and plain then cloud. settings.json is byte-identical in every case, key order included.
- vendor() has one caller (init); the moved hook block runs for `--cloud` only, as before.
- Ledger shapes (probe script, head): malformed line and blank lines are ignored (hook row still counts or not as it should); non-object lines crash doctor (finding); clone file with no init row plus a refused row gives ok; no clone file gives warn.
- On origin/main the same `[1]` line gives a ledger fail row and doctor completes, so the crash is new.
- Mutants, each run against tests/test_setup.py in a copy: drop the workspace.init reset -> test_doctor_counts_a_hook_row_in_this_clones_ledger_since_the_latest_init fails; add `attest` to HOOK_ROWS -> same test fails; read every clone's file -> same test fails; drop the `.wuwei/executable` check -> test_doctor_reads_the_code_host_as_wuwei_does_and_says_when_no_hook_fired fails; drop the cloud hook loop -> test_init_cloud_vendors_the_plugin_into_the_repository fails.
- Simplicity: the `HOOK_ROWS` set and the single loop are needed. A small cleanup is possible: `ws.clone(root)` creates the clone file when it is missing, so doctor writes on a read-only check; that is acceptable (ws.record does the same), so nothing to delete.

## Residual risk
Past the non-object line, the change matches the four acceptance scenarios and I found no gap. The size test passes at exactly 3,000 lines.
