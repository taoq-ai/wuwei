# Validation

From the worktree root, use the interpreter assigned by the task with:

```text
-m pytest -q -p no:cacheprovider tests/test_protect_state.py tests/test_hooks.py
```

The regression table submits Bash text through the full PreToolUse pipeline and
checks deny plus a protect_state refusal record. It never runs that Bash text.
Shim replay tests check the shipped Claude Code hook configuration. Before final
verification, search tests/ for protect_state and include every importing file
explicitly, plus enforcement and scope integration coverage.
