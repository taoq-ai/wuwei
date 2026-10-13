# Validation

From the worktree root, use the task's pipeline interpreter:

```sh
../_pipeline/venv/bin/python -m pytest -q -p no:cacheprovider tests/test_agent_launch.py tests/test_launch_contract.py
```

New cases launch directly from a prompt, check private persistence and stop
binding, refuse guard violations, and exercise terminal-report recovery.
Before completion also run every test file found by searching tests for the
changed module names, plus tests/test_signal_status.py. Adapters are fakes;
no real GitHub or network calls. Review regressions additionally cover gate
receipt refusal, planned-builder refusal, explicit item inference, first-prompt
identity, and nested/planner ad-hoc refusal.
