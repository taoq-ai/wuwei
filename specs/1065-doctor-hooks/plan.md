# Plan: doctor hooks check (#1065)

## Approach

- `cli/wuwei/setup.py`: a `HOOK_ROWS` set. In `doctor`, walk this clone's ledger file and keep
  the kinds seen since the last `workspace.init`; `ok hooks` when `.wuwei/executable` exists or
  that set meets `HOOK_ROWS`.
- Lines: `doctor` reads `ws.config(root)` once (-1). The cloud hook entries move from `vendor`
  into `merge_settings(directory, cloud)`, so settings.json is parsed and written once per init
  (-3). Net zero in setup.py.
- `tests/test_setup.py`: one test for scenarios 1 to 3, plus `attest` and `sent` not counting.
  The existing doctor test holds scenario 4; the size test holds scenario 5.

## Constitution check

Stdlib only, no new module, runtime at 3,000 lines, test first.
