# Validation guide

From the repository root, use the task's pipeline interpreter.

1. Count function definitions with the regex in `.github/workflows/tests.yml`. Expected: at most 2809.
2. Collect with `../_pipeline/venv/bin/python -m pytest --collect-only -q -p no:cacheprovider tests/test_*.py`. Expected: at least 7859 items, with no changed file below its baseline.
3. Run `../_pipeline/venv/bin/python -m pytest -q -p no:cacheprovider tests/test_*.py`. Expected: all cases pass.
4. Inspect the diff for no runtime edits, skips, weakened assertions, or embedded local absolute paths.
