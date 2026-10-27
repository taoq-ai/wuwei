# Validation

From the worktree root:

```sh
uv run --no-project --with pytest python -m pytest -q tests/test_evidence.py tests/test_guards.py
```

Pending review permits auto-merge across CLI, REST and MCP routes. Direct merge and failed-review routes remain refused. Ready regression cases retain green non-review CI and passed gates. Route differential compares archived main and head trees using the same tests and fake PR evidence.
