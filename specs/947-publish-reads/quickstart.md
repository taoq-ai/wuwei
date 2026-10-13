# Validation

From the repository root, use the task-specified Python interpreter:

```sh
python -m pytest -q -p no:cacheprovider tests/test_edges.py
```

The edge tests use temporary workspaces and fake adapters. They classify the two reported commands without executing them. Include tests/test_signal_status.py in the follow-up run. Run every additional test file found by searching tests for imports of edges, with the same interpreter and pytest flags. No real GitHub or network calls are required.
