# Validation

From the worktree root, use the task-prescribed pipeline interpreter with
`-m pytest -q -p no:cacheprovider` and explicit test files. First run
`tests/test_handback.py tests/test_build_next.py tests/test_reconcile.py` for
regressions. Then include every test file importing a changed module.
All adapters that could contact external services must be replaced by test fakes.
Expected: final text records once; running tasks have no stop offer; transport
failures become gaps; committed recovery reaches checks then gates.
